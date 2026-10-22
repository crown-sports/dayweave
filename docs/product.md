# Product fit and evidence

The intended user is one person balancing study, job hunting or daily tasks
against limited hours. The question is “what fits, and what must I change?”
The output is a checked timetable or a conflict to resolve. This scenario is
inferred from the product; no user study or measured productivity gain is claimed.

## What makes the workflow useful

| Compared with manually sorting a to-do list | Inspectable evidence | Limit |
| --- | --- | --- |
| Fit complete effort around deadlines, prerequisites and appointments | [Scheduling tests](../tests/test_scheduling.py), [oracle and baseline results](results.md) | Uses estimated durations; bounded solve may return unknown |
| Replan while accounting for movement of existing tasks | [Scheduling tests](../tests/test_scheduling.py), [replanning fixtures](results.md) | Synthetic cases are not a comparison with commercial planners |
| Schedule remaining effort after explicit progress updates | [Progress tests](../tests/test_progress.py), [90-minute example](../examples/partial-progress.json) | No automatic time tracking or inference of completion |
| Independently check schedules before export | [Checker and solver model](algorithms.md), [calendar tests](../tests/test_capture_calendar.py) | Passing checks does not guarantee that a person follows the plan |

OR-Tools supplies the established solver. The integration of constraints,
conflict explanations, movement accounting and independent checking is the
current implementation value. The source is copyable; it is not evidence of a
proprietary scheduling algorithm or an established business moat.

## What to validate next

1. Observe new users trying the example, creating their own week and explaining
   why a conflict occurred. Measure where they fail before adding more controls.
2. With consent, collect minimal anonymous reproductions of confusing schedules,
   estimate changes and calendar imports. Preserve failures in regression tests.
3. Test whether people can update progress and reuse plans over several weeks.
   This would inform workflow fit; current solver benchmarks cannot answer it.

A well-maintained calendar compatibility suite and real usability evidence could
accumulate over time. No retention, time-saving or cross-calendar reliability
statistics have been established. Team scheduling, reminders and automatic
calendar writes remain outside this release. See [usage and data boundaries](usage.md).

## Version availability

This guide is included in v0.2.1. The existing browser examples and
partial-progress fixture also run in v0.2.0. The v0.2.1 patch updates the browser
version label and documentation; scheduling behavior is unchanged.
