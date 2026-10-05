"""Paired solver/baseline evaluation with independently enumerated small-instance optima."""

from __future__ import annotations

import argparse
import copy
import hashlib
import itertools
import json
import platform
import statistics
import time
from collections import defaultdict
from datetime import UTC, datetime
from importlib.metadata import version
from pathlib import Path
from typing import Any

from fixtures import SEED, medium_cases, replan_cases, tiny_cases

from dayweave.contracts import PlanningInput, Task
from dayweave.examples import example
from dayweave.scheduler import schedule
from dayweave.validation import movement, validate_schedule

ROOT = Path(__file__).resolve().parents[1]


def source_fingerprint() -> str:
    """Hash public implementation and benchmark source, independent of checkout location."""
    digest = hashlib.sha256()
    paths = sorted(
        [
            *ROOT.glob("src/dayweave/*.py"),
            *ROOT.glob("src/dayweave/ui/*"),
            *ROOT.glob("benchmarks/*.py"),
            ROOT / "pyproject.toml",
            ROOT / "launch.py",
        ]
    )
    for path in paths:
        digest.update(path.relative_to(ROOT).as_posix().encode() + b"\0" + path.read_bytes() + b"\0")
    return digest.hexdigest()


def exhaustive(plan: PlanningInput) -> tuple[list[dict[str, Any]] | None, tuple[int, int, int] | None, int]:
    """Enumerate placements using direct arithmetic, without CP-SAT or the result checker."""
    choices = []
    for task in plan.tasks:
        candidates = []
        ranges = [range(task.release, task.deadline - duration + 1) for duration in task.parts]
        for starts in itertools.product(*ranges):
            spans = [(start, start + duration) for start, duration in zip(starts, task.parts, strict=True)]
            if any(not any(a <= s and e <= b for a, b in plan.available) for s, e in spans):
                continue
            if any(a[1] > b[0] for a, b in zip(spans, spans[1:], strict=False)):
                continue
            if task.locked and tuple(starts) != task.locked:
                continue
            candidates.append(
                [
                    {"task": task.id, "part": part, "minute": start, "duration": duration}
                    for part, (start, duration) in enumerate(zip(starts, task.parts, strict=True))
                ]
            )
        if not task.required:
            candidates.append([])
        choices.append(candidates)
    best_slots, best_score, count = None, None, 0
    old = defaultdict(list)
    for item in plan.previous:
        old[item.task].append((item.part, item.start, item.duration))
    for combination in itertools.product(*choices):
        slots = [item for group in combination for item in group]
        by_task = {task.id: group for task, group in zip(plan.tasks, combination, strict=True) if group}
        spans = sorted(
            [(s["minute"], s["minute"] + s["duration"]) for s in slots] + [(e.start, e.end) for e in plan.appointments]
        )
        if any(a[1] > b[0] for a, b in zip(spans, spans[1:], strict=False)):
            continue
        if any(
            parent not in by_task
            or max(x["minute"] + x["duration"] for x in by_task[parent]) > min(x["minute"] for x in by_task[task.id])
            for task in plan.tasks
            if task.id in by_task
            for parent in task.after
        ):
            continue
        count += 1
        retained = sum(task.priority for task in plan.tasks if task.id in by_task)
        changed, distance = 0, 0
        for task in plan.tasks:
            if not old[task.id]:
                continue
            previous = sorted(old[task.id])
            current = sorted((x["part"], x["minute"], x["duration"]) for x in by_task.get(task.id, []))
            changed += previous != current
            distance += sum(abs(a[1] - b[1]) for a, b in zip(previous, current, strict=False))
        score = (-retained, changed, distance)
        if best_score is None or score < best_score:
            best_slots, best_score = slots, score
    return best_slots, best_score, count


