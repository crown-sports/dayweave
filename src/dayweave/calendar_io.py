"""Local calendar import and independently checked iCalendar export."""

from __future__ import annotations

import hashlib
import math
from datetime import UTC, date, datetime, time, timedelta
from typing import Any

import recurring_ical_events
from icalendar import Calendar, Event

from .contracts import InputError, PlanningInput, local_time
from .validation import validate_schedule


def calendar_time(value: Any, plan: PlanningInput) -> datetime:
    """Interpret floating calendar times in the explicitly selected planning timezone."""
    if isinstance(value, datetime):
        if value.tzinfo is None:
            minute = local_time(value.replace(second=0, microsecond=0).isoformat(timespec="minutes"), plan.zone)
            return minute + timedelta(seconds=value.second, microseconds=value.microsecond)
        return value
    if isinstance(value, date):
        return datetime.combine(value, time.min, plan.zone)
    raise InputError("Calendar events need valid dates or times")


def import_calendar(data: str, plan: PlanningInput) -> dict[str, Any]:
    """Expand bounded daily-or-slower recurrences, exclusions, overrides, and all-day occupied events."""
    if not isinstance(data, str) or len(data.encode()) > 1048576:
        raise InputError("Calendar files must be at most 1 MiB")
    try:
        calendar = Calendar.from_ical(data)
        events = calendar.walk("VEVENT")
        if len(events) > 500:
            raise InputError("Calendar files may contain at most 500 event definitions")
        for event in events:
            if event.errors:
                raise InputError("Calendar contains invalid event properties")
            rule = event.get("RRULE")
            if rule and str(rule.get("FREQ", [""])[0]).upper() not in {"DAILY", "WEEKLY", "MONTHLY", "YEARLY"}:
                raise InputError("Only daily, weekly, monthly, and yearly recurrences are supported")
            recurrence = event.get("RECURRENCE-ID")
            if recurrence and recurrence.params.get("RANGE"):
                raise InputError("THISANDFUTURE recurrence edits need a flattened calendar export")
        expanded = recurring_ical_events.of(calendar, keep_recurrence_attributes=True).between(
            plan.origin, plan.origin + timedelta(minutes=plan.horizon)
        )
        if len(expanded) > 200:
            raise InputError("This horizon contains more than 200 calendar occurrences")
        result = []
        warnings = []
        seen: set[str] = set()
        for event in expanded:
            if str(event.get("STATUS", "")).upper() == "CANCELLED":
                continue
            if str(event.get("TRANSP", "")).upper() == "TRANSPARENT":
                continue
            start = calendar_time(event.decoded("DTSTART"), plan).astimezone(UTC)
            if "DTEND" in event:
                end = calendar_time(event.decoded("DTEND"), plan).astimezone(UTC)
            elif "DURATION" in event:
                end = start + event.decoded("DURATION")
            elif isinstance(event.decoded("DTSTART"), date) and not isinstance(event.decoded("DTSTART"), datetime):
                next_day = event.decoded("DTSTART") + timedelta(days=1)
                end = calendar_time(next_day, plan).astimezone(UTC)
            else:
                raise InputError("A timed calendar event is missing its end or duration")
            left = max(0, math.floor((start - plan.origin).total_seconds() / 60))
            right = min(plan.horizon, math.ceil((end - plan.origin).total_seconds() / 60))
            if right <= left:
                continue
            uid = str(event.get("UID", ""))
            identity = hashlib.sha256(f"{uid}\0{start.isoformat()}".encode()).hexdigest()[:20]
            if identity in seen:
                raise InputError("Calendar contains duplicate occurrence identities")
            seen.add(identity)
            title = str(event.get("SUMMARY", "已有安排"))[:200].replace("\n", " ").replace("\r", " ")
            result.append(
                {"id": "cal_" + identity, "title": title or "已有安排", "start": plan.iso(left), "end": plan.iso(right)}
            )
            if start.second or end.second:
                warnings.append("Some busy intervals were rounded outward to whole minutes")
        return {"appointments": sorted(result, key=lambda item: item["start"]), "warnings": sorted(set(warnings))}
    except InputError:
        raise
    except (ValueError, TypeError, KeyError, AttributeError) as exc:
        raise InputError("Could not interpret this calendar; use a valid .ics export") from exc


def export_calendar(plan: PlanningInput, slots: list[dict[str, Any]]) -> bytes:
    """Export only a fully validated plan; original appointments are not duplicated into the new calendar."""
    errors = validate_schedule(plan, slots)
    if errors:
        raise InputError("Cannot export an invalid or incomplete required schedule: " + "; ".join(errors))
    calendar = Calendar()
    calendar.add("PRODID", "-//DayWeave//Reviewed personal plan//EN")
    calendar.add("VERSION", "2.0")
    calendar.add("X-WR-CALNAME", "DayWeave")
    calendar.add("X-WR-TIMEZONE", plan.zone.key)
    for slot in slots:
        event = Event()
        identity = hashlib.sha256(f"{plan.origin.isoformat()}/{slot['task']}/{slot['part']}".encode()).hexdigest()[:32]
        event.add("UID", identity + "@dayweave.local")
        event.add("DTSTAMP", datetime.now(UTC))
        event.add("DTSTART", plan.origin + timedelta(minutes=slot["minute"]))
        event.add("DTEND", plan.origin + timedelta(minutes=slot["minute"] + slot["duration"]))
        task = next(item for item in plan.tasks if item.id == slot["task"])
        event.add("SUMMARY", task.title)
        event.add("DESCRIPTION", "Reviewed DayWeave task block. Duration is the user's estimate.")
        calendar.add_component(event)
    return bytes(calendar.to_ical())
