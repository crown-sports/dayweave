"""Local browser interface with bounded requests, independent export validation, and explicit model configuration."""

from __future__ import annotations

import asyncio
import json
import secrets
import time
from collections.abc import Awaitable, Callable
from importlib.resources import files
from typing import Any

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, Response
from starlette.concurrency import run_in_threadpool

from .calendar_io import export_calendar, import_calendar
from .capture import capture_note
from .contracts import InputError, PlanningInput, strict_json
from .examples import example
from .scheduler import schedule


def create_app(model_endpoint: str | None = None, model: str = "qwen3:4b") -> FastAPI:
    """Expose local computations; no connected calendar, filesystem path, or messaging action is accepted."""
    app = FastAPI(docs_url=None, redoc_url=None, openapi_url=None)
    token = secrets.token_urlsafe(32)
    gate = asyncio.Semaphore(2)
    downloads: dict[str, tuple[float, bytes, str, str]] = {}

    def downloadable(data: bytes, content_type: str, name: str) -> Response:
        """Offer a normal browser download from bounded, five-minute memory storage."""
        now = time.monotonic()
        for key in list(downloads):
            if downloads[key][0] < now:
                del downloads[key]
        while len(downloads) >= 8:
            del downloads[next(iter(downloads))]
        key = secrets.token_urlsafe(24)
        downloads[key] = (now + 300, data, content_type, name)
        return Response(
            data,
            media_type=content_type,
            headers={
                "Content-Disposition": f"attachment; filename={name}",
                "X-DayWeave-Download": f"/download/{key}",
            },
        )

    @app.middleware("http")
    async def local_requests(request: Request, call_next: Callable[[Request], Awaitable[Response]]) -> Response:
        if request.url.hostname not in {"127.0.0.1", "localhost", "::1"}:
            return JSONResponse({"error": "Use a local loopback URL"}, status_code=403)
        if request.method == "POST":
            if request.headers.get("origin") != str(request.base_url).rstrip("/"):
                return JSONResponse({"error": "Local same-origin requests are required"}, status_code=403)
            if request.cookies.get("dayweave_session") != token or request.headers.get("x-dayweave-token") != token:
                return JSONResponse({"error": "Reload this local page to establish a session"}, status_code=403)
            length = request.headers.get("content-length", "")
            if not length.isdigit() or not 0 < int(length) <= 2097152:
                return JSONResponse(
                    {"error": "Request exceeds its 2 MiB limit or has no declared length"}, status_code=413
                )
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Cache-Control"] = "no-store"
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; "
            "connect-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'self'"
        )
        return response

    async def payload(request: Request) -> dict[str, Any]:
        data = bytearray()
        async for chunk in request.stream():
            if len(data) + len(chunk) > 2097152:
                raise InputError("Request is too large")
            data.extend(chunk)
        result = strict_json(bytes(data))
        if not isinstance(result, dict):
            raise InputError("Expected an object")
        return result

    @app.exception_handler(InputError)
    async def bad_input(request: Request, error: InputError) -> JSONResponse:
        return JSONResponse({"error": str(error)}, status_code=400)

    @app.get("/")
    async def home() -> Response:
        return Response(files("dayweave").joinpath("ui/index.html").read_bytes(), media_type="text/html")

    @app.get("/assets/{name}")
    async def asset(name: str) -> Response:
        modules = {"app.js", "calendar.js", "controls.js", "project_state.js", "input_editor.js", "capture_sheet.js"}
        allowed = {**dict.fromkeys(modules, "text/javascript"), "workbench.css": "text/css"}
        if name not in allowed:
            return Response(status_code=404)
        return Response(files("dayweave").joinpath("ui", name).read_bytes(), media_type=allowed[name])

    @app.get("/api/session")
    async def session() -> JSONResponse:
        response = JSONResponse({"token": token, "model_enabled": bool(model_endpoint), "version": "0.1.0"})
        response.set_cookie("dayweave_session", token, httponly=True, samesite="strict")
        return response

    @app.get("/api/example/{kind}")
    async def sample(kind: str, day: str = "2026-10-05", timezone: str = "Asia/Shanghai") -> dict[str, Any]:
        return example(kind, day, timezone)

    @app.post("/api/solve")
    async def solve(request: Request) -> dict[str, Any]:
        body = await payload(request)
        plan = PlanningInput.from_dict(body)
        async with gate:
            return await run_in_threadpool(schedule, plan)

    @app.post("/api/capture")
    async def capture(request: Request) -> dict[str, Any]:
        body = await payload(request)
        source, anchor = body.get("text"), body.get("anchor")
        if not isinstance(source, str) or not isinstance(anchor, str):
            raise InputError("Capture needs a text note and an explicit reference date/time")
        async with gate:
            return await run_in_threadpool(
                capture_note,
                source,
                anchor,
                body.get("timezone", "Asia/Shanghai"),
                model_endpoint,
                model,
            )

    @app.post("/api/calendar")
    async def calendar(request: Request) -> dict[str, Any]:
        body = await payload(request)
        plan = PlanningInput.from_dict(body.get("plan"))
        source = body.get("text")
        if not isinstance(source, str):
            raise InputError("Calendar import needs the contents of an .ics file")
        async with gate:
            return await run_in_threadpool(import_calendar, source, plan)

    @app.post("/api/export")
    async def export(request: Request) -> Response:
        body = await payload(request)
        plan = PlanningInput.from_dict(body.get("plan"))
        slots = body.get("slots")
        if not isinstance(slots, list) or len(slots) > 300 or not all(isinstance(slot, dict) for slot in slots):
            raise InputError("Export requires bounded schedule segments")
        result = export_calendar(plan, slots)
        return downloadable(result, "text/calendar", "dayweave.ics")

    @app.post("/api/backup")
    async def backup(request: Request) -> Response:
        body = await payload(request)
        project = body.get("project")
        if not isinstance(project, dict):
            raise InputError("A project backup must be an object")
        result = json.dumps(project, ensure_ascii=False, separators=(",", ":")).encode()
        if len(result) > 2097152:
            raise InputError("Project backup exceeds its 2 MiB limit")
        return downloadable(result, "application/json", "dayweave-project.json")

    @app.get("/download/{key}")
    async def download(key: str, request: Request) -> Response:
        if request.cookies.get("dayweave_session") != token:
            return Response(status_code=403)
        item = downloads.get(key)
        if item is None or item[0] < time.monotonic():
            downloads.pop(key, None)
            return Response("This download expired; generate the file again.", status_code=404)
        _, data, content_type, name = item
        return Response(data, media_type=content_type, headers={"Content-Disposition": f"attachment; filename={name}"})

    return app
