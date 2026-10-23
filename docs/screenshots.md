# Recreate the remaining-work screenshot

The README shows the actual v0.2.1 browser planner. The input is
[partial-project.json](assets/partial-project.json), copied from
[the CLI fixture](../examples/partial-progress.json) with `example: true` so its
fixed date stays usable. No schedule result is prefilled.

1. Run `dayweave serve --port 8787` and open `http://127.0.0.1:8787`.
2. Choose **打开项目** and open `docs/assets/partial-project.json` from a main checkout.
3. Click **安排这一周**. The draft has 60 of 90 minutes remaining; review needs 30.
4. Check **2/2**, **1.5 小时**, draft **10:00–11:00**, review **11:00–11:30**.

The committed image is a Chromium screenshot at a **1100 × 1000** viewport,
capturing the workspace rectangle **x=24, y=220, width=1052, height=680**. This
keeps the remaining-work fields and timetable readable instead of shrinking the
whole page. No content or styling was changed for the screenshot.

The second README image, `overload.jpg`, is the existing built-in overload
example. It illustrates 240 required minutes inside 180 available minutes.
