# DayWeave development contract

## Person, problem, outcome

A person has deadlines, appointments, limited free hours, and tasks that may
depend on each other. A plausible list of tasks is not enough: the work must fit
the calendar. When a new appointment arrives, rebuilding the whole week creates
unnecessary disruption. When work cannot fit, a useful planner should explain
which commitments conflict rather than drawing an impossible timetable.

Input: editable tasks, durations, release/deadline times, dependencies, optional
splitting, available hours, existing calendar appointments, and optionally a
previous plan. Output: an independently validated timetable, explicit postponed
work, explainable conflicts, and calendar export. A pasted note can populate a
review sheet; missing or uncertain timing never becomes an invented hard fact.

## Algorithms and engineering

1. Represent optional task segments as integer-minute intervals. Each task has
   one shared presence variable, required by an assumption when the user marks
   it mandatory. Available windows restrict start domains; deadlines, dependency
   precedence, locked starts, and no-overlap are actual solver constraints.
2. Use OR-Tools CP-SAT, an established open-source constraint solver, with
   sequential objectives: retained priority, number of changed old tasks, total
   start-time displacement, then early completion/compact segments. Publish each
   objective's solve status and bound; a time-limited feasible plan is not called
   a proven optimum.
3. On proven infeasibility, obtain an assumption conflict core and shrink it by
   deletion checks within a bounded budget. State whether subset minimality was
   established; this does not mean minimum cardinality. Explain workload versus
   available capacity when that supplies an independent numeric witness.
4. Produce a best-effort alternative while retaining appointments and explicit
   locks. A user sees every omitted task and must choose whether to permit
   postponement. Calendar export does not silently turn that alternative into a
   complete plan.
5. Validate every result with a separate interval/precedence checker that does
   not use the solver. Compare against earliest-deadline and priority-first
   insertion on paired generated cases. Use exhaustive enumeration on tiny cases
   as an independent oracle. These are scheduling fixtures, not measured human
   productivity improvements.

Optional local-model capture returns exact source substrings; deterministic
parsers convert supported duration/date phrases and leave unsupported fields
unresolved. No model may invent time, mark a task complete, or publish events.
The UI allows manual entry, text review, bounded calendar import, timetable
inspection, conflict alternatives, locks, and reviewed replanning.

## Scope and delivery order

Implement typed domain contracts and independent validation, then the scheduler
and conflict explanations, then calendar/text adapters, then the ordinary-user
browser experience. Evaluate exact small instances and realistic bounded
scheduling cases before claiming an advantage. Exercise real browser journeys
and Linux/5090 optional extraction on synthetic public notes. Publish source,
tests, raw records, limitations, installation instructions, and real screenshots.

The first release is a trusted local single-person planner. It does not contact
other people, write to a connected calendar, predict how long an unspecified
task takes, or guarantee actual human adherence. Calendar files are imported or
downloaded locally. Existing repositories are not deleted or repackaged into
this project; this is a new implementation for the user's revised audience.
