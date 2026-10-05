"""Behavioral scheduling tests, including an independent exhaustive small-instance oracle."""

import itertools
import random

import pytest

from dayweave.contracts import InputError, PlanningInput, strict_json
from dayweave.scheduler import schedule
from dayweave.validation import movement, validate_schedule


def tiny(tasks, horizon=10, appointments=None, previous=None):
    origin = "2026-10-05T09:00"
    end = f"2026-10-05T09:{horizon:02d}"
    return PlanningInput.from_dict(
        {
            "start": origin,
            "end": end,
            "available": [{"start": origin, "end": end}],
            "tasks": tasks,
            "appointments": appointments or [],
            "previous": previous or [],
        }
    )


def exhaustive(plan):
    choices = []
    for task in plan.tasks:
        candidates = []
        for positions in itertools.product(range(plan.horizon), repeat=len(task.parts)):
            candidates.append(
                [
                    {"task": task.id, "part": part, "minute": start, "duration": duration}
                    for part, (start, duration) in enumerate(zip(positions, task.parts, strict=True))
                ]
            )
        if not task.required:
            candidates.append([])
        choices.append(candidates)
    valid = []
    for combination in itertools.product(*choices):
        slots = [slot for group in combination for slot in group]
        if not validate_schedule(plan, slots):
            valid.append(slots)
    return valid


def test_solver_matches_exhaustive_feasibility_without_solver_oracle():
    rng = random.Random(7031)
    for case in range(36):
        tasks = []
        for index in range(3):
            tasks.append(
                {
                    "id": f"t{index}",
                    "title": f"事 {case}/{index}",
                    "duration": rng.randint(1, 4),
                    "release": f"2026-10-05T09:0{rng.randint(0, 3)}",
                    "deadline": f"2026-10-05T09:0{rng.randint(5, 9)}",
                    "after": [f"t{index - 1}"] if index and rng.random() < 0.25 else [],
                }
            )
        plan = tiny(tasks)
        oracle = exhaustive(plan)
        result = schedule(plan, seconds=1)
        assert (result["state"] == "scheduled") == bool(oracle)
        if oracle:
            assert result["validated"] and not validate_schedule(plan, result["slots"])
        else:
            assert result["state"] == "conflict"


def test_replanning_minimizes_changed_tasks_against_exhaustive_oracle():
    tasks = [{"id": f"t{x}", "title": str(x), "duration": 2} for x in range(3)]
    previous = [{"task": f"t{x}", "part": 0, "start": f"2026-10-05T09:0{x * 2}", "duration": 2} for x in range(3)]
    event = {"id": "call", "title": "临时电话", "start": "2026-10-05T09:02", "end": "2026-10-05T09:04"}
    plan = tiny(tasks, appointments=[event], previous=previous)
    result = schedule(plan, seconds=2)
    oracle = exhaustive(plan)
    minimum = min(movement(plan, slots)["changed_count"] for slots in oracle)
    assert result["optimal"] and minimum == 1 and result["movement"]["changed_count"] == minimum


def test_release_time_makes_earliest_deadline_insertion_fail_but_solver_fits():
    plan = tiny(
        [
            {
                "id": "phone",
                "title": "预约电话",
                "duration": 2,
                "release": "2026-10-05T09:04",
                "deadline": "2026-10-05T09:08",
            },
            {"id": "study", "title": "连续复习", "duration": 6},
        ]
    )
    result = schedule(plan)
    assert result["state"] == "scheduled"
    assert {slot["task"]: slot["minute"] for slot in result["slots"]} == {"study": 0, "phone": 6}


def test_conflict_core_is_independently_infeasible_and_each_deletion_feasible():
    plan = tiny([{"id": f"t{x}", "title": str(x), "duration": 4} for x in range(3)])
    result = schedule(plan)
    assert result["conflict"]["subset_minimal"]
    core_ids = {item["id"] for item in result["conflict"]["items"]}
    assert len(core_ids) == 3
    assert not exhaustive(plan)
    for removed in core_ids:
        changed = tiny([{"id": t.id, "title": t.title, "duration": t.duration} for t in plan.tasks if t.id != removed])
        assert exhaustive(changed)
    assert result["capacity"]["shortfall_minutes"] == 2
    assert result["alternative"]["validated"] and len(result["alternative"]["postponed"]) == 1


