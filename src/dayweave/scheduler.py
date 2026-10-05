"""Constraint scheduling, bounded conflict explanations, and stable replanning."""

from __future__ import annotations

import time
from collections import defaultdict
from dataclasses import dataclass
from typing import Any

from ortools.sat.python import cp_model

from .contracts import PlanningInput, merge_intervals
from .validation import movement, validate_schedule


@dataclass
class CompiledPlan:
    model: Any
    present: dict[str, Any]
    starts: dict[str, list[Any]]
    ends: dict[str, list[Any]]
    assumptions: dict[str, Any]
    labels: dict[str, dict[str, str]]
    objectives: list[tuple[str, str, Any]]


def compile_plan(plan: PlanningInput, relaxed: bool = False) -> CompiledPlan:
    """Encode shared task presence, time windows, segment order, dependencies, appointments, and pins."""
    model = cp_model.CpModel()
    present: dict[str, Any] = {}
    starts: dict[str, list[Any]] = {}
    ends: dict[str, list[Any]] = {}
    assumptions: dict[str, Any] = {}
    labels: dict[str, dict[str, str]] = {}
    intervals = []
    for event in plan.appointments:
        flag = model.new_bool_var(f"appointment/{event.id}")
        key = f"appointment/{event.id}"
        assumptions[key] = flag
        labels[key] = {"kind": "appointment", "id": event.id, "title": event.title}
        intervals.append(model.new_optional_fixed_size_interval_var(event.start, event.end - event.start, flag, key))
    for task in plan.tasks:
        flag = model.new_bool_var(f"task/{task.id}")
        present[task.id] = flag
        starts[task.id], ends[task.id] = [], []
        if (task.required and not relaxed) or task.locked:
            key = f"task/{task.id}"
            assumptions[key] = flag
            labels[key] = {"kind": "locked_task" if task.locked else "task", "id": task.id, "title": task.title}
        for part, duration in enumerate(task.parts):
            domains = [
                (max(left, task.release), min(right, task.deadline) - duration)
                for left, right in plan.available
                if max(left, task.release) <= min(right, task.deadline) - duration
            ]
            if domains:
                start = model.new_int_var_from_domain(
                    cp_model.Domain.from_intervals(domains), f"start/{task.id}/{part}"
                )
            else:
                start = model.new_int_var(0, plan.horizon, f"start/{task.id}/{part}")
                model.add(flag == 0)
            end = model.new_int_var(0, plan.horizon + 1440, f"end/{task.id}/{part}")
            model.add(end == start + duration)
            intervals.append(model.new_optional_interval_var(start, duration, end, flag, f"segment/{task.id}/{part}"))
            if part:
                model.add(start >= ends[task.id][-1]).only_enforce_if(flag)
            if task.locked:
                model.add(start == task.locked[part]).only_enforce_if(flag)
            starts[task.id].append(start)
            ends[task.id].append(end)
    model.add_no_overlap(intervals)
    for task in plan.tasks:
        for parent in task.after:
            model.add(present[parent] >= present[task.id])
            model.add(starts[task.id][0] >= ends[parent][-1]).only_enforce_if(present[task.id])
    previous = defaultdict(list)
    for slot in plan.previous:
        previous[slot.task].append(slot)
    changed, displacement, compact = [], [], []
    for task in plan.tasks:
        flag = present[task.id]
        old = sorted(previous[task.id], key=lambda item: item.part)
        if old:
            moved = model.new_bool_var(f"changed/{task.id}")
            if [item.part for item in old] != list(range(len(task.parts))) or [item.duration for item in old] != list(
                task.parts
            ):
                model.add(moved == 1)
            else:
                equal = []
                for part, prior in enumerate(old):
                    same = model.new_bool_var(f"same/{task.id}/{part}")
                    model.add(starts[task.id][part] == prior.start).only_enforce_if(same)
                    model.add(starts[task.id][part] != prior.start).only_enforce_if(same.Not())
                    equal.append(same)
                model.add_bool_and([flag, *equal]).only_enforce_if(moved.Not())
                model.add_bool_or([flag.Not(), *(item.Not() for item in equal)]).only_enforce_if(moved)
            changed.append(moved)
            for part, prior in enumerate(old[: len(task.parts)]):
                absolute = model.new_int_var(0, 161280, f"absolute/{task.id}/{part}")
                distance = model.new_int_var(0, 161280, f"distance/{task.id}/{part}")
                model.add_abs_equality(absolute, starts[task.id][part] - prior.start)
                model.add(distance == absolute).only_enforce_if(flag)
                model.add(distance == 0).only_enforce_if(flag.Not())
                displacement.append(distance)
        completion = model.new_int_var(0, plan.horizon + 1440, f"completion/{task.id}")
        model.add(completion == ends[task.id][-1]).only_enforce_if(flag)
        model.add(completion == 0).only_enforce_if(flag.Not())
        gap = model.new_int_var(0, plan.horizon + 1440, f"gap/{task.id}")
        model.add(gap == ends[task.id][-1] - starts[task.id][0] - task.duration).only_enforce_if(flag)
        model.add(gap == 0).only_enforce_if(flag.Not())
        compact.extend([task.priority * completion, 3 * gap])
    objectives = [("retained_priority", "max", sum(task.priority * present[task.id] for task in plan.tasks))]
    if changed:
        objectives.extend([("changed_tasks", "min", sum(changed)), ("displacement_minutes", "min", sum(displacement))])
    objectives.append(("early_compact_completion", "min", sum(compact)))
    model.add_assumptions(list(assumptions.values()))
    return CompiledPlan(model, present, starts, ends, assumptions, labels, objectives)


