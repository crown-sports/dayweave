"""Exercise ordinary-user workflows through the same API used by the browser."""

from fastapi.testclient import TestClient

from dayweave.web import create_app


def client():
    connection = TestClient(create_app(), base_url="http://127.0.0.1")
    session = connection.get("/api/session").json()
    connection.headers.update({"Origin": "http://127.0.0.1", "X-DayWeave-Token": session["token"]})
    return connection


def test_browser_api_complete_plan_replan_and_calendar_download():
    with client() as browser:
        request = browser.get("/api/example/balanced?day=2026-10-05").json()
        response = browser.post("/api/solve", json=request)
        assert response.status_code == 200, response.text
        initial = response.json()
        assert initial["state"] == "scheduled" and initial["validated"]
        request["previous"] = [{k: slot[k] for k in ("task", "part", "start", "duration")} for slot in initial["slots"]]
        slot = initial["slots"][0]
        request["appointments"].append(
            {"id": "urgent", "title": "临时预约", "start": slot["start"], "end": slot["end"]}
        )
        revised = browser.post("/api/solve", json=request).json()
        assert revised["state"] == "scheduled" and revised["movement"]["changed_count"] >= 1
        response = browser.post("/api/export", json={"plan": request, "slots": revised["slots"]})
        assert response.status_code == 200 and b"BEGIN:VEVENT" in response.content
        link = response.headers["X-DayWeave-Download"]
        downloaded = browser.get(link)
        assert downloaded.status_code == 200 and downloaded.content == response.content
        assert downloaded.headers["Content-Disposition"] == "attachment; filename=dayweave.ics"
        assert browser.post("/api/export", json={"plan": request, "slots": []}).status_code == 400


def test_overload_requires_explicit_postponement_choice():
    with client() as browser:
        request = browser.get("/api/example/overload?day=2026-10-05").json()
        response = browser.post("/api/solve", json=request).json()
        assert response["state"] == "conflict" and response["capacity"]["shortfall_minutes"] == 60
        alternative = response["alternative"]
        assert browser.post("/api/export", json={"plan": request, "slots": alternative["slots"]}).status_code == 400
        allowed = {item["id"] for item in alternative["postponed"]}
        for task in request["tasks"]:
            if task["id"] in allowed:
                task["required"] = False
        decided = browser.post("/api/solve", json=request).json()
        assert decided["state"] == "scheduled" and decided["postponed"]
        assert browser.post("/api/export", json={"plan": request, "slots": decided["slots"]}).status_code == 200


def test_capture_and_local_request_guards():
    with client() as browser:
        response = browser.post(
            "/api/capture", json={"text": "准备面试 | 90分钟 | 周三18:00前", "anchor": "2026-10-05T09:00"}
        )
        assert response.status_code == 200 and response.json()["items"][0]["duration"] == 90
        assert browser.post("/api/solve", json={}, headers={"Origin": "https://foreign.example"}).status_code == 403
        assert browser.post("/api/solve", json={}, headers={"X-DayWeave-Token": "wrong"}).status_code == 403
        assert browser.get("/", headers={"Host": "foreign.example"}).status_code == 403
        assert (
            browser.post(
                "/api/solve", content='{"tasks":[],"tasks":[]}', headers={"Content-Type": "application/json"}
            ).status_code
            == 400
        )
        assert browser.get("/assets/../pyproject.toml").status_code == 404
        assert browser.get("/").status_code == 200


def test_project_backup_supports_unfinished_drafts_and_download_requires_its_session():
    app = create_app()
    with TestClient(app, base_url="http://127.0.0.1") as browser:
        token = browser.get("/api/session").json()["token"]
        headers = {"Origin": "http://127.0.0.1", "X-DayWeave-Token": token}
        project = {"tasks": [{"id": "draft", "title": "尚待估计的事项", "duration": None}]}
        response = browser.post("/api/backup", json={"project": project}, headers=headers)
        assert response.status_code == 200 and response.json() == project
        link = response.headers["X-DayWeave-Download"]
        assert browser.get(link).json() == project
        browser.cookies.clear()
        assert browser.get(link).status_code == 403