def place_task(
    plan: PlanningInput, task: Task, busy: list[tuple[int, int]], parent_end: int
) -> list[dict[str, Any]] | None:
    """Greedily allocate an entire task; a failed split is rolled back rather than partly counted."""
    occupied = list(busy)
    slots = []
    cursor = max(task.release, parent_end)
    for part, duration in enumerate(task.parts):
        selected = None
        for a, b in plan.available:
            start, last = max(cursor, a), min(b, task.deadline) - duration
            if task.locked:
                start = task.locked[part]
            while start <= last and start >= max(cursor, a):
                conflicts = [(left, right) for left, right in occupied if start < right and left < start + duration]
                if not conflicts:
                    selected = start
                    break
                if task.locked:
                    break
                start = max(right for _, right in conflicts)
            if selected is not None:
                break
        if selected is None:
            return None
        slots.append(
            {
                "task": task.id,
                "part": part,
                "minute": selected,
                "duration": duration,
                "start": plan.iso(selected),
                "end": plan.iso(selected + duration),
                "title": task.title,
            }
        )
        occupied.append((selected, selected + duration))
        cursor = selected + duration
    return slots


def greedy(plan: PlanningInput, order: str, keep_existing: bool = False) -> dict[str, Any]:
    """Use dependency-aware insertion, with an optional preservation-first reservation pass."""
    started = time.monotonic()
    tasks = {task.id: task for task in plan.tasks}
    essential = {task.id for task in plan.tasks if task.required}
    while True:
        parents = {parent for key in essential for parent in tasks[key].after}
        if parents <= essential:
            break
        essential |= parents
    placed: dict[str, list[dict[str, Any]]] = {}
    busy = [(event.start, event.end) for event in plan.appointments]
    if keep_existing:
        old = defaultdict(list)
        for item in plan.previous:
            if item.task in tasks:
                old[item.task].append(
                    {
                        "task": item.task,
                        "part": item.part,
                        "minute": item.start,
                        "duration": item.duration,
                        "start": plan.iso(item.start),
                        "end": plan.iso(item.start + item.duration),
                        "title": tasks[item.task].title,
                    }
                )
        candidates = dict(old)
        changed = True
        while changed:
            changed = False
            for key in list(candidates):
                task = tasks[key]
                group = sorted(candidates[key], key=lambda x: x["part"])
                wrong = [x["part"] for x in group] != list(range(len(task.parts))) or [
                    x["duration"] for x in group
                ] != list(task.parts)
                wrong |= any(
                    x["minute"] < task.release
                    or x["minute"] + x["duration"] > task.deadline
                    or not any(a <= x["minute"] and x["minute"] + x["duration"] <= b for a, b in plan.available)
                    or any(x["minute"] < b and a < x["minute"] + x["duration"] for a, b in busy)
                    for x in group
                )
                wrong |= any(
                    parent not in candidates
                    or max(x["minute"] + x["duration"] for x in candidates[parent]) > min(x["minute"] for x in group)
                    for parent in task.after
                )
                wrong |= bool(task.locked) and tuple(x["minute"] for x in group) != task.locked
                if wrong:
                    del candidates[key]
                    changed = True
        placed.update(candidates)
        busy.extend((x["minute"], x["minute"] + x["duration"]) for group in placed.values() for x in group)
    remaining = set(tasks) - placed.keys()
    failed = set()
    while remaining:
        ready = [tasks[key] for key in remaining if set(tasks[key].after) <= (placed.keys() | failed)]
        if not ready:
            raise RuntimeError("Fixture has a dependency cycle")

        def ranking(task: Task) -> tuple[Any, ...]:
            score = (task.deadline, -task.priority) if order == "edf" else (-task.priority, task.deadline)
            return (task.id not in essential, *score, task.id)

        task = min(ready, key=ranking)
        remaining.remove(task.id)
        group = None
        if not set(task.after) & failed:
            end = max((x["minute"] + x["duration"] for parent in task.after for x in placed[parent]), default=0)
            group = place_task(plan, task, busy, end)
        if group is None:
            failed.add(task.id)
        else:
            placed[task.id] = group
            busy.extend((x["minute"], x["minute"] + x["duration"]) for x in group)
    slots = sorted([x for group in placed.values() for x in group], key=lambda x: (x["minute"], x["task"], x["part"]))
    errors = validate_schedule(plan, slots)
    return {
        "state": "scheduled" if not errors else "incomplete",
        "validated": not errors,
        "slots": slots,
        "errors": errors,
        "movement": movement(plan, slots),
        "duration_ms": round((time.monotonic() - started) * 1000, 3),
    }