def make_solver(seconds: float) -> Any:
    """Use one worker for repeatable tests and bounded local computation."""
    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = max(0.001, seconds)
    solver.parameters.num_search_workers = 1
    solver.parameters.random_seed = 731
    return solver


def read_slots(plan: PlanningInput, compiled: CompiledPlan, solver: Any) -> list[dict[str, Any]]:
    """Copy a solver incumbent immediately so a later timed-out solve cannot erase it."""
    slots = []
    for task in plan.tasks:
        if not solver.value(compiled.present[task.id]):
            continue
        for part, duration in enumerate(task.parts):
            start = int(solver.value(compiled.starts[task.id][part]))
            slots.append(
                {
                    "task": task.id,
                    "title": task.title,
                    "part": part,
                    "minute": start,
                    "duration": duration,
                    "start": plan.iso(start),
                    "end": plan.iso(start + duration),
                    "priority": task.priority,
                    "locked": bool(task.locked),
                }
            )
    return sorted(slots, key=lambda item: (item["minute"], item["task"], item["part"]))


def optimize(
    plan: PlanningInput,
    compiled: CompiledPlan,
    deadline: float,
    initial: tuple[Any, int] | None = None,
    relaxed: bool = False,
) -> dict[str, Any]:
    """Optimize lexicographically, retaining feasible incumbents and exposing every unproven stage."""
    slots = read_slots(plan, compiled, initial[0]) if initial else None
    stages = []
    proven = True
    for index, (name, direction, expression) in enumerate(compiled.objectives):
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            proven = False
            break
        if direction == "max":
            compiled.model.maximize(expression)
        else:
            compiled.model.minimize(expression)
        solver = make_solver(remaining / (len(compiled.objectives) - index))
        status = solver.solve(compiled.model)
        stage: dict[str, Any] = {"objective": name, "status": solver.status_name(status)}
        if status not in {cp_model.OPTIMAL, cp_model.FEASIBLE}:
            stages.append(stage)
            proven = False
            break
        slots = read_slots(plan, compiled, solver)
        value = int(round(solver.objective_value))
        stage.update({"value": value, "bound": solver.best_objective_bound})
        stages.append(stage)
        proven = proven and status == cp_model.OPTIMAL
        compiled.model.add(expression == value)
    if slots is None:
        return {
            "state": "infeasible" if stages and stages[0]["status"] == "INFEASIBLE" else "unknown",
            "slots": [],
            "stages": stages,
            "optimal": False,
            "validated": False,
        }
    errors = validate_schedule(plan, slots, allow_postponed=relaxed)
    if errors:
        raise RuntimeError("Independent schedule validation failed: " + "; ".join(errors))
    included = {slot["task"] for slot in slots}
    return {
        "state": "alternative" if relaxed else "scheduled",
        "slots": slots,
        "stages": stages,
        "optimal": proven and len(stages) == len(compiled.objectives),
        "validated": True,
        "postponed": [
            {"id": task.id, "title": task.title, "duration": task.duration, "required": task.required}
            for task in plan.tasks
            if task.id not in included
        ],
        "movement": movement(plan, slots),
    }


