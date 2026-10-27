import { test, expect } from "@playwright/test";

const WORLDS = ["mist", "hyperion", "threebody", "tidal_archive"];

async function enter(page) {
  await page.goto("/");
  await expect(page.locator("#scene canvas")).toBeVisible();
  await page.getByRole("button", { name: "踏入雾中" }).click();
  await expect(page.locator("#identity")).toBeVisible();
}

test("四世界场景布局、十二席与手机宽度", async ({ page }) => {
  const failures = [];
  page.on("pageerror", (error) => failures.push(error.message));
  await page.route("**/api/advance", async (route) => {
    const response = await page.request.get("/api/state");
    await route.fulfill({ response });
  });
  await enter(page);
  for (const world of WORLDS) {
    const response = await page.request.post("/api/game", {
      data: { role: "villager", worldbook: world },
      headers: { "X-Mist-Request": "1" },
    });
    expect(response.ok(), await response.text()).toBe(true);
    await page.reload();
    await expect(page.locator("#scene")).toHaveAttribute("data-layout", world);
    await expect(page.locator("#roster .person")).toHaveCount(12);
  }
  await page.setViewportSize({ width: 390, height: 844 });
  await page.reload();
  await expect(page.locator("#scene")).toHaveAttribute(
    "data-layout",
    "tidal_archive",
  );
  const width = await page.evaluate(
    () => document.documentElement.scrollWidth,
  );
  expect(width).toBeLessThanOrEqual(390);
  expect(failures).toEqual([]);
});

test.describe("减少动效", () => {
  test.use({ reducedMotion: "reduce" });

  test("场景仍显示十二席与静态状态标记", async ({ page }) => {
    const failures = [];
    page.on("pageerror", (error) => failures.push(error.message));
    await enter(page);
    await expect(page.locator("#scene")).toHaveAttribute("data-layout", "mist");
    await expect(page.locator("#roster .person")).toHaveCount(12);
    expect(failures).toEqual([]);
  });
});

// 这里固定合法公开视图的形状，只检验渲染/交互，不把fixture当真实模型思考。
test("真实表情图集随神态换帧，跨阶段旧发言不误亮，点击只同步合法目标", async ({ page }) => {
  await page.goto("/");
  await page.request.post("/api/enter", {
    data: { password: "" }, headers: { "X-Mist-Request": "1" },
  });
  const screenshots = [];
  let rendered;
  await page.route(/\/api\/(state|advance)$/, (route) => route.fulfill({ json: rendered }));
  for (const world of WORLDS) {
    const response = await page.request.post("/api/game", {
      data: { role: "villager", worldbook: world }, headers: { "X-Mist-Request": "1" },
    });
    const original = await response.json();
    const speech = { id: 991, actor: 2, speaker: `2号 · ${original.players[1].name}`,
      round: 1, text: "我先核对公开证词。", private: false, effect: null,
      is_speech: true, phase_id: "scene-speech" };
    const choices = [{ tool: "exile_vote", label: "决定谁离开", targets: [2, 3, 4] }];
    rendered = { ...original, phase: "day_speech", phase_id: "scene-speech", night: false, choices, story: [] };
    const captures = [];
    for (const state of ["neutral", "speaking", "thinking"]) {
      rendered = { ...rendered, story: state === "speaking" ? [speech] : [], choices: state === "thinking" ? [] : choices };
      await page.reload();
      await page.locator("#roster .person").nth(1).click();
      await expect(page.locator("#scene-focus")).toHaveAttribute("data-expression", state);
      await expect(page.locator("#scene-focus-name")).toContainText(original.players[1].name);
      const face = page.locator(".scene-focus__face");
      await face.locator("img").evaluate((image) => image.decode());
      captures.push(await face.screenshot());
    }
    expect(captures[0].equals(captures[1]), `${world}平静/发言应为不同真实图片`).toBe(false);
    expect(captures[1].equals(captures[2]), `${world}发言/思索应为不同真实图片`).toBe(false);
    screenshots.push(world);

    rendered = { ...rendered, phase: "exile_vote", phase_id: "scene-vote", choices, story: [speech] };
    await page.reload();
    await expect(page.locator("#scene")).toHaveAttribute("data-speaking", "");
    await expect(page.locator("#scene-focus-state")).toHaveText("表决中的思索");
    await page.locator("#target").selectOption("3");
    await page.locator("#roster .person").nth(1).click();
    await expect(page.locator("#target")).toHaveValue("2");
    await page.locator("#roster .person").nth(6).click();
    await expect(page.locator("#scene-focus")).toHaveAttribute("data-seat", "7");
    await expect(page.locator("#target")).toHaveValue("2");
    await page.locator("#roster .person").nth(2).focus();
    await page.keyboard.press("Enter");
    await expect(page.locator("#target")).toHaveValue("3");
  }
  expect(screenshots).toHaveLength(4);
});
