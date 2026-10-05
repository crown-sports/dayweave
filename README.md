# DayWeave

**A personal planner that fits your actual calendar, explains overload, and changes fewer plans when life interrupts.**

[中文使用说明](README.zh-CN.md) · [Algorithms](docs/algorithms.md) · [Measured results](docs/results.md)

People have tasks, deadlines, appointments, and limited free hours. Sorting a
to-do list does not establish whether the work fits. Rebuilding a week whenever
one appointment changes can disrupt otherwise usable plans.

DayWeave turns **tasks + estimated durations + deadlines + available hours +
existing appointments** into a checked timetable. If commitments conflict, it
shows the conflicting items and, when possible, a precise time shortfall. If a
new appointment arrives, it searches for a plan that moves fewer existing tasks.
You review any proposed postponement before using it.

![Actual browser result: an inserted appointment moves one task](docs/assets/workbench.jpg)

## Use it

Install Python 3.12 from [python.org](https://www.python.org/downloads/), then
download and unzip this repository from **Code → Download ZIP** on GitHub.

- **Windows:** double-click `Start-DayWeave.cmd`.
- **macOS:** double-click `Start-DayWeave.command`.
- **Linux or terminal:** run `python3 launch.py`.

The first launch installs dependencies in the project's `.venv` directory and
needs internet. Later launches use that environment. A browser opens at
`http://127.0.0.1:8787`; keep the terminal window open while using the planner.
The core planner needs no account, API key, language model, or GPU.

In the browser:

1. Click **新建自己的计划** to start your own plan. Editable examples are explicitly
   separate and use their example time rather than the real clock.
2. Paste one task per line or use the manual editor. For example:

   ```text
   Prepare interview | 90 minutes | 2026-10-09 18:00
   Read a chapter | 30 minutes | 2026-10-10 18:00
   ```

3. Review durations and deadlines, then edit your available hours and import an
   `.ics` calendar if you have one.
4. Click **安排这一周**. Inspect the timetable, or review the conflict and choose
   what to change. Pin an arrangement when its time must remain fixed.
5. Add an appointment and replan. Export a checked timetable as `.ics` and import
   it into your calendar yourself. Save a JSON project backup to move devices.

The current browser UI is Chinese; JSON/CLI contracts and technical docs are in
English. Dates and durations in pasted text support the formats in
[the usage guide](docs/usage.md).

## What the algorithm does

This is an independently implemented application built on the established
[OR-Tools CP-SAT solver](https://developers.google.com/optimization/cp/cp_solver).
It does not claim to invent CP-SAT or a new scheduling theory.

- Encode available windows, integer-minute durations, deadlines, prerequisites,
  appointments, explicit splitting, and pinned starts as actual constraints.
- Optimize sequentially: retained priority sum, changed existing tasks, start
  displacement, then earlier completion and smaller gaps between segments.
- Explain solver-proven infeasibility with an assumption core and bounded
  deletion checks. A subset-minimal core is distinct from a smallest-size core.
- Validate returned schedules with a separate arithmetic checker before
  accepting or exporting them. Report feasible solutions and timeouts honestly.
- Parse explicit structured notes deterministically. Optional local-model
  capture selects exact source substrings from prose; missing fields remain for
  review and rejected output falls back visibly.

The contribution is a usable local workflow that combines these techniques,
with independent checks and reproducible evidence. See
[the mathematical model and worked examples](docs/algorithms.md).

## Evidence, not productivity promises

Paired fixtures use identical inputs and include every failed case. In the
48-case constructed-feasible suite, DayWeave produced **48 complete valid
plans**, versus **34** for dependency-aware earliest-deadline insertion.
In 32 constrained replanning fixtures, it moved **2 tasks per case**;
preserve-first insertion with deadline-rebuild fallback moved **9.125 on
average**, with both methods completing all 32 cases. On flexible replanning
fixtures, the preservation baseline also achieves one moved task.

An independent exhaustive oracle agrees on feasibility and the first three
optimization objectives in **96/96 small cases**, including 17 independently
checked conflict cores. These are published synthetic fixtures, not measured
human productivity or comparisons against commercial planning apps. CPU
results, actual RTX 5090 capture outputs, source hashes, and failures are in
[the results report](docs/results.md).

## Developer installation

```sh
python3 -m venv .venv
.venv/bin/python -m pip install '.[dev]'
.venv/bin/dayweave serve
```

On Windows use `.venv\Scripts\python.exe` and `.venv\Scripts\dayweave.exe`.

```sh
dayweave example sorting --output input.json
dayweave plan input.json --output result.json --calendar plan.ics
python benchmarks/evaluate.py --output benchmark-runs/scheduling --seconds 2
pytest -q
ruff check src tests benchmarks launch.py
mypy src
```

[JSON input/output and local-model setup](docs/usage.md) ·
[Design and acceptance contract](docs/design.md)

## Limits and data

This is a local, single-person prerelease. The browser stores the project in
local storage; calculations run in the local process. Generated downloads are
held in bounded memory for at most five minutes. Clear browser data only after
saving a backup. Initial package installation needs network access; optional
model weights are obtained separately. No connected calendar is written to.

The UI plans one week; the API allows up to 28 days, 60 tasks, and 300 explicit
segments. Time is minute-based. Overlapping busy appointments are conflicting
commitments; transparent calendar events are ignored. Future planning excludes
elapsed appointments, but unfinished tasks still need your review. A task's
duration is your estimate; DayWeave does not infer actual completion or promise
adherence. It does not implement reminders, shared calendars, habit tracking,
travel-time estimation, or optimality beyond a bounded solve.

MIT for DayWeave. Separately installed dependency licenses and optional model
attributions are described in [NOTICE](NOTICE).
