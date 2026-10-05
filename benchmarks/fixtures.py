"""Seeded synthetic schedules with hidden construction witnesses and explicit suite labels."""

from __future__ import annotations

import random
from datetime import datetime, timedelta
from typing import Any

SEED = 20261005
ORIGIN = datetime(2026, 10, 5, 9)


def stamp(minute: int) -> str:
    return (ORIGIN + timedelta(minutes=minute)).isoformat(timespec="minutes")


def tiny_cases(count: int = 96) -> list[dict[str, Any]]:
    """Generate small cases whose complete search space is independently enumerable."""
    rng = random.Random(SEED)
    cases = []
    for index in range(count):
        windows = [(0, 5), (6, 12)] if index % 3 == 0 else [(0, 12)]
        tasks = []
        for number in range(3):
            duration = rng.randint(1, 4)
            tasks.append(
                {
                    "id": f"t{number}",
                    "title": f"Small task {number}",
                    "duration": duration,
                    "release": stamp(rng.randint(0, 3)),
                    "deadline": stamp(rng.randint(7, 12)),
                    "priority": rng.randint(1, 5),
                    "required": rng.random() >= 0.25,
                    "after": [f"t{number - 1}"] if number and rng.random() < 0.25 else [],
                    "chunk": 2 if duration > 2 and index % 5 == 0 else duration,
                }
            )
        payload = {
            "timezone": "Asia/Shanghai",
            "start": stamp(0),
            "end": stamp(12),
            "available": [{"start": stamp(a), "end": stamp(b)} for a, b in windows],
            "tasks": tasks,
            "appointments": [],
            "previous": [],
        }
        if index % 4 == 0:
            payload["appointments"] = [{"id": "a", "title": "Small appointment", "start": stamp(8), "end": stamp(10)}]
        if index % 2:
            payload["previous"] = [
                {"task": task["id"], "part": 0, "start": stamp(number * 3), "duration": task["duration"]}
                for number, task in enumerate(tasks)
            ]
        cases.append({"id": f"tiny-{index:03d}", "suite": "exhaustive", "input": payload})
    return cases


def medium_cases(count: int = 48) -> list[dict[str, Any]]:
    """Plant valid work inside two days; witnesses are recorded but never passed to a planner."""
    cases = []
    for index in range(count):
        rng = random.Random(SEED + 1000 + index)
        windows = [(0, 180), (240, 480), (1440, 1620), (1680, 1920)]
        cursor = 0
        tasks, events, witness = [], [], []
        last_id = None
        for number in range(18):
            duration = rng.choice([15, 30, 45, 60, 75])
            if rng.random() < 0.15:
                duration = 30
                kind = "event"
            else:
                kind = "task"
            found = next(((max(cursor, a), b) for a, b in windows if max(cursor, a) + duration <= b), None)
            if found is None:
                break
            start, _ = found
            finish = start + duration
            if kind == "event":
                events.append(
                    {
                        "id": f"e{number}",
                        "title": f"Existing appointment {number}",
                        "start": stamp(start),
                        "end": stamp(finish),
                    }
                )
            else:
                task_id = f"t{number}"
                task = {
                    "id": task_id,
                    "title": f"Personal task {number}",
                    "duration": duration,
                    "release": stamp(max(0, start - rng.choice([0, 15, 30, 60, 120, 240]))),
                    "deadline": stamp(min(1920, finish + rng.choice([0, 15, 30, 60, 120, 240]))),
                    "priority": rng.randint(1, 5),
                    "required": True,
                    "after": [last_id] if last_id and rng.random() < 0.2 else [],
                }
                chunk = 30 if duration >= 60 and rng.random() < 0.3 else duration
                task["chunk"] = chunk
                for part, offset in enumerate(range(0, duration, chunk)):
                    witness.append(
                        {
                            "task": task_id,
                            "part": part,
                            "minute": start + offset,
                            "duration": min(chunk, duration - offset),
                        }
                    )
                tasks.append(task)
                last_id = task_id
            cursor = finish + rng.choice([0, 0, 0, 15])
        rng.shuffle(tasks)
        cases.append(
            {
                "id": f"calendar-{index:03d}",
                "suite": "constructed_feasible",
                "input": {
                    "timezone": "Asia/Shanghai",
                    "start": stamp(0),
                    "end": stamp(1920),
                    "available": [{"start": stamp(a), "end": stamp(b)} for a, b in windows],
                    "tasks": tasks,
                    "appointments": events,
                },
                "construction_witness": witness,
            }
        )
    return cases


def replan_cases(count: int = 32, constrained: bool = False) -> list[dict[str, Any]]:
    """Insert an appointment into dense existing plans while preserving spare future capacity."""
    cases = []
    for index in range(count):
        rng = random.Random(SEED + 3000 + index)
        tasks, previous, witness = [], [], []
        cursor = 0
        chosen = rng.randrange(2, 8)
        uniform_duration = rng.choice([15, 30, 45])
        for number in range(10):
            duration = uniform_duration if constrained else rng.choice([15, 30, 45])
            release = cursor if constrained and number == chosen else 0
            deadline = cursor + 2 * duration if constrained and number == chosen else 600
            tasks.append(
                {
                    "id": f"t{number}",
                    "title": f"Previously planned task {number}",
                    "duration": duration,
                    "release": stamp(release),
                    "deadline": stamp(deadline),
                    "priority": rng.randint(1, 5),
                    "required": True,
                }
            )
            previous.append({"task": f"t{number}", "part": 0, "start": stamp(cursor), "duration": duration})
            witness.append({"task": f"t{number}", "part": 0, "minute": cursor, "duration": duration})
            cursor += duration
        selected = previous[chosen]
        event = {
            "id": "inserted",
            "title": "New appointment",
            "start": selected["start"],
            "end": stamp(witness[chosen]["minute"] + selected["duration"]),
        }
        witness[chosen]["minute"] = cursor
        if constrained:
            witness[chosen]["minute"] = (chosen + 1) * uniform_duration
            witness[chosen + 1]["minute"] = cursor
        cases.append(
            {
                "id": f"replan-{'tight' if constrained else 'flexible'}-{index:03d}",
                "suite": "constrained_replanning" if constrained else "stable_replanning",
                "input": {
                    "timezone": "Asia/Shanghai",
                    "start": stamp(0),
                    "end": stamp(600),
                    "available": [{"start": stamp(0), "end": stamp(600)}],
                    "tasks": tasks,
                    "previous": previous,
                    "appointments": [event],
                },
                "construction_witness": witness,
                "known_minimum_changed": 2 if constrained else 1,
            }
        )
    return cases
