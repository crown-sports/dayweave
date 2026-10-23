# Use and integration

## Local browser

Recommended: Python 3.12 and `python3 launch.py`, or the bundled Windows/macOS
launcher. The first launch installs dependencies into `.venv`; later launches
reuse it. The browser UI is Chinese. It runs at `http://127.0.0.1:8787` and is
bound to loopback, for one trusted local person. Keep the terminal open.

An editable example has its own time reference. **新建自己的计划** starts a
personal plan, excludes elapsed available time, and does not automatically
claim that old tasks were completed. Review unfinished work, including an
already started task's remaining duration. Completion is always a user action.

The UI displays seven local wall-clock days. The API can schedule up to 28 days;
for a longer plan use JSON/CLI. Daylight-saving repeated times require explicit
offsets in JSON; the wall-clock calendar view is not a repeated-hour timeline.
CLI/export retain unambiguous UTC/offset times.

Save the JSON project before clearing browser data or changing the app's port.
Local storage belongs to a browser and URL origin. **打开项目** restores tasks,
constraints, and prior starts, then requires recalculation; imported result
claims cannot authorize export. Content edits have an in-memory undo stack.
Changing the week shifts availability templates; personal task deadlines and
imported appointments retain their actual dates and need review.

Generated downloads are normal browser links tied to the current local session,
valid for five minutes, with at most eight files in process memory. They are
never saved by the server to arbitrary paths. Browser downloads can be imported
into another calendar manually; no connected-calendar write is performed.

## Text capture

One task per line works without a model:

```text
准备面试 | 90分钟 | 周五18:00前
读书 | 半小时 | 2026-10-11 18:00
买菜 | 时长待估计 | 期限未定
```

Supported effort phrases include whole minutes, `1.5h`, `2 hours`, `半小时`,
`一个半小时`, `一小时`, and `两小时`. Supported deadlines include full ISO dates
with times, 今天/明天/后天, and 本周/这周/下周 weekday forms with an explicit
clock time. `周五` alone stays unresolved; `明天8点` without a period is
ambiguous and stays unresolved, while `明天08:00` is explicit.

Reference dates use the selected timezone. Relative dates from text outside the
selected planning week must be reviewed rather than silently pulled inside it.
Choose drafts to include, fill missing effort, and provide a full deadline or
explicitly permit a week-end target. The review form reads current field values
at confirmation, including the last focused input.

## JSON input and output

```json
{
  "timezone": "Asia/Shanghai",
  "start": "2026-10-05T09:00",
  "end": "2026-10-05T14:00",
  "available": [{"start":"2026-10-05T09:00","end":"2026-10-05T14:00"}],
  "tasks": [
    {"id":"phone","title":"预约电话","duration":60,"release":"2026-10-05T11:00","deadline":"2026-10-05T13:00","priority":5},
    {"id":"study","title":"连续复习","duration":180,"deadline":"2026-10-05T14:00","priority":3}
  ],
  "appointments": [],
  "previous": []
}
```

Durations and optional `chunk` are integer minutes. `required` defaults true.
`priority` is an integer 1–5. `after` lists prerequisite IDs. `locked` pins every
segment start of a required task. `previous` items contain `task`, `part`,
`start`, and `duration`; use returned starts from the earlier plan. An explicit
`not_before` inside the horizon clips future availability and appointments.

```sh
dayweave example sorting --output input.json
dayweave plan input.json --output result.json --calendar plan.ics
```

The example places continuous study at 09:00–12:00 and the telephone task at
12:00–13:00. Earliest-deadline insertion first places the phone at 11:00–12:00,
fragmenting the free interval so the three-hour study task no longer fits.

A result is `scheduled`, `conflict`, or `unknown`. A scheduled result has
validated slots, postponed optional tasks, movement accounting, objective
statuses, timezone, appointments and normalized available windows. `optimal`
means all recorded objective stages were proved optimal. A conflict has a
proved conflicting combination, optional capacity witness, and an explicit
alternative. `unknown` is a bounded-search outcome, not proof of infeasibility.
`--calendar` refuses conflict/unknown results.

## Calendar import/export

Import supports `.ics` files up to 1 MiB, 500 source definitions and 200 expanded
occurrences. Daily, weekly, monthly and yearly recurrences are supported,
including exclusions, individual overrides and cancellations. Transparent
events are ignored. Floating times use the selected timezone; all-day busy
events occupy their stated dates. Fractional minutes round outward with a
warning. More frequent rules and `THISANDFUTURE` range overrides are rejected;
flatten those occurrences in your calendar application first.

Import reads only event titles and times. It follows no remote links or
attachments. Overlapping busy appointments are a conflict requiring your
review, including all-day opaque entries. Mark an event free in the original
calendar or remove its busy entry locally when it is only a date marker.

Export includes scheduled task blocks, preserves complete validated effort,
uses stable task/part UIDs, and does not duplicate imported appointments.
Re-import behavior of another calendar application is its responsibility;
review its update/duplicate options before replacing a previous import.

## Optional local model

The planner works without a model. For prose capture, configure a local
Ollama-compatible endpoint:

```sh
dayweave serve --model-url http://127.0.0.1:11434 --model your-local-model
```

Only local HTTP root addresses are accepted, proxies are disabled, and
redirects are refused. Explicit pipe-separated lines still use deterministic
parsing. Model-assisted prose retains exact quoted fields, exposes rejection,
and requires review; source membership does not guarantee semantic correctness.

The included Hugging Face adapter requires an NVIDIA GPU and separately
downloaded trusted weights. The measured setup used
[Qwen/Qwen3-4B-Instruct-2507](https://huggingface.co/Qwen/Qwen3-4B-Instruct-2507),
revision `cdbee75f17c01a7cc42f958dc650907174af0554`, PyTorch 2.8.0 and
Transformers 4.57.6, on one RTX 5090. It loads local weights with remote-code
execution disabled, uses BF16/SDPA and greedy generation, and serializes
requests. It is a small local development adapter, not a public inference
service.

```sh
python -m pip install '.[model]'
dayweave model-serve --path /your/local/model --port 8788
dayweave serve --model-url http://127.0.0.1:8788 --model Qwen3-4B-Instruct-2507
python benchmarks/evaluate_capture.py --model-url http://127.0.0.1:8788 --model Qwen3-4B-Instruct-2507
```

Model download/setup is optional and takes substantially more disk/memory than
the CPU planner. The supplied evaluation uses synthetic public notes, not user
calendar contents. See raw results rather than assuming all local models have
the same extraction accuracy.

## Browser editing regression check

On main, input editors retain their controls across field changes. The browser
check types with real keyboard events, tabs through fields, clicks directly from
an edit into scheduling, and checks progress, dependency selection and undo.
Its fixed Monday/Friday clocks also cover the default week for a new personal
plan; importing an existing project preserves its dates.

With Node.js and Playwright 1.62.1 installed, run `dayweave serve` in one terminal,
then `node tests/browser_editing.cjs` in another. `DAYWEAVE_URL` selects another
loopback port; `BROWSER_PATH` optionally selects an installed Chromium binary.
The Linux/Python 3.12 CI job runs this check against the installed package.
