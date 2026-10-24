import { test, expect } from "@playwright/test";

async function start(page, role = "wolf") {
  await page.goto("/");
  await expect(page.locator("#scene canvas")).toBeVisible();
  await page.locator("#role-select").selectOption(role);
  await page.getByRole("button", { name: "踏入雾中" }).click();
  await expect(page.locator("#identity")).toBeVisible();
}
async function post(page, path, data) {
  const response = await page.request.post("/api/" + path, {
    data,
    headers: { "X-Mist-Request": "1" },
  });
  if (response.status() !== 409)
    expect(response.ok(), await response.text()).toBeTruthy();
  return response.json();
}

test("入镇、私语、权限、札记、刷新与手机画面", async ({ page }) => {
  const failures = [];
  page.on("pageerror", (e) => failures.push(e.message));
  await page.goto("/");
  await expect(page.locator("#scene canvas")).toBeVisible();
  await expect(page.locator("html")).toHaveAttribute("data-mode", "entering");
  await expect(page.locator("#intro")).toBeVisible();
  await page.screenshot({
    path: "../临时/完整可玩版/网页截图/入镇.png",
    fullPage: true,
  });
  await start(page);
  await expect(page.locator("html")).toHaveAttribute("data-mode", "playing");
  expect(["night", "day"]).toContain(
    await page.locator("html").getAttribute("data-phase"),
  );
  await expect(page.locator("#phase-chip")).toBeVisible();
  await expect(page.locator("#phase-label")).not.toHaveText("");
  await expect(page.locator("#turn-badge")).toBeVisible();
  await page.screenshot({
    path: "../临时/完整可玩版/网页截图/行动可用.png",
    fullPage: true,
  });
  await page.locator("#choice").selectOption("wolf_chat");
  await page
    .locator("#speech")
    .fill("<img src=x onerror=alert(1)> 灯下等你。");
  await page.locator("#submit-action").click();
  await expect(page.locator("#story")).toContainText(
    "<img src=x onerror=alert(1)>",
  );
  await expect(page.locator("#story img")).toHaveCount(0);
  await expect(page.locator("#story .entry.private").first()).toBeVisible();
  await page.screenshot({
    path: "../临时/完整可玩版/网页截图/私密记录.png",
    fullPage: true,
  });
  await page.locator("#assistant-toggle").click();
  await page.locator("#query-kind").selectOption("self_info");
  await page.getByRole("button", { name: "翻阅札记" }).click();
  await expect(page.locator("#answer")).toContainText("夜裔");
  await page.locator("#query-kind").selectOption("speech_hint");
  await page.getByRole("button", { name: "翻阅札记" }).click();
  await expect(page.locator("#use-hint")).toBeVisible();
  await page.screenshot({
    path: "../临时/完整可玩版/网页截图/夜间私语.png",
    fullPage: true,
  });
  const original = await page.evaluate(async () =>
    (await fetch("/api/state")).json(),
  );
  await page.reload();
  await expect(page.locator("#identity")).toContainText("夜裔");
  const restored = await page.evaluate(async () =>
    (await fetch("/api/state")).json(),
  );
  expect(restored.game_id).toBe(original.game_id);
  await page.setViewportSize({ width: 390, height: 844 });
  await page.screenshot({
    path: "../临时/完整可玩版/网页截图/手机对局.png",
    fullPage: true,
  });
  expect(
    await page.evaluate(() => document.documentElement.scrollWidth),
  ).toBeLessThanOrEqual(390);
  expect(failures).toEqual([]);
});
test("从网页开始完整局，行动至结局且展示复盘身份", async ({ page }) => {
  await start(page, "villager");
  await page.locator("#auto").click();
  let state;
  // 浏览器通过正式 HTTP API 操作，离线测试替身只选择最小合法目标。
  for (let i = 0; i < 450; i++) {
    state = await (await page.request.get("/api/state")).json();
    if (state.winner) break;
    const choice =
      state.choices.find((c) => c.tool === "exile_vote") ||
      state.choices.find((c) => c.tool === "abstain");
    if (choice) {
      await post(page, "action", {
        request_id: crypto.randomUUID(),
        phase_id: state.phase_id,
        expected_version: state.version,
        tool: choice.tool,
        payload: choice.targets ? { target: Math.min(...choice.targets) } : {},
      });
    } else await post(page, "advance", {});
  }
  expect(state.winner).toBeTruthy();
  await page.reload();
  await expect(page.locator("#ending")).toBeVisible();
  await expect(page.locator("#action-form")).toBeHidden();
  await expect(page.locator("html")).toHaveAttribute("data-mode", "ended");
  await page.screenshot({
    path: "../临时/完整可玩版/网页截图/结局.png",
    fullPage: true,
  });
  expect(state.players.every((p) => p.role)).toBe(true);
});
test("暗牌、可见目标与断线提示", async ({ page }) => {
  await start(page, "seer");
  await page.locator("#auto").click();
  for (let i = 0; i < 8; i++) {
    const state = await post(page, "advance", {});
    if (state.choices.some((c) => c.tool === "inspect")) break;
  }
  await page.reload();
  await expect(page.locator("#choice")).toContainText("向星空询问");
  await page.locator("#choice").selectOption("inspect");
  await expect(page.locator('#target option[value="1"]')).toHaveCount(0);
  const roleLabels = await page.locator("#roster small").allTextContents();
  expect(roleLabels.filter((t) => t === "观星者")).toHaveLength(1);
  await page.route("**/api/action", (route) => route.abort());
  await page.locator("#submit-action").click();
  await expect(page.locator("#error")).toBeVisible();
  await expect(page.locator("html")).toHaveAttribute("data-error", "network");
  await page.screenshot({
    path: "../临时/完整可玩版/网页截图/断线提示.png",
    fullPage: true,
  });
  await expect(page.locator("#submit-action")).toBeEnabled();
});

test("减少动效：系统偏好减少动效时仍可入镇、行动并恢复", async ({
  page,
}) => {
  const failures = [];
  page.on("pageerror", (e) => failures.push(e.message));
  await page.emulateMedia({ reducedMotion: "reduce" });
  await page.goto("/");
  await expect(page.locator("html")).toHaveAttribute("data-motion", "reduced");
  await expect(page.locator("#scene canvas")).toBeVisible();
  await start(page, "wolf");
  await page.locator("#choice").selectOption("wolf_chat");
  await page.locator("#speech").fill("雾里先听，不急着开口。");
  await page.locator("#submit-action").click();
  await expect(page.locator("#story")).toContainText("雾里先听");
  await page.reload();
  await expect(page.locator("#identity")).toBeVisible();
  await expect(page.locator("#scene canvas")).toBeVisible();
  expect(failures).toEqual([]);
});