def test_split_resolves_fragmentation_without_reducing_work():
    base = {
        "start": "2026-10-05T09:00",
        "end": "2026-10-05T12:00",
        "available": [
            {"start": "2026-10-05T09:00", "end": "2026-10-05T10:00"},
            {"start": "2026-10-05T11:00", "end": "2026-10-05T12:00"},
        ],
        "tasks": [{"id": "essay", "title": "写文章", "duration": 120}],
    }
    assert schedule(PlanningInput.from_dict(base))["state"] == "conflict"
    base["tasks"][0]["chunk"] = 60
    plan = PlanningInput.from_dict(base)
    result = schedule(plan)
    assert result["state"] == "scheduled" and sum(x["duration"] for x in result["slots"]) == 120


def test_pins_are_kept_and_conflicting_appointments_not_silently_moved():
    plan = tiny(
        [{"id": "t", "title": "固定复习", "duration": 2, "locked": ["2026-10-05T09:00"]}],
        appointments=[{"id": "a", "title": "不可改的预约", "start": "2026-10-05T09:01", "end": "2026-10-05T09:03"}],
    )
    result = schedule(plan)
    assert result["state"] == "conflict" and result["alternative"]["state"] == "infeasible"
    assert {x["kind"] for x in result["conflict"]["items"]} == {"locked_task", "appointment"}


def test_optional_dependency_must_be_included_before_required_child():
    plan = tiny(
        [
            {"id": "a", "title": "先准备", "duration": 3, "required": False},
            {"id": "b", "title": "再提交", "duration": 3, "after": ["a"]},
        ]
    )
    result = schedule(plan)
    assert {x["task"] for x in result["slots"]} == {"a", "b"}
    assert result["slots"][0]["task"] == "a"


@pytest.mark.parametrize(
    "data", ['{"a":1,"a":2}', '{"a":NaN}', '{"a":1e999}', '{"a":"\\ud800"}', '{"a":' + "9" * 5000 + "}"]
)
def test_strict_json_rejects_ambiguous_numbers_and_keys(data):
    with pytest.raises(InputError):
        strict_json(data)


def test_timezone_dst_elapsed_minutes_and_ambiguous_time_refusal():
    plan = PlanningInput.from_dict(
        {
            "timezone": "America/New_York",
            "start": "2026-11-01T00:00-04:00",
            "end": "2026-11-01T04:00-05:00",
            "tasks": [],
        }
    )
    assert plan.horizon == 300
    with pytest.raises(InputError, match="ambiguous"):
        PlanningInput.from_dict(
            {"timezone": "America/New_York", "start": "2026-11-01T01:30", "end": "2026-11-01T04:00", "tasks": []}
        )


def test_checker_catches_deadline_overlap_missing_effort_and_invalid_pins():
    plan = tiny(
        [
            {"id": "a", "title": "写作", "duration": 2, "locked": ["2026-10-05T09:00"]},
            {"id": "b", "title": "读书", "duration": 2, "after": ["a"]},
        ]
    )
    errors = validate_schedule(
        plan,
        [{"task": "a", "part": -99, "minute": 0, "duration": 2}, {"task": "b", "part": 0, "minute": 1, "duration": 2}],
    )
    assert any("Overlap" in item for item in errors) and any("locked" in item for item in errors)


def test_dependency_cycle_and_boolean_duration_rejected():
    with pytest.raises(InputError):
        tiny([{"id": "a", "title": "a", "duration": True}])
    with pytest.raises(InputError, match="cycle"):
        tiny(
            [
                {"id": "a", "title": "a", "duration": 2, "after": ["b"]},
                {"id": "b", "title": "b", "duration": 2, "after": ["a"]},
            ]
        )


def test_future_plan_ignores_past_overlaps_and_keeps_remaining_ongoing_appointment():
    plan = PlanningInput.from_dict(
        {
            "start": "2026-10-05T09:00",
            "end": "2026-10-05T12:00",
            "not_before": "2026-10-05T10:00",
            "available": [{"start": "2026-10-05T09:00", "end": "2026-10-05T12:00"}],
            "tasks": [{"id": "t", "title": "Future task", "duration": 30}],
            "appointments": [
                {"id": "past1", "title": "Past one", "start": "2026-10-05T09:00", "end": "2026-10-05T09:45"},
                {"id": "past2", "title": "Past two", "start": "2026-10-05T09:30", "end": "2026-10-05T10:00"},
                {"id": "ongoing", "title": "Ongoing", "start": "2026-10-05T09:45", "end": "2026-10-05T10:30"},
            ],
        }
    )
    result = schedule(plan)
    assert result["state"] == "scheduled" and result["slots"][0]["minute"] == 90
    assert len(result["appointments"]) == 1 and result["appointments"][0]["start"] == "2026-10-05T10:00+08:00"
