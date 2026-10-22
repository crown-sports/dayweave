"""Typed planning inputs, explicit time interpretation, and bounded user data."""

from __future__ import annotations

import json
import math
import re
from dataclasses import dataclass, replace
from datetime import UTC, datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError


class InputError(ValueError):
    """Report an actionable input problem without exposing internal failures."""


def strict_json(data: str | bytes) -> Any:
    """Reject duplicate object keys and nonfinite numbers before interpreting a plan."""

    def pairs(items: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in items:
            if key in result:
                raise InputError(f"Duplicate JSON key: {key}")
            result[key] = value
        return result

    def number(value: str) -> float:
        result = float(value)
        if not math.isfinite(result):
            raise InputError("Numbers must be finite")
        return result

    try:
        result = json.loads(data, object_pairs_hook=pairs, parse_float=number, parse_constant=number)
        pending = [result]
        while pending:
            item = pending.pop()
            if isinstance(item, str):
                item.encode("utf-8")
            elif isinstance(item, dict):
                pending.extend(item.keys())
                pending.extend(item.values())
            elif isinstance(item, list):
                pending.extend(item)
        return result
    except InputError:
        raise
    except (ValueError, RecursionError) as exc:
        raise InputError("Expected valid UTF-8 JSON") from exc


def text(value: Any, label: str, limit: int = 200) -> str:
    """Require bounded nonempty human text without allowing control characters."""
    if not isinstance(value, str) or not value.strip() or len(value) > limit:
        raise InputError(f"{label} must be nonempty text of at most {limit} characters")
    if any(ord(char) < 32 for char in value):
        raise InputError(f"{label} cannot contain control characters")
    return value.strip()


def integer(value: Any, label: str, lower: int, upper: int) -> int:
    """Keep integer-minute constraints distinct from booleans and floating-point guesses."""
    if isinstance(value, bool) or not isinstance(value, int) or not lower <= value <= upper:
        raise InputError(f"{label} must be an integer between {lower} and {upper}")
    return int(value)


def identifier(value: Any) -> str:
    result = text(value, "Identifier", 64)
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]*", result):
        raise InputError("Identifiers accept letters, digits, underscores, and hyphens")
    return result


def local_time(value: Any, zone: ZoneInfo) -> datetime:
    """Resolve minute-precision ISO times; require an offset for ambiguous daylight-saving times."""
    raw = text(value, "Date/time", 60)
    try:
        parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError as exc:
        raise InputError("Use a full ISO date and time, for example 2026-10-05T09:00") from exc
    if "T" not in raw and " " not in raw:
        raise InputError("A date alone needs an explicit time")
    if parsed.second or parsed.microsecond:
        raise InputError("Planning times use whole minutes")
    if parsed.tzinfo is None:
        first, second = parsed.replace(tzinfo=zone, fold=0), parsed.replace(tzinfo=zone, fold=1)
        if first.astimezone(UTC).astimezone(zone).replace(tzinfo=None) != parsed:
            raise InputError("This local time does not exist at the daylight-saving transition")
        if first.utcoffset() != second.utcoffset():
            raise InputError("This local time is ambiguous; provide an explicit UTC offset")
        parsed = first
    return parsed.astimezone(UTC)


def merge_intervals(items: list[tuple[int, int]]) -> list[tuple[int, int]]:
    """Union occupied or available intervals without counting overlap twice."""
    result: list[tuple[int, int]] = []
    for left, right in sorted(items):
        if right <= left:
            continue
        if result and left <= result[-1][1]:
            result[-1] = (result[-1][0], max(result[-1][1], right))
        else:
            result.append((left, right))
    return result


@dataclass(frozen=True)
class Task:
    id: str
    title: str
    duration: int
    release: int
    deadline: int
    priority: int
    required: bool
    chunk: int
    after: tuple[str, ...]
    locked: tuple[int, ...]

    @property
    def parts(self) -> tuple[int, ...]:
        """Split only at the user's explicit chunk size, preserving the full requested effort."""
        return tuple(min(self.chunk, self.duration - offset) for offset in range(0, self.duration, self.chunk))


