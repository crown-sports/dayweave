"""Partial work reduces future effort without assuming that elapsed slots were completed."""

import copy
import json
import shutil
import subprocess
from pathlib import Path

import pytest
from icalendar import Calendar
from test_web import client

from dayweave.calendar_io import export_calendar
from dayweave.contracts import InputError, PlanningInput
from dayweave.scheduler import schedule
from dayweave.validation import validate_schedule


def project():
    return {
        "timezone": "UTC",
        "start": "2026-10-22T09:00",
        "end": "2026-10-22T12:00",
        "available": [{"start": "2026-10-22T10:00", "end": "2026-10-22T11:30"}],
        "not_before": "2026-10-22T10:00",
        "appointments": [],
        "previous": [],
        "tasks": [
            {"id": "draft", "title": "Draft", "duration": 90, "chunk": 60, "completed_minutes": 30},
            {"id": "review", "title": "Review", "duration": 30, "after": ["draft"]},
        ],
    }


def test_only_remaining_work_scheduled_validated_and_exported():
    raw = project()
    original = copy.deepcopy(raw)
    plan = PlanningInput.from_dict(raw)
    result = schedule(plan)
    assert result["state"] == "scheduled" and result["validated"]
    assert sum(slot["duration"] for slot in result["slots"]) == 90
    assert [task.duration for task in plan.tasks] == [60, 30]
    assert not validate_schedule(plan, result["slots"])
    assert raw == original
    events = Calendar.from_ical(export_calendar(plan, result["slots"])).walk("VEVENT")
    assert sum((event.decoded("DTEND") - event.decoded("DTSTART")).total_seconds() / 60 for event in events) == 90
    raw["tasks"][0]["completed_minutes"] = 0
    assert schedule(PlanningInput.from_dict(raw))["state"] == "conflict"


def test_completed_prerequisite_satisfied_and_no_elapsed_time_auto_completion():
    raw = project()
    raw["tasks"][0]["completed_minutes"] = 90
    plan = PlanningInput.from_dict(raw)
    assert len(plan.tasks) == 1 and plan.tasks[0].after == ()
    assert sum(slot["duration"] for slot in schedule(plan)["slots"]) == 30
    raw["tasks"][1]["completed_minutes"] = 30
    result = schedule(PlanningInput.from_dict(raw))
    assert result["state"] == "scheduled" and result["slots"] == []


@pytest.mark.parametrize("value", [-1, 91, True, 1.5, "30"])
def test_progress_must_be_bounded_integer(value):
    raw = project()
    raw["tasks"][0]["completed_minutes"] = value
    with pytest.raises(InputError, match="Completed minutes"):
        PlanningInput.from_dict(raw)


def test_stale_previous_shapes_cleared_but_remaining_plan_is_preserved():
    raw = project()
    raw["previous"] = [
        {"task": "draft", "part": 0, "start": "2026-10-22T09:00", "duration": 60},
        {"task": "draft", "part": 1, "start": "2026-10-22T10:00", "duration": 30},
    ]
    plan = PlanningInput.from_dict(raw)
    assert plan.previous == ()
    result = schedule(plan)
    raw["previous"] = [{key: slot[key] for key in ("task", "part", "start", "duration")} for slot in result["slots"]]
    again = PlanningInput.from_dict(raw)
    assert len(again.previous) == 2
    assert schedule(again)["movement"]["changed_count"] == 0


def test_locks_apply_to_remaining_segments_and_obsolete_pins_fail():
    raw = project()
    raw["tasks"][0]["locked"] = ["2026-10-22T10:00"]
    assert schedule(PlanningInput.from_dict(raw))["state"] == "scheduled"
    raw["tasks"][0]["locked"].append("2026-10-22T11:00")
    with pytest.raises(InputError, match="pin every segment"):
        PlanningInput.from_dict(raw)


def test_progress_flows_through_browser_api_and_export():
    with client() as browser:
        result = browser.post("/api/solve", json=project()).json()
        assert result["state"] == "scheduled"
        assert sum(slot["duration"] for slot in result["slots"]) == 90
        response = browser.post("/api/export", json={"plan": project(), "slots": result["slots"]})
        assert response.status_code == 200


def test_browser_project_backup_roundtrip_and_input_preserve_progress(tmp_path):
    if not shutil.which("node"):
        pytest.skip("Node is needed for the browser state module contract")
    ui = Path(__file__).resolve().parents[1] / "src/dayweave/ui"
    shutil.copytree(ui, tmp_path / "ui")
    (tmp_path / "package.json").write_text('{"type":"module"}')
    path = tmp_path / "ui/project_state.js"
    script = f"""import assert from "node:assert/strict";
import {{restoreProject, buildPlanInput}} from {json.dumps(path.as_uri())};
const raw = {json.dumps(project())}; raw.example = true;
const restored = restoreProject(raw);
assert.equal(restored.tasks[0].completed_minutes, 30);
assert.equal(buildPlanInput(restored).tasks[0].completed_minutes, 30);
assert.throws(() => restoreProject({{...raw, tasks:[{{...raw.tasks[0], completed_minutes:91}}]}}));
raw.tasks[0].completed_minutes = 90;
const done = restoreProject(raw);
assert.equal(done.tasks[0].done, true);
assert.deepEqual(buildPlanInput(done).tasks[0].after, []);
const draft = {{...raw, tasks:[{{id:"draft",title:"Unestimated",duration:null}}]}};
const restoredDraft = restoreProject(restoreProject(draft));
assert.equal(restoredDraft.tasks[0].duration, null);
assert.equal(restoredDraft.tasks[0].completed_minutes, 0);
assert.throws(() => restoreProject({{...draft, tasks:[{{...draft.tasks[0], completed_minutes:1}}]}}));
"""
    subprocess.run(
        ["node", "--input-type=module", "-e", script],
        check=True,
        capture_output=True,
    )