def result_metrics(plan: PlanningInput, result: dict[str, Any]) -> dict[str, Any]:
    slots = result.get("slots", [])
    included = {x["task"] for x in slots}
    valid = result.get("state") == "scheduled" and not validate_schedule(plan, slots)
    return {
        "valid_complete": valid,
        "retained_tasks": len(included),
        "retained_priority": sum(t.priority for t in plan.tasks if t.id in included),
        "changed_tasks": movement(plan, slots)["changed_count"],
        "duration_ms": result["duration_ms"],
        "proven_all_objectives": bool(result.get("optimal")),
    }


def preserve_or_rebuild(plan: PlanningInput) -> dict[str, Any]:
    """Try preservation first, then rebuild by deadline when reservations block required work."""
    retained = greedy(plan, "edf", True)
    if retained["validated"]:
        retained["fallback_used"] = False
        return retained
    rebuilt = greedy(plan, "edf")
    rebuilt["duration_ms"] += retained["duration_ms"]
    rebuilt["fallback_used"] = True
    return rebuilt


def check_tiny_core(payload: dict[str, Any], result: dict[str, Any]) -> dict[str, Any]:
    """Check core unsatisfiability and each single deletion with the independent enumeration oracle."""
    core = result["conflict"]["items"]

    def feasible(items: list[dict[str, str]]) -> bool:
        retained = {(item["kind"], item["id"]) for item in items}
        trial = copy.deepcopy(payload)
        for task in trial["tasks"]:
            task["required"] = ("task", task["id"]) in retained
        trial["appointments"] = [event for event in trial["appointments"] if ("appointment", event["id"]) in retained]
        return exhaustive(PlanningInput.from_dict(trial))[0] is not None

    infeasible = not feasible(core)
    deletions = [feasible([item for item in core if item != removed]) for removed in core]
    minimal = all(deletions)
    if not infeasible or (result["conflict"]["subset_minimal"] and not minimal):
        raise RuntimeError("A conflict explanation disagreed with exhaustive enumeration")
    return {"infeasible": infeasible, "subset_minimal": minimal, "single_deletion_feasible": deletions}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=Path("benchmark-runs/scheduling"))
    parser.add_argument("--seconds", type=float, default=3)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    cases = tiny_cases() + medium_cases() + replan_cases() + replan_cases(constrained=True)
    for kind in ("sorting", "overload"):
        cases.append({"id": f"story-{kind}", "suite": "worked_examples", "input": example(kind)})
    (args.output / "cases.json").write_text(json.dumps(cases, ensure_ascii=False, indent=2) + "\n")
    records = []
    with (args.output / "results.jsonl").open("w") as stream:
        for case in cases:
            plan = PlanningInput.from_dict(case["input"])
            witness = case.get("construction_witness")
            if witness is not None and validate_schedule(plan, witness):
                raise RuntimeError("Construction witness failed independent validation: " + case["id"])
            methods = {
                "dayweave": schedule(plan, seconds=args.seconds),
                "earliest_deadline": greedy(plan, "edf"),
                "priority_first": greedy(plan, "priority"),
                "preserve_then_edf": greedy(plan, "edf", True),
                "preserve_or_rebuild": preserve_or_rebuild(plan),
            }
            record = {
                "case": case["id"],
                "suite": case["suite"],
                "methods": methods,
                "metrics": {key: result_metrics(plan, result) for key, result in methods.items()},
            }
            if "known_minimum_changed" in case:
                observed = record["metrics"]["dayweave"]
                record["known_minimum_changed"] = case["known_minimum_changed"]
                record["matches_known_minimum_changed"] = (
                    observed["valid_complete"] and observed["changed_tasks"] == case["known_minimum_changed"]
                )
                if not record["matches_known_minimum_changed"]:
                    raise RuntimeError("Solver did not achieve the constructed movement lower bound: " + case["id"])
            if case["suite"] == "exhaustive":
                oracle_slots, score, count = exhaustive(plan)
                result = methods["dayweave"]
                feasible = oracle_slots is not None
                observed = record["metrics"]["dayweave"]
                observed_score = (
                    -observed["retained_priority"],
                    observed["changed_tasks"],
                    movement(plan, result.get("slots", []))["displacement_minutes"],
                )
                matches = (result["state"] == "scheduled") == feasible and (not feasible or observed_score == score)
                record["oracle"] = {
                    "feasible": feasible,
                    "valid_placements": count,
                    "best_score": score,
                    "matches_feasibility_and_first_three_objectives": matches,
                }
                if result["state"] == "conflict":
                    record["oracle"]["conflict_core"] = check_tiny_core(case["input"], result)
                if not matches:
                    raise RuntimeError("Solver disagreed with exhaustive oracle: " + case["id"])
            records.append(record)
            stream.write(json.dumps(record, ensure_ascii=False) + "\n")
            stream.flush()
            if len(records) % 12 == 0:
                print(f"Evaluated {len(records)}/{len(cases)} paired cases", flush=True)
    summary: dict[str, Any] = {
        "seed": SEED,
        "source_sha256": source_fingerprint(),
        "created_at": datetime.now(UTC).isoformat(),
        "python": platform.python_version(),
        "platform": {"system": platform.system(), "machine": platform.machine()},
        "versions": {
            name: version(name) for name in ("dayweave", "ortools", "numpy", "icalendar", "recurring-ical-events")
        },
        "solve_budget_seconds": args.seconds,
        "case_count": len(cases),
        "suites": {},
        "limits": "Synthetic fixtures; no measured human productivity or superiority to commercial planning tools.",
    }
    for suite in sorted({record["suite"] for record in records}):
        subset = [record for record in records if record["suite"] == suite]
        summary["suites"][suite] = {"cases": len(subset), "methods": {}}
        for method in methods:
            values = [record["metrics"][method] for record in subset]
            summary["suites"][suite]["methods"][method] = {
                "valid_complete": sum(v["valid_complete"] for v in values),
                "proven_all_objectives": sum(v["proven_all_objectives"] for v in values),
                "median_ms": round(statistics.median(v["duration_ms"] for v in values), 3),
                "p95_ms": round(
                    sorted(v["duration_ms"] for v in values)[min(len(values) - 1, int(len(values) * 0.95))], 3
                ),
            }
        if suite in {"stable_replanning", "constrained_replanning"}:
            paired = [
                record for record in subset if all(value["valid_complete"] for value in record["metrics"].values())
            ]
            summary["suites"][suite]["common_valid_denominator"] = len(paired)
            summary["suites"][suite]["mean_changed_on_common_valid"] = {
                key: round(statistics.mean(record["metrics"][key]["changed_tasks"] for record in paired), 3)
                if paired
                else None
                for key in methods
            }
            summary["suites"][suite]["mean_changed_on_each_methods_valid_cases"] = {
                key: statistics.mean(
                    record["metrics"][key]["changed_tasks"]
                    for record in subset
                    if record["metrics"][key]["valid_complete"]
                )
                if any(record["metrics"][key]["valid_complete"] for record in subset)
                else None
                for key in methods
            }
            summary["suites"][suite]["known_minimum_agreements"] = sum(
                record["matches_known_minimum_changed"] for record in subset
            )
            pairs = {}
            for key in methods:
                if key == "dayweave":
                    continue
                common = [
                    record
                    for record in subset
                    if record["metrics"]["dayweave"]["valid_complete"] and record["metrics"][key]["valid_complete"]
                ]
                pairs[key] = {
                    "common_valid_denominator": len(common),
                    "dayweave_mean_changed": statistics.mean(r["metrics"]["dayweave"]["changed_tasks"] for r in common)
                    if common
                    else None,
                    "baseline_mean_changed": statistics.mean(r["metrics"][key]["changed_tasks"] for r in common)
                    if common
                    else None,
                }
            summary["suites"][suite]["pairwise_changes"] = pairs
        if suite == "exhaustive":
            summary["suites"][suite]["oracle_agreements"] = sum(
                record["oracle"]["matches_feasibility_and_first_three_objectives"] for record in subset
            )
            summary["suites"][suite]["independently_checked_conflict_cores"] = sum(
                "conflict_core" in record["oracle"] for record in subset
            )
    for name in ("cases.json", "results.jsonl"):
        summary.setdefault("artifact_sha256", {})[name] = hashlib.sha256((args.output / name).read_bytes()).hexdigest()
    (args.output / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