def shrink_conflict(compiled: CompiledPlan, solver: Any, deadline: float) -> dict[str, Any]:
    """Reduce a solver-proven conflict by deletion; never label a bounded partial shrink minimal."""
    by_index = {variable.index: key for key, variable in compiled.assumptions.items()}
    core = [by_index[index] for index in solver.sufficient_assumptions_for_infeasibility() if index in by_index]
    minimal = True
    checks: list[dict[str, str]] = []
    for key in list(core):
        remaining = deadline - time.monotonic()
        if remaining <= 0 or len(checks) >= 40:
            minimal = False
            break
        trial = [item for item in core if item != key]
        compiled.model.clear_assumptions()
        compiled.model.add_assumptions([compiled.assumptions[item] for item in trial])
        trial_solver = make_solver(min(0.3, remaining))
        status = trial_solver.solve(compiled.model)
        checks.append({"removed": key, "status": trial_solver.status_name(status)})
        if status == cp_model.INFEASIBLE:
            core = trial
        elif status not in {cp_model.OPTIMAL, cp_model.FEASIBLE}:
            minimal = False
    return {
        "items": [compiled.labels[key] for key in core],
        "subset_minimal": minimal,
        "deletion_checks": checks,
        "note": "Subset minimal does not mean minimum cardinality.",
    }


def capacity_witness(plan: PlanningInput) -> dict[str, Any] | None:
    """Find a workload-over-capacity interval independent of CP-SAT's search internals."""
    required = [task for task in plan.tasks if task.required]
    occupied = merge_intervals(
        [(max(a, event.start), min(b, event.end)) for a, b in plan.available for event in plan.appointments]
    )
    candidates = sorted({0, plan.horizon, *(task.release for task in required), *(task.deadline for task in required)})
    best: dict[str, Any] | None = None
    for left in candidates:
        for right in candidates:
            if right <= left:
                continue
            contained = [task for task in required if left <= task.release and task.deadline <= right]
            demand = sum(task.duration for task in contained)
            capacity = sum(max(0, min(right, b) - max(left, a)) for a, b in plan.available) - sum(
                max(0, min(right, b) - max(left, a)) for a, b in occupied
            )
            deficit = demand - capacity
            if deficit > 0 and (best is None or deficit > best["shortfall_minutes"]):
                best = {
                    "start": plan.iso(left),
                    "end": plan.iso(right),
                    "required_minutes": demand,
                    "available_minutes": capacity,
                    "shortfall_minutes": deficit,
                    "tasks": [task.id for task in contained],
                }
    return best


def schedule(plan: PlanningInput, seconds: float = 5.0) -> dict[str, Any]:
    """Return a checked plan, a proved conflict with an explicit alternative, or an honest timeout."""
    if not 0.01 <= seconds <= 15:
        raise ValueError("Solve budget must be between 0.01 and 15 seconds")
    started = time.monotonic()
    deadline = started + seconds
    compiled = compile_plan(plan)
    solver = make_solver(min(1.0, seconds / 3))
    status = solver.solve(compiled.model)
    if status in {cp_model.OPTIMAL, cp_model.FEASIBLE}:
        result = optimize(plan, compiled, deadline, (solver, status))
    elif status == cp_model.INFEASIBLE:
        conflict = shrink_conflict(compiled, solver, min(deadline, time.monotonic() + seconds / 3))
        alternate = optimize(plan, compile_plan(plan, relaxed=True), deadline, relaxed=True)
        result = {
            "state": "conflict",
            "slots": [],
            "validated": False,
            "optimal": False,
            "conflict": conflict,
            "capacity": capacity_witness(plan),
            "alternative": alternate,
            "message": "Required commitments cannot all fit. Review the conflicting items or permit postponement.",
        }
    elif status == cp_model.MODEL_INVALID:
        raise RuntimeError("Internal scheduling model is invalid: " + compiled.model.validate())
    else:
        result = {
            "state": "unknown",
            "slots": [],
            "validated": False,
            "optimal": False,
            "message": "No feasible plan or infeasibility proof was found within the solve budget.",
        }
    result["duration_ms"] = round((time.monotonic() - started) * 1000, 3)
    result["timezone"] = plan.zone.key
    result["horizon"] = {"start": plan.iso(0), "end": plan.iso(plan.horizon)}
    result["available"] = [{"start": plan.iso(left), "end": plan.iso(right)} for left, right in plan.available]
    result["appointments"] = [
        {"id": event.id, "title": event.title, "start": plan.iso(event.start), "end": plan.iso(event.end)}
        for event in plan.appointments
    ]
    return result