@dataclass(frozen=True)
class Appointment:
    id: str
    title: str
    start: int
    end: int


@dataclass(frozen=True)
class PriorSlot:
    task: str
    part: int
    start: int
    duration: int


@dataclass(frozen=True)
class PlanningInput:
    zone: ZoneInfo
    origin: datetime
    horizon: int
    not_before: int
    available: tuple[tuple[int, int], ...]
    tasks: tuple[Task, ...]
    appointments: tuple[Appointment, ...]
    previous: tuple[PriorSlot, ...]

    def minute(self, value: Any) -> int:
        """Use elapsed UTC minutes internally so timezone changes do not alter interval lengths."""
        return int((local_time(value, self.zone) - self.origin).total_seconds() // 60)

    def iso(self, minute: int) -> str:
        return (self.origin + timedelta(minutes=minute)).astimezone(self.zone).isoformat(timespec="minutes")

    @classmethod
    def from_dict(cls, value: Any) -> PlanningInput:
        """Validate complete editable plans before any scheduling or model work occurs."""
        if not isinstance(value, dict):
            raise InputError("The plan must be an object")
        try:
            zone = ZoneInfo(text(value.get("timezone", "Asia/Shanghai"), "Timezone", 100))
        except (ZoneInfoNotFoundError, ValueError) as exc:
            raise InputError("Unknown IANA timezone") from exc
        origin = local_time(value.get("start"), zone)
        end = local_time(value.get("end"), zone)
        horizon = int((end - origin).total_seconds() // 60)
        if not 1 <= horizon <= 28 * 1440:
            raise InputError("The planning horizon must be positive and at most 28 days")
        empty = cls(zone, origin, horizon, 0, (), (), (), ())
        not_before = empty.minute(value.get("not_before", value["start"]))
        if not 0 <= not_before <= horizon:
            raise InputError("Earliest planning time must lie inside the horizon")
        windows = value.get("available", [])
        if not isinstance(windows, list) or len(windows) > 100:
            raise InputError("At most 100 available windows are supported")
        available = []
        for window in windows:
            if not isinstance(window, dict):
                raise InputError("An available window needs start/end times")
            left, right = empty.minute(window.get("start")), empty.minute(window.get("end"))
            if not 0 <= left < right <= horizon:
                raise InputError("Available windows must lie inside the planning horizon")
            available.append((max(left, not_before), right))
        raw_tasks, raw_events, raw_previous = (
            value.get("tasks", []),
            value.get("appointments", []),
            value.get("previous", []),
        )
        if not isinstance(raw_tasks, list) or len(raw_tasks) > 60:
            raise InputError("At most 60 tasks are supported")
        if not isinstance(raw_events, list) or len(raw_events) > 200:
            raise InputError("At most 200 appointments are supported")
        if not isinstance(raw_previous, list) or len(raw_previous) > 300:
            raise InputError("At most 300 previous task segments are supported")
        tasks = []
        progress: dict[str, int] = {}
        for raw in raw_tasks:
            if not isinstance(raw, dict):
                raise InputError("A task must be an object")
            duration = integer(raw.get("duration"), "Task duration", 1, 1440)
            completed = integer(raw.get("completed_minutes", 0), "Completed minutes", 0, duration)
            remaining = duration - completed
            chunk = integer(raw.get("chunk", duration), "Segment duration", 1, duration)
            if math.ceil(duration / chunk) > 12:
                raise InputError("A task may have at most twelve segments")
            release = empty.minute(raw.get("release", value["start"]))
            deadline = empty.minute(raw.get("deadline", value["end"]))
            if not 0 <= release <= horizon or not 0 <= deadline <= horizon:
                raise InputError("Task release and deadline times must lie inside the horizon")
            required = raw.get("required", True)
            if not isinstance(required, bool):
                raise InputError("Required must be true or false")
            after, locked = raw.get("after", []), raw.get("locked", [])
            if not isinstance(after, list) or len(after) > 20 or not isinstance(locked, list):
                raise InputError("Dependencies and locked starts must be bounded lists")
            if locked and (not required or not remaining or len(locked) != math.ceil(remaining / chunk)):
                raise InputError("A locked task must be required and pin every segment")
            progress[identifier(raw.get("id"))] = completed
            tasks.append(
                Task(
                    identifier(raw.get("id")),
                    text(raw.get("title"), "Task title"),
                    duration,
                    max(release, not_before),
                    deadline,
                    integer(raw.get("priority", 3), "Priority", 1, 5),
                    required,
                    chunk,
                    tuple(identifier(item) for item in after),
                    tuple(empty.minute(item) for item in locked),
                )
            )
        ids = {task.id for task in tasks}
        if len(ids) != len(tasks) or sum(len(task.parts) for task in tasks) > 300:
            raise InputError("Task identifiers must be unique; at most 300 segments are supported")
        graph = {task.id: set(task.after) for task in tasks}
        for task in tasks:
            if any(item not in ids or item == task.id for item in task.after):
                raise InputError("Dependencies must refer to other tasks in this plan")
        resolved: set[str] = set()
        while len(resolved) < len(tasks):
            ready = {key for key, parents in graph.items() if key not in resolved and parents <= resolved}
            if not ready:
                raise InputError("Task dependencies contain a cycle")
            resolved.update(ready)
        events = []
        for raw in raw_events:
            if not isinstance(raw, dict):
                raise InputError("An appointment must be an object")
            left, right = empty.minute(raw.get("start")), empty.minute(raw.get("end"))
            if right <= left:
                raise InputError("An appointment must finish after it starts")
            if left < horizon and right > not_before:
                events.append(
                    Appointment(
                        identifier(raw.get("id")),
                        text(raw.get("title"), "Appointment title"),
                        max(not_before, left),
                        min(horizon, right),
                    )
                )
        if len({event.id for event in events}) != len(events):
            raise InputError("Appointment identifiers must be unique")
        previous = []
        seen: set[tuple[str, int]] = set()
        for raw in raw_previous:
            if not isinstance(raw, dict):
                raise InputError("Previous segments must be objects")
            task_id = identifier(raw.get("task"))
            part = integer(raw.get("part"), "Segment number", 0, 11)
            if (task_id, part) in seen:
                raise InputError("Previous segments cannot repeat a task/part pair")
            seen.add((task_id, part))
            start = empty.minute(raw.get("start"))
            if not -28 * 1440 <= start <= 56 * 1440:
                raise InputError("Previous start is too far from this horizon")
            previous.append(PriorSlot(task_id, part, start, integer(raw.get("duration"), "Previous duration", 1, 1440)))
        completed_ids = {task.id for task in tasks if progress[task.id] == task.duration}
        tasks = [
            replace(
                task,
                duration=task.duration - progress[task.id],
                chunk=min(task.chunk, task.duration - progress[task.id]),
                after=tuple(parent for parent in task.after if parent not in completed_ids),
            )
            for task in tasks
            if task.id not in completed_ids
        ]
        # Progress may change segment shapes. Preserve valid remaining plans, but do not
        # optimize against obsolete segments or completed work as if it still existed.
        parts = {task.id: task.parts for task in tasks}
        stale = set(completed_ids)
        for task_id, minutes in progress.items():
            if not minutes or task_id not in parts:
                continue
            old = sorted((slot for slot in previous if slot.task == task_id), key=lambda slot: slot.part)
            if [slot.part for slot in old] != list(range(len(parts[task_id]))) or tuple(
                slot.duration for slot in old
            ) != parts[task_id]:
                stale.add(task_id)
        previous = [slot for slot in previous if slot.task not in stale]
        return cls(
            zone,
            origin,
            horizon,
            not_before,
            tuple(merge_intervals(available)),
            tuple(tasks),
            tuple(events),
            tuple(previous),
        )
