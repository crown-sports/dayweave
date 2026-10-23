# When a plan does not fit

## Check the inputs before changing priorities

Start with the hours you can actually use. Then check each task's duration,
deadline, prerequisites and whether it may be split. A three-hour task cannot
use two separate ninety-minute gaps unless its split rule permits that.
Appointments remove time from availability. [Input format and examples](usage.md).

The overload example asks for **240 minutes** inside **180 available minutes**.
The proposed postponement changes the plan only after confirmation. If a solver
times out, the result is unknown; it is not proof that the tasks cannot fit.

## Record progress before replanning

For a 90-minute draft with 30 minutes completed, enter **30** in the cumulative
completed-work field. The next plan needs 60 minutes for the draft and 30 for
its dependent review. Entering progress is explicit: no timer or activity monitor
updates it for you. [Example input](../examples/partial-progress.json).

Pin times that must remain fixed. Otherwise the solver accounts for movement
from the previous plan while satisfying the updated constraints. Check the new
timetable before exporting it. [Progress tests](../tests/test_progress.py).

## How the result is checked

OR-Tools CP-SAT places tasks within available intervals, with deadlines,
prerequisites and split rules. A separate checker validates the returned schedule
before calendar export. The published 48-case benchmark uses synthetic fixtures;
it measures feasible scheduling, not the time people save.
[Algorithm](algorithms.md) · [Results and failures](results.md).

Use **保存项目** for a JSON backup. Calendar export creates a local `.ics` file;
import it into your calendar yourself. Supported recurrence rules and data
storage details are in [usage](usage.md).

[Recreate the README screenshot](screenshots.md). The pictured planner is v0.2.1;
this documentation update does not change the scheduling code.
