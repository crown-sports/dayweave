# DayWeave

Version **0.2.1 (prerelease)** is distributed through [GitHub Releases](https://github.com/crown-sports/dayweave/releases/tag/v0.2.1) as a wheel, source archive, and `SHA256SUMS`. Installation below pins this version; no PyPI release is required.

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

Use it for personal study, job hunting or weekly errands when several deadlines
compete for the same free hours. If you only need to remember a few tasks, a
to-do list may be enough. If you need team assignments, reminders or automatic
calendar synchronization, those are outside this prerelease. The useful output
here is a timetable you can inspect and export, or a specific conflict that
helps you decide what to change. [Evidence behind the implementation](docs/product.md).

## Use it

Install Python 3.12 from [python.org](https://www.python.org/downloads/), then
download and unzip **Source code (zip)** from the [v0.2.1 GitHub prerelease](https://github.com/crown-sports/dayweave/releases/tag/v0.2.1).

- **Windows:** double-click `Start-DayWeave.cmd`.
- **macOS:** double-click `Start-DayWeave.command`.
- **Linux or terminal:** run `python3 launch.py`.

The first launch installs dependencies in the project's `.venv` directory and
needs internet. Later launches use that environment. A browser opens at
`http://127.0.0.1:8787`; keep the terminal window open while using the planner.
The core planner needs no account, API key, language model, or GPU.

**Try before entering your own tasks:** choose **简单排序排不了的一天** under
**先体验一下**, click **载入示例**, then **安排这一周**. Success means both
tasks fit: three hours of study at 09:00–12:00 and a one-hour phone task at
12:00–13:00. The phone task may start only after 11:00; placing it first at
11:00 would break up the continuous study time. This is a computed example,
not your real calendar. The **事情比时间多的上午** example instead shows
240 minutes of work competing for 180 minutes and asks you to choose a change.

For your own plan:

1. Click **新建自己的计划** to start your own plan. Editable examples are explicitly
   separate and use their example time rather than the real clock.
2. Paste one task per line or use the manual editor. For example:

   ```text
   Prepare interview | 90 minutes
   Read a chapter | 30 minutes
   ```

3. Set actual deadlines in the review form, or explicitly choose the end of the
   selected week. Then edit your available hours and import an `.ics` calendar
   if you have one. Do not leave example availability in place for a personal plan.
4. Click **安排这一周**. Inspect the timetable, or review the conflict and choose
   what to change. Pin an arrangement when its time must remain fixed.
5. Add an appointment and replan. Export a checked timetable as `.ics` and import
   it into your calendar yourself. Save a JSON project backup to move devices.

The current browser UI is Chinese; JSON/CLI contracts and technical docs are in
English. Dates and durations in pasted text support the formats in
[the usage guide](docs/usage.md).

## Record partial progress and replan only what remains

Open a task's **调整详情** and set **已完成工时（分钟，累计）**. A 90-minute
task with 30 minutes completed now schedules 60 minutes; the original estimate
and cumulative progress stay in your project backup. Updating progress clears
that task's old fixed slots, then **安排这一周** finds time for the remaining
work. Fully completed prerequisites no longer block dependent tasks. No elapsed
calendar time is automatically counted as completed work.

JSON/CLI clients can set `"completed_minutes": 30` alongside `"duration": 90`.
Completed minutes must be an integer from zero through the total estimate. Any
explicit locked starts must match the remaining segment count. The independent
schedule checker and `.ics` export validate only the outstanding work.

```sh
dayweave plan examples/partial-progress.json --output remaining.json --calendar remaining.ics
```

After the developer installation below, this fixed-date example should produce
`state: scheduled` and `validated: true`, with a 60-minute draft followed by a
30-minute review. The `.ics` contains those two remaining blocks. For your own
project, record actual progress yourself and review remaining effort before
replanning; passing time is not proof that work was completed.

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
source .venv/bin/activate
dayweave serve
```

On Windows use `.venv\Scripts\python.exe` and `.venv\Scripts\dayweave.exe`,
or activate with `.venv\Scripts\Activate.ps1` in PowerShell before the commands below.

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
