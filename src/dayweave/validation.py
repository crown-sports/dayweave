"""Independent schedule checking using ordinary interval arithmetic, not solver objects."""

from __future__ import annotations

from collections import defaultdict
from typing import Any

from .contracts import PlanningInput


def validate_schedule(plan: PlanningInput, slots: list[dict[str, Any]], allow_postponed: bool = False) -> list[str]:
    """Check effort, availability, appointments, deadlines, order, prerequisites, and pins independently."""
    errors = []
    indexed: dict[str, list[tuple[int, int, int]]] = defaultdict(list)
    tasks = {task.id: task for task in plan.tasks}
    occupied = [(event.start, event.end, f"appointment/{event.id}") for event in plan.appointments]
    for slot in slots:
        raw_task = slot.get("task")
        task = tasks.get(raw_task) if isinstance(raw_task, str) else None
        if task is None:
            errors.append("Unknown scheduled task")
            continue
        start, duration, part = slot.get("minute"), slot.get("duration"), slot.get("part")
        if (
            not isinstance(start, int)
            or isinstance(start, bool)
            or not isinstance(duration, int)
            or isinstance(duration, bool)
            or not isinstance(part, int)
            or isinstance(part, bool)
        ):
            errors.append(f"{task.id}: non-integer segment")
            continue
        end = start + duration
        if part < 0 or part >= len(task.parts) or duration != task.parts[part]:
            errors.append(f"{task.id}: wrong segment duration or index")
        if not any(left <= start and end <= right for left, right in plan.available):
            errors.append(f"{task.id}: outside available hours")
        if start < task.release or end > task.deadline:
            errors.append(f"{task.id}: outside release/deadline bounds")
        if task.locked and (not 0 <= part < len(task.locked) or start != task.locked[part]):
            errors.append(f"{task.id}: moved a locked segment")
        indexed[task.id].append((part, start, end))
        occupied.append((start, end, task.id))
    for task in plan.tasks:
        parts = sorted(indexed[task.id])
        if not parts:
            if (task.required and not allow_postponed) or task.locked:
                errors.append(f"{task.id}: missing required task")
            continue
        if [item[0] for item in parts] != list(range(len(task.parts))):
            errors.append(f"{task.id}: partial or repeated task segments")
        if any(left[2] > right[1] for left, right in zip(parts, parts[1:], strict=False)):
            errors.append(f"{task.id}: segments out of order")
        for parent in task.after:
            if not indexed[parent]:
                errors.append(f"{task.id}: missing prerequisite {parent}")
            elif max(item[2] for item in indexed[parent]) > min(item[1] for item in parts):
                errors.append(f"{task.id}: prerequisite {parent} finishes too late")
    active_end = -(10**9)
    active_id = ""
    for start, end, name in sorted(occupied):
        if start < active_end:
            errors.append(f"Overlap: {active_id} / {name}")
        if end > active_end:
            active_end, active_id = end, name
    return errors


def movement(plan: PlanningInput, slots: list[dict[str, Any]]) -> dict[str, Any]:
    """Measure changed existing tasks separately from newly added or explicitly removed work."""
    previous: dict[str, list[tuple[int, int, int]]] = defaultdict(list)
    current: dict[str, list[tuple[int, int, int]]] = defaultdict(list)
    for item in plan.previous:
        previous[item.task].append((item.part, item.start, item.duration))
    for slot in slots:
        current[slot["task"]].append((slot["part"], slot["minute"], slot["duration"]))
    task_ids = {task.id for task in plan.tasks}
    changed = []
    displacement = 0
    for key in previous.keys() & task_ids:
        old, new = sorted(previous[key]), sorted(current[key])
        if old != new:
            changed.append(key)
        for left, right in zip(old, new, strict=False):
            displacement += abs(left[1] - right[1])
    return {
        "changed_tasks": sorted(changed),
        "changed_count": len(changed),
        "displacement_minutes": displacement,
        "added_tasks": sorted(current.keys() - previous.keys()),
        "removed_tasks": sorted(previous.keys() - task_ids),
    }
