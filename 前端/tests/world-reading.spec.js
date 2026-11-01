import { test, expect } from "@playwright/test";

const headers = { "X-Mist-Request": "1" };
const shots = "../临时/完整可玩版/网页截图";

test("独立世界入口、长篇正文、跨世界会话与刷新恢复", async ({ page }) => {
  const errors = [];
  page.on("pageerror", (error) => errors.push(error.message));
  await page.route("**/api/advance", async (route) => {
    await route.fulfill({ response: await page.request.get("/api/state") });
  });
  await page.goto("/");
  await expect(page.locator("#world-picker")).toBeVisible();
  await expect(page.locator("#intro")).toBeHidden();
  await expect(page.locator("#scene canvas")).toHaveCount(0);
  await expect(page.locator("#world-list .world-cover__photo")).toHaveCount(4);
  await expect.poll(() => page.locator("#world-list .world-cover__photo").evaluateAll(
    (images) => images.every((image) => image.complete && image.naturalWidth > 0),
  )).toBe(true);
  await page.screenshot({ path: `${shots}/独立世界目录.png`, fullPage: true });
  for (const world of ["mist", "hyperion", "threebody", "tidal_archive"]) {
    await page.goto("/");
    await page.locator(`.world-card[data-world-id="${world}"]`).click();
    await expect(page).toHaveURL(new RegExp(`/world/${world}$`));
    await expect(page.locator("#world-picker")).toBeHidden();
    await expect(page.locator("#reading-chapter option")).toHaveCount(1);
    await expect(page.locator("#reading-text p")).toHaveCount(6);
    expect((await page.locator("#reading-text").innerText()).length).toBeGreaterThan(500);
    await page.locator("#reading-panel").scrollIntoViewIfNeeded();
    await page.screenshot({ path: `${shots}/世界阅读-${world}.png`, fullPage: false });
  }
  await page.goto("/world/threebody");
  await page.locator("#role-select").selectOption("seer");
  await page.getByRole("button", { name: "踏入雾中" }).click();
  await expect(page.locator("#identity")).toBeVisible();
  await expect(page.locator("#reading-chapter option")).toHaveCount(3);
  await page.locator("#reading-chapter").selectOption("world:threebody:story:letter:seer");
  await expect(page.locator("#reading-meta")).toHaveText("你的身份手记，仅本人可见");
  const original = await (await page.request.get("/api/state")).json();
  await page.locator("#back-worlds").click();
  await expect(page.locator("#resume-link")).toHaveAttribute("href", "/world/threebody");
  let advances = 0;
  const count = (request) => { if (request.url().endsWith("/api/advance")) advances += 1; };
  page.on("request", count);
  await page.waitForTimeout(1500);
  page.off("request", count);
  expect(advances).toBe(0);
  await page.locator('.world-card[data-world-id="hyperion"]').click();
  await expect(page.locator("#resume-note")).toContainText("三体");
  await expect(page.locator("#intro")).toBeVisible();
  await expect(page.locator("#identity")).toBeHidden();
  await expect(page.locator("#reading-chapter option")).toHaveCount(1);
  const untouched = await (await page.request.get("/api/state")).json();
  expect([untouched.game_id, untouched.version]).toEqual([original.game_id, original.version]);
  await page.reload();
  await expect(page.locator("html")).toHaveAttribute("data-world", "hyperion");
  await page.locator("#resume-link").click();
  await expect(page.locator("#identity")).toBeVisible();
  await expect(page.locator("#role-title")).toContainText("监听员");
  await page.locator("#new-story").click();
  await expect(page.locator("#intro")).toBeVisible();
  await page.reload();
  await expect(page.locator("#identity")).toBeVisible();
  expect((await (await page.request.get("/api/state")).json()).game_id).toBe(original.game_id);
  await page.setViewportSize({ width: 390, height: 844 });
  await page.locator("#reading-chapter").selectOption("world:threebody:story:letter:seer");
  await page.locator("#reading-panel").scrollIntoViewIfNeeded();
  expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBeLessThanOrEqual(390);
  await page.screenshot({ path: `${shots}/世界阅读-手机私密手记.png`, fullPage: false });
  expect(errors).toEqual([]);
});

test("跨世界新局后旧页面停止自动推进", async ({ page }) => {
  await page.goto("/world/threebody");
  await page.locator("#role-select").selectOption("seer");
  await page.getByRole("button", { name: "踏入雾中" }).click();
  await expect(page.locator("#identity")).toBeVisible();
  await expect(page.locator("#waiting")).toBeVisible();
  await page.locator("#auto").click();
  await expect(page.locator("html")).toHaveAttribute("data-busy", "no");
  let created;
  for (let attempt = 0; attempt < 5; attempt += 1) {
    created = await page.request.post("/api/game", {
      data: { role: "villager", worldbook: "hyperion" },
      headers,
    });
    if (created.ok()) break;
    await page.waitForTimeout(300);
  }
  expect(created.ok()).toBe(true);
  let advances = 0;
  const count = (request) => {
    if (request.url().endsWith("/api/advance")) advances += 1;
  };
  page.on("request", count);
  await page.locator("#auto").click();
  await page.waitForTimeout(3500);
  page.off("request", count);
  expect(advances).toBeLessThanOrEqual(1);
  await expect(page.locator("#resume-note")).toContainText("海伯利安");
  await expect(page.locator("#waiting")).toBeHidden();
  await expect(page.locator("#intro")).toBeVisible();
  await expect(page.locator("#identity")).toBeHidden();
  await expect(page.locator("#action-form")).toBeHidden();
  await expect(page.locator("#reading-chapter option")).toHaveCount(1);
});

test("阅读请求失败可重试，未知世界返回404", async ({ page }) => {
  await page.route("**/api/reading/mist", (route) => route.abort());
  await page.goto("/world/mist");
  await expect(page.locator("#reading-status")).toContainText("请重试");
  await page.unroute("**/api/reading/mist");
  await page.locator("#reading-retry").click();
  await expect(page.locator("#reading-chapter option")).toHaveCount(1);
  expect((await page.request.get("/world/no-such-book")).status()).toBe(404);
  expect((await page.request.get("/api/reading/no-such-book")).status()).toBe(404);
  // Query parameters cannot grant a private role before a real session exists.
  const response = await page.request.get("/api/reading/mist?role=wolf", { headers });
  expect((await response.json()).chapters.some((chapter) => chapter.private)).toBe(false);
});
