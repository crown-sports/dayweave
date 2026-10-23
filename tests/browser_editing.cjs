/** Real keyboard/click regression: start `dayweave serve`, then run with Playwright installed. */
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const { chromium } = require("playwright");

(async () => {
  const browser = await chromium.launch({
    headless: true,
    ...(process.env.BROWSER_PATH ? { executablePath: process.env.BROWSER_PATH } : {}),
  });
  try {
    const page = await browser.newPage({ viewport: { width: 1440, height: 1100 } });
    // A personal plan uses the clock; keep this regression independent of the day it runs.
    await page.addInitScript(() => { Date.now = () => Date.parse("2026-10-19T01:00:00Z"); });
    const errors = [];
    page.on("pageerror", (error) => errors.push(error.message));
    const saved = () => page.evaluate(() => JSON.parse(localStorage.getItem("dayweave.project.v1")));
    const focused = () => page.evaluate(() => document.activeElement.getAttribute("aria-label"));
    async function type(locator, value) {
      await locator.click();
      await page.keyboard.press("ControlOrMeta+A");
      await page.keyboard.type(value);
    }
    await page.goto(process.env.DAYWEAVE_URL || "http://127.0.0.1:8787");
    await page.waitForSelector("#tasks .task-card");
    await page.locator("#new-project").click();
    await page.waitForFunction(() => document.querySelectorAll("#tasks .task-card").length === 0);
    assert.equal((await saved()).start.slice(0, 10), "2026-10-19", "Monday stays in this week");
    await page.locator("#add-task").click();
    await type(page.getByLabel("事项名称", { exact: true }), "Draft A");
    await page.keyboard.press("Tab");
    assert.equal(await focused(), "预计时长（分钟）", "Tab must keep moving after a title commit");
    await page.keyboard.type("90");
    await page.keyboard.press("Tab");
    assert.equal(await focused(), "重要程度");
    await page.keyboard.press("Tab");
    assert.equal(await focused(), "已完成工时（分钟，累计）");
    await page.keyboard.press("ControlOrMeta+A");
    await page.keyboard.type("30");
    await page.keyboard.press("Tab");
    assert.equal(await focused(), "最早开始（可留空）");
    assert.equal((await saved()).tasks[0].completed_minutes, 30);

    // A blur commit must not remove the node receiving the user's next click.
    await type(page.getByLabel("事项名称", { exact: true }), "Draft A revised");
    await page.getByLabel("预计时长（分钟）", { exact: true }).click();
    assert.equal(await focused(), "预计时长（分钟）");
    await page.keyboard.press("ControlOrMeta+A");
    await page.keyboard.type("60");
    await page.locator("#add-task").click();
    assert.equal(await page.locator("#tasks .task-card").count(), 2);
    assert.equal((await saved()).tasks[0].duration, 60);
    const secondName = page.getByLabel("事项名称", { exact: true }).nth(1);
    await type(secondName, "Draft A revised");
    await page.keyboard.press("Tab");
    assert.equal(await focused(), "预计时长（分钟）");
    await page.keyboard.type("30");
    await page.keyboard.press("Tab");
    const firstId = (await saved()).tasks[0].id;
    await page.getByLabel("必须先完成", { exact: true }).nth(1).selectOption(firstId);
    await type(secondName, "Review final");
    await page.locator("#solve").click();
    await page.waitForFunction(() => !document.getElementById("export").disabled);
    let project = await saved();
    assert.equal(project.tasks[0].title, "Draft A revised");
    assert.equal(project.tasks[1].title, "Review final");
    assert.deepEqual(project.tasks[1].after, [firstId]);
    assert.equal(project.result.slots.reduce((total, slot) => total + slot.duration, 0), 60);

    await type(page.getByLabel("已完成工时（分钟，累计）", { exact: true }).first(), "60");
    await page.keyboard.press("Tab");
    assert(await page.locator("#export").isDisabled(), "Editing must invalidate export");
    project = await saved();
    assert.equal(project.tasks[0].done, true);
    assert(!await page.getByLabel("必须先完成", { exact: true }).nth(1)
      .locator(`option[value="${firstId}"]`).count(), "Completed parents leave the selector");
    await page.locator("#undo").click();
    project = await saved();
    assert.equal(project.tasks[0].completed_minutes, 30, "Undo must restore the prior task object");
    await type(page.getByLabel("事项名称", { exact: true }).nth(1), "Review after undo");
    await page.locator("#solve").click();
    await page.waitForFunction(() => !document.getElementById("export").disabled);
    assert.equal((await saved()).tasks[1].title, "Review after undo", "Handlers must use the restored project");
    assert.deepEqual(errors, []);
    if (process.env.ARTIFACT_DIR) {
      fs.mkdirSync(process.env.ARTIFACT_DIR, { recursive: true });
      await page.screenshot({ path: path.join(process.env.ARTIFACT_DIR, "keyboard-plan.png"), fullPage: true });
      fs.writeFileSync(path.join(process.env.ARTIFACT_DIR, "keyboard-project.json"), JSON.stringify(await saved(), null, 2));
    }
    const evening = await browser.newPage();
    await evening.addInitScript(() => { Date.now = () => Date.parse("2026-10-23T13:34:00Z"); });
    await evening.goto(process.env.DAYWEAVE_URL || "http://127.0.0.1:8787");
    await evening.waitForSelector("#tasks .task-card");
    const originalExample = await evening.evaluate(() => JSON.parse(localStorage.getItem("dayweave.project.v1")));
    assert.equal(originalExample.start.slice(0, 10), "2026-10-19", "An existing example keeps its date");
    await evening.locator("#new-project").click();
    await evening.waitForFunction(() => document.querySelectorAll("#tasks .task-card").length === 0);
    const nextWeek = await evening.evaluate(() => JSON.parse(localStorage.getItem("dayweave.project.v1")));
    assert.equal(nextWeek.start.slice(0, 10), "2026-10-26");
    assert.equal(nextWeek.end.slice(0, 10), "2026-11-02");
    assert.match(await evening.locator("#notice").innerText(), /已创建下周计划/);
    assert.match(await evening.locator("#week-label").innerText(), /10月26日/);
    assert.equal(nextWeek.example, false);
    if (process.env.ARTIFACT_DIR)
      await evening.screenshot({ path: path.join(process.env.ARTIFACT_DIR, "friday-new-week.png") });
    // Import keeps its explicit date; only newProject advances a week.
    await evening.locator("#project-file").setInputFiles({
      name: "existing-project.json", mimeType: "application/json",
      buffer: Buffer.from(JSON.stringify(originalExample)),
    });
    await evening.waitForSelector("#tasks .task-card");
    const loaded = await evening.evaluate(() => JSON.parse(localStorage.getItem("dayweave.project.v1")));
    assert.equal(loaded.start.slice(0, 10), "2026-10-19");
    console.log("PASS: keyboard Tab, click after blur, duplicate labels, progress, dependencies, direct solve, undo and fixed Monday/Friday clocks");
  } finally {
    await browser.close();
  }
})().catch((error) => { console.error(error); process.exitCode = 1; });
