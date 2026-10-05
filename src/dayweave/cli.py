"""Small entry points for the browser, reproducible schedule calculation, and local calendar export."""

from __future__ import annotations

import argparse
import json
import sys
import threading
import webbrowser
from pathlib import Path

from .calendar_io import export_calendar
from .contracts import InputError, PlanningInput, strict_json
from .examples import example
from .scheduler import schedule


def main() -> int:
    """Run ordinary-user browser workflows or inspect the same algorithm through JSON files."""
    parser = argparse.ArgumentParser(prog="dayweave", description="Fit your commitments into your actual free hours")
    commands = parser.add_subparsers(dest="command", required=True)
    serve = commands.add_parser("serve", help="Open the local personal planner")
    serve.add_argument("--port", type=int, default=8787)
    serve.add_argument("--open", action="store_true", help="Open your default browser after starting")
    serve.add_argument("--model-url")
    serve.add_argument("--model", default="qwen3:4b")
    calculate = commands.add_parser("plan", help="Calculate a reviewable plan from a JSON input")
    calculate.add_argument("input", type=Path)
    calculate.add_argument("--output", type=Path)
    calculate.add_argument("--calendar", type=Path)
    sample = commands.add_parser("example", help="Write an editable example")
    sample.add_argument("kind", choices=("balanced", "sorting", "overload"), default="balanced", nargs="?")
    sample.add_argument("--day", default="2026-10-05")
    sample.add_argument("--output", type=Path)
    model = commands.add_parser("model-serve", help="Run optional local Hugging Face note capture")
    model.add_argument("--path", type=Path, required=True)
    model.add_argument("--port", type=int, default=8788)
    args = parser.parse_args()
    try:
        if args.command == "serve":
            import uvicorn

            from .web import create_app

            print(f"Open http://127.0.0.1:{args.port} · your project stays in this browser")
            if args.open:
                opener = threading.Timer(1.0, webbrowser.open, args=(f"http://127.0.0.1:{args.port}",))
                opener.daemon = True
                opener.start()
            uvicorn.run(create_app(args.model_url, args.model), host="127.0.0.1", port=args.port, log_level="warning")
        elif args.command == "plan":
            data = args.input.read_bytes()
            if len(data) > 2097152:
                raise InputError("Plan files must be at most 2 MiB")
            plan = PlanningInput.from_dict(strict_json(data))
            result = schedule(plan)
            content = json.dumps(result, ensure_ascii=False, indent=2) + "\n"
            if args.output:
                args.output.write_text(content)
            else:
                print(content, end="")
            if args.calendar:
                if result["state"] != "scheduled":
                    raise InputError("Resolve conflicts before exporting to a calendar")
                args.calendar.write_bytes(export_calendar(plan, result["slots"]))
        elif args.command == "example":
            content = json.dumps(example(args.kind, args.day), ensure_ascii=False, indent=2) + "\n"
            if args.output:
                args.output.write_text(content)
            else:
                print(content, end="")
        elif args.command == "model-serve":
            import uvicorn

            from .local_model import create_model_app

            uvicorn.run(create_model_app(args.path), host="127.0.0.1", port=args.port, log_level="warning")
    except (InputError, OSError, ImportError) as exc:
        print(f"DayWeave: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
