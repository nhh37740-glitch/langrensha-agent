import { test, expect } from "@playwright/test";
import { mkdirSync } from "node:fs";

const SHOTS =
  process.env.STORY_NARRATOR_SHOTS ||
  "../临时/世界书视觉Issue/验证证据/叙事标签";
mkdirSync(SHOTS, { recursive: true });

const WORLDS = [
  { id: "mist", name: "雾钟镇", narrator: "钟楼记事" },
  { id: "hyperion", name: "海伯利安", narrator: "营地纪事" },
  { id: "threebody", name: "三体", narrator: "站内记录" },
  { id: "tidal_archive", name: "潮汐档案馆", narrator: "馆内潮记" },
];
const HEADERS = { "X-Mist-Request": "1" };

async function openEntry(page) {
  await page.goto("/");
  await expect(page.locator("#scene canvas")).toBeVisible();
  await expect(page.locator("#world-list")).toHaveAttribute("aria-busy", "false");
  await expect(page.locator("#world-list .world-card")).toHaveCount(4);
}

async function post(page, path, data) {
  const response = await page.request.post("/api/" + path, {
    data,
    headers: HEADERS,
  });
  expect(response.ok(), await response.text()).toBeTruthy();
  return response.json();
}

async function expectNoHorizontalOverflow(page) {
  const metrics = await page.evaluate(() => ({
    viewport: document.documentElement.clientWidth,
    scroll: document.documentElement.scrollWidth,
  }));
  expect(metrics.viewport).toBeLessThanOrEqual(390);
  expect(metrics.scroll).toBeLessThanOrEqual(390);
}

test("公开目录四世界都带叙事标签", async ({ page }) => {
  const catalog = await (await page.request.get("/api/worldbooks")).json();
  for (const world of WORLDS) {
    const book = catalog.worldbooks.find((item) => item.id === world.id);
    expect(book, `${world.name} 应在公开目录中`).toBeTruthy();
    expect(book.narrator).toBe(world.narrator);
  }
});

for (const world of WORLDS) {
  test(`${world.name}：选择、入局与刷新后叙事标签一致`, async ({ page }) => {
    const failures = [];
    page.on("pageerror", (error) => failures.push(error.message));
    await openEntry(page);

    await page.locator(`.world-card[data-world-id="${world.id}"]`).click();
    await expect(page.locator("#story-narrator")).toBeVisible();
    await expect(page.locator("#story-narrator")).toHaveText(world.narrator);

    await post(page, "enter", { password: "" });
    const state = await post(page, "game", {
      role: "villager",
      worldbook: world.id,
    });
    expect(state.worldbook).toBe(world.id);
    expect(state.narrator).toBe(world.narrator);

    // 入局与刷新都保持世界标签，不只依赖选择页目录。
    await page.reload();
    await expect(page.locator("#identity")).toBeVisible();
    await expect(page.locator("#story-narrator")).toHaveText(world.narrator);
    await expect(page.locator("html")).toHaveAttribute("data-world", world.id);

    await page.reload();
    await expect(page.locator("#identity")).toBeVisible();
    await expect(page.locator("#story-narrator")).toHaveText(world.narrator);

    await page.screenshot({
      path: `${SHOTS}/叙事标签-${world.id}-桌面.png`,
      fullPage: true,
    });
    expect(failures).toEqual([]);
  });
}

test("390px 手机：四世界叙事标签与页面无横向溢出", async ({ page }) => {
  const failures = [];
  page.on("pageerror", (error) => failures.push(error.message));
  await page.setViewportSize({ width: 390, height: 844 });
  await openEntry(page);
  await expectNoHorizontalOverflow(page);

  for (const world of WORLDS) {
    await page.locator(`.world-card[data-world-id="${world.id}"]`).click();
    await expect(page.locator("#story-narrator")).toHaveText(world.narrator);
    await expectNoHorizontalOverflow(page);
  }

  await post(page, "enter", { password: "" });
  await post(page, "game", { role: "villager", worldbook: "tidal_archive" });
  await page.reload();
  await expect(page.locator("#identity")).toBeVisible();
  await expect(page.locator("#story-narrator")).toHaveText("馆内潮记");
  await expectNoHorizontalOverflow(page);
  await page.screenshot({
    path: `${SHOTS}/叙事标签-tidal_archive-手机390.png`,
    fullPage: true,
  });
  expect(failures).toEqual([]);
});
