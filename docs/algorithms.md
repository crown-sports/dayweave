# Algorithms, assumptions, and engineering contribution

## Problem

Schedule one person's work in a union of available time intervals. Each task
has an estimated duration, a release time, a deadline, an importance score, a
mandatory/optional decision, prerequisites, and optionally an explicit split
size or pinned segment starts. Existing appointments occupy fixed intervals.
The input may include a previous schedule.

This is a combination of interval scheduling, precedence constraints, optional
work selection, and schedule stability. A deadline-ordered list alone does not
solve it: placing a short released task in the middle of a free interval can
prevent a longer uninterrupted task from fitting.

## Encoding

The implementation is in [`scheduler.py`](../src/dayweave/scheduler.py).
Times are integer **elapsed UTC minutes** from the horizon origin; display is
in the selected IANA timezone. A task's segment durations sum to its complete
estimated effort. Splitting occurs only at the user's explicit segment size.

For task i, let p_i be its presence Boolean and s_ik the start of segment k.
Every segment shares p_i, so a partially allocated task cannot be counted as
scheduled. Each possible start belongs to a union of ranges:

```text
[max(available_start, release), min(available_end, deadline) - segment_duration]
```

No-overlap covers task segments and fixed appointments. Task segments are
ordered. A scheduled dependent requires its prerequisite to be present and
finished first. Pinned segment starts are equalities when the task is present;
a pinned task must be mandatory. Empty start domains force absence, producing
an explicit conflict if the task was required.

The solver is the established
[OR-Tools CP-SAT](https://developers.google.com/optimization/cp/cp_solver),
using interval/precedence techniques documented in its
[scheduling guide](https://developers.google.com/optimization/scheduling/job_shop).
These primitives and CP-SAT itself are upstream technology, not a novel claim
by DayWeave. The application calls the library; it does not copy its source.

## Stable, sequential optimization

After establishing feasibility, optimize these objectives in order:

1. Maximize the sum of importance scores of present tasks. Required tasks
   already have hard presence constraints; this objective selects optional
   work. In a conflict alternative, unlocked mandatory tasks can also be
   explicitly proposed for postponement. A sum is not a strict priority-class
   hierarchy: two score-3 tasks may outweigh one score-5 task.
2. Minimize the number of existing tasks whose segment starts/durations differ
   from the previous plan, including previously planned work omitted this time.
   New tasks and explicitly removed tasks are reported separately.
3. Minimize summed absolute start-time displacement for paired old/new segments.
   Dropped tasks count as changed; they contribute no fictitious new start time.
4. Minimize priority-weighted completion plus three times total gaps between
   segments of the same task.

Fix the attained value after each stage, then solve the next stage. A feasible
time-limited stage is retained but makes the full result **unproven optimal**.
If a later solve times out, retain the last copied, independently checked
incumbent. The response exposes stage status, objective value, and bound.
The default solve budget is five seconds with one worker and seed 731; model
construction/checking can add overhead. No GPU is involved in scheduling.

## Explaining infeasibility

Mandatory task presence and appointment presence are assumption literals.
After CP-SAT proves infeasibility, obtain a sufficient assumption core, then
try deleting each member and resolving. Remove an assumption only when that
trial is proved infeasible. Unknown trials or a reached limit make
`subset_minimal` false. There are at most 40 deletion checks, each bounded by
0.3 seconds and the remaining budget.

If all relevant deletion checks succeed, the returned core is **subset
minimal**: remove any member and that isolated combination becomes feasible.
It is not necessarily a core with the fewest possible members. Other tasks
can still create a different conflict, so any chosen edit needs a full replan.

A separate arithmetic witness looks for a release/deadline-bounded interval
whose mandatory effort exceeds the union of available hours minus occupied
hours. The difference is the reported minute shortfall. This is a sufficient
explanation when found, not a complete test for fragmentation or dependency
conflicts. All-day and overlapping busy commitments retain their stated
meaning; they are not silently moved or converted to free time.

A suggested alternative permits unpinned work to be absent while keeping
appointments and pinned tasks. It lists every omitted task. The strict export
checker refuses that partial alternative until the user explicitly changes
the relevant tasks to optional and resolves the full input.

## Independent checking

[`validation.py`](../src/dayweave/validation.py) uses ordinary arithmetic,
without solver objects. It checks complete effort, segment order, availability,
release/deadline bounds, required/locked presence, prerequisites, and overlap.
Calendar export runs this checker again and derives titles/times from validated
task identities and minute values rather than trusting display strings.

The small-instance benchmark separately enumerates placements using direct
arithmetic. It checks feasibility, retained-priority optimum, minimum changes,
minimum displacement, and conflict cores. It does not call CP-SAT or the
production result checker as its oracle. Larger fixture construction witnesses
are retained in raw inputs but are not supplied to any evaluated planner.

## Capture and calendar adapters

Explicit `task | effort | deadline` lines use deterministic parsing even when
a local model is configured. Prose can use a separately configured local
Ollama-compatible provider or the included Hugging Face adapter. Model output
contains exact contiguous source quotes. Unsupported time phrases remain
unresolved; missing effort is never estimated by the model. Rejected text is
retained for review and triggers a visible offline fallback.

Substring membership prevents invented source quotations. It does **not**
establish correct task/time association, recall, or instruction resistance.
The user chooses which drafts to add and confirms all fields. Neither a model
nor a parser can mark work completed or publish calendar events.

Calendar import uses separately installed `icalendar` and
[`recurring-ical-events`](https://github.com/niccokunzmann/python-recurring-ical-events).
It expands recurrence within a bounded horizon, respects exclusions, overrides,
cancellations and transparent events, and performs no external URL fetching.
Unsupported recurrence forms are rejected instead of approximated.

## Source structure and patterns

The code is a new implementation for personal planning. There is no inherited
private agent hierarchy or copied project directory. Components have explicit
responsibilities and use composition:

| Component | Responsibility |
| --- | --- |
| `contracts.py` | Immutable domain values, bounded inputs, explicit time interpretation |
| `scheduler.py` | Domain-to-constraint compilation, optimization, conflict queries |
| `validation.py` | Independent acceptance boundary and movement accounting |
| `capture.py`, `calendar_io.py` | Adapters from text/calendar formats to domain values |
| `web.py`, `cli.py` | Entry points to the same use cases |
| `local_model.py` | Optional serialized local inference adapter |
| `project_state.js` | Browser input contract and project restore boundary |
| `input_editor.js`, `capture_sheet.js`, `calendar.js` | Separate editing, review, and calendar views |
| `app.js`, `controls.js` | Workflow controller and shared controls |

Immutable domain values, adapter boundaries, an explicit model compiler, and
an independent validator supply the useful design structure. There are no
empty factories or deep inheritance chains added solely to name a pattern.
Methods have fresh contract docstrings; public source remains formatted.

## What is and is not claimed

The engineering contribution is the integrated, local, explainable workflow
with stable scheduling and published validation. The hard parts are making
constraints consistent across solving/checking/import/export, handling bounded
search honestly, and preserving user decisions during replanning.

These are established algorithmic techniques applied to a concrete personal
problem. The published benchmark is synthetic and deliberately labeled. This
release does not establish new mathematical theory, superiority to all other
planners, measured human productivity gains, or reliable automatic completion.
