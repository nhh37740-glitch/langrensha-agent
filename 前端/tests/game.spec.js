import { test, expect } from "@playwright/test";

const SHOTS = "../临时/完整可玩版/网页截图";

async function openEntry(page) {
  await page.goto("/");
  await expect(page.locator("#scene canvas")).toBeVisible();
  await expect(page.locator("#world-picker")).toBeVisible();
  await expect(page.locator("#debug-toggle")).toHaveAttribute(
    "aria-pressed",
    "true",
  );
  await expect(page.locator("#debug-panel")).toBeHidden();
  await expect(page.locator("#world-list")).toHaveAttribute(
    "aria-busy",
    "false",
  );
  await expect(page.locator("#world-list .world-card")).toHaveCount(4);
}

async function start(page, role = "wolf") {
  await openEntry(page);
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
    path: `${SHOTS}/入镇.png`,
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
    path: `${SHOTS}/行动可用.png`,
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
    path: `${SHOTS}/私密记录.png`,
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
    path: `${SHOTS}/夜间私语.png`,
    fullPage: true,
  });
  await expect(page.locator("#query-warning")).toBeHidden();
  await page.locator("#query-kind").selectOption("ask_world");
  await page.locator("#query-text").fill("铜铃");
  await page.getByRole("button", { name: "翻阅札记" }).click();
  await expect(page.locator("#query-warning")).toBeVisible();
  await expect(page.locator("#query-warning")).toContainText("关键词");
  await expect(page.locator("#answer")).toContainText("铜铃");
  await page.screenshot({
    path: `${SHOTS}/语义降级提示.png`,
    fullPage: true,
  });
  await page.locator("#query-kind").selectOption("self_info");
  await page.getByRole("button", { name: "翻阅札记" }).click();
  await expect(page.locator("#query-warning")).toBeHidden();
  await expect(page.locator("#answer")).toContainText("夜裔");
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
    path: `${SHOTS}/手机对局.png`,
    fullPage: true,
  });
  expect(
    await page.evaluate(() => document.documentElement.scrollWidth),
  ).toBeLessThanOrEqual(390);
  expect(failures).toEqual([]);
});

test("四本世界可选、选择真实生效、刷新后主题一致", async ({ page }) => {
  const failures = [];
  page.on("pageerror", (e) => failures.push(e.message));
  await openEntry(page);

  const catalog = await (await page.request.get("/api/worldbooks")).json();
  expect(catalog.worldbooks).toHaveLength(4);
  const hyperion = catalog.worldbooks.find((book) => book.id === "hyperion");
  expect(hyperion).toBeTruthy();

  await expect(
    page.locator('.world-card[data-world-id="mist"]'),
  ).toHaveAttribute("aria-pressed", "true");
  await expect(page.locator("html")).toHaveAttribute("data-world", "mist");
  await page.screenshot({
    path: `${SHOTS}/世界书-四本可选.png`,
    fullPage: true,
  });

  await page.locator('.world-card[data-world-id="hyperion"]').click();
  await expect(
    page.locator('.world-card[data-world-id="hyperion"]'),
  ).toHaveAttribute("aria-pressed", "true");
  await expect(page.locator("html")).toHaveAttribute(
    "data-world",
    "hyperion",
  );
  await expect(page.locator("#world-detail")).toBeVisible();
  await expect(page.locator("#world-detail-name")).toHaveText(hyperion.name);
  await expect(page.locator("#brand-name")).toHaveText(hyperion.name);
  await expect(page.locator("#scene-eyebrow")).toHaveText(
    hyperion.scene.eyebrow,
  );
  await expect(page.locator("#intro-lead")).toHaveText(hyperion.scene.intro);
  await expect(page.locator("#day")).toHaveText(`${hyperion.name} · 初至`);
  await expect(page.locator("#story-title")).toHaveText(
    hyperion.scene.chapter,
  );
  await expect(page.locator("#chapter-caption")).toContainText(
    hyperion.scene.caption,
  );
  await expect(
    page.locator('#role-select option[value="wolf"]'),
  ).toContainText(hyperion.role_labels.wolf);
  await page.screenshot({
    path: `${SHOTS}/世界书-选择海伯利安.png`,
    fullPage: true,
  });

  await page.locator("#role-select").selectOption("wolf");
  const [request] = await Promise.all([
    page.waitForRequest(
      (r) => r.url().includes("/api/game") && r.method() === "POST",
    ),
    page.getByRole("button", { name: "踏入雾中" }).click(),
  ]);
  expect(request.postDataJSON()).toEqual({
    role: "wolf",
    worldbook: "hyperion",
  });
  await expect(page.locator("#identity")).toBeVisible();
  await expect(page.locator("html")).toHaveAttribute(
    "data-world",
    "hyperion",
  );
  await expect(page.locator("#brand-name")).toHaveText(hyperion.name);
  await expect(page.locator("#role-title")).toContainText(
    hyperion.role_labels.wolf,
  );
  const state = await (await page.request.get("/api/state")).json();
  expect(state.worldbook).toBe("hyperion");
  await expect(page.locator("#chapter")).toHaveText(state.chapter);
  await expect(page.locator("#story-title")).toHaveText(state.chapter);
  await expect(page.locator("#day")).toContainText(
    state.night ? "冢夜" : "白昼",
  );
  await expect(page.locator("#phase-label")).toContainText(
    state.night ? "冢夜" : "白昼",
  );
  await expect(page.locator("#waiting-text")).toContainText("冢影中");
  await page.screenshot({
    path: `${SHOTS}/世界书-海伯利安对局.png`,
    fullPage: true,
  });

  await page.reload();
  await expect(page.locator("#identity")).toBeVisible();
  await expect(page.locator("html")).toHaveAttribute(
    "data-world",
    "hyperion",
  );
  await expect(page.locator("#brand-name")).toHaveText(hyperion.name);
  await expect(page.locator("#role-title")).toContainText(
    hyperion.role_labels.wolf,
  );
  await expect(page.locator("#chapter")).toHaveText(state.chapter);
  expect(await page.locator("#scene-title").innerText()).toContain(
    hyperion.scene.title[0].slice(0, 4),
  );
  const restored = await page.evaluate(async () =>
    (await fetch("/api/state")).json(),
  );
  expect(restored.game_id).toBe(state.game_id);
  await page.screenshot({
    path: `${SHOTS}/世界书-刷新后一致.png`,
    fullPage: true,
  });
  await expect(page.locator("#world-picker")).toBeHidden();
  page.once("dialog", (dialog) => dialog.accept());
  await page.locator("#reset").click();
  await expect(page.locator("#world-picker")).toBeVisible();
  await expect(page.locator("#world-list .world-card")).toHaveCount(4);
  await expect(page.locator("#brand-name")).toHaveText(hyperion.name);
  await expect(page.locator("#day")).toHaveText(`${hyperion.name} · 初至`);
  await expect(page.locator("#story-title")).toHaveText(
    hyperion.scene.chapter,
  );
  expect(failures).toEqual([]);
});

test("390px 下世界卡可键盘选择并入镇", async ({ page }) => {
  const failures = [];
  page.on("pageerror", (e) => failures.push(e.message));
  await page.setViewportSize({ width: 390, height: 844 });
  await openEntry(page);
  expect(
    await page.evaluate(() => document.documentElement.scrollWidth),
  ).toBeLessThanOrEqual(390);

  const card = page.locator('.world-card[data-world-id="tidal_archive"]');
  await card.focus();
  await page.keyboard.press("Enter");
  await expect(card).toHaveAttribute("aria-pressed", "true");
  await expect(page.locator("html")).toHaveAttribute(
    "data-world",
    "tidal_archive",
  );
  await expect(page.locator("#world-detail-name")).toHaveText("潮汐档案馆");
  const box = await card.boundingBox();
  expect(box.x).toBeGreaterThanOrEqual(0);
  expect(box.x + box.width).toBeLessThanOrEqual(390);
  await page.locator("#world-picker").scrollIntoViewIfNeeded();
  await page.screenshot({
    path: `${SHOTS}/世界书-手机选择.png`,
    fullPage: false,
  });

  await page.locator("#role-select").selectOption("seer");
  await page.getByRole("button", { name: "踏入雾中" }).click();
  await expect(page.locator("#identity")).toBeVisible();
  await expect(page.locator("html")).toHaveAttribute(
    "data-world",
    "tidal_archive",
  );
  await expect(page.locator("#role-title")).toContainText("验潮员");
  await expect(page.locator("#waiting-text")).toContainText("潮声里");
  expect(
    await page.evaluate(() => document.documentElement.scrollWidth),
  ).toBeLessThanOrEqual(390);
  await page.screenshot({
    path: `${SHOTS}/世界书-手机入镇.png`,
    fullPage: true,
  });
  expect(failures).toEqual([]);
});

test("世界书目录失败、封面图片失败仍可入镇", async ({ page }) => {
  const failures = [];
  page.on("pageerror", (e) => failures.push(e.message));

  await page.route("**/api/worldbooks", (route) => route.abort());
  // 只让浏览器里的图片请求失败，不拦截 Vite 以 JS 模块形式提供的资源 URL。
  await page.route(/\.(webp|png|jpe?g)(\?|$)/, (route) =>
    route.request().resourceType() === "image"
      ? route.abort()
      : route.continue(),
  );
  await page.goto("/");
  await expect(page.locator("#scene canvas")).toBeVisible();
  await expect(page.locator("#world-status")).toContainText("内置世界");
  await expect(page.locator("#world-list .world-card")).toHaveCount(4);
  await expect
    .poll(() => page.locator(".world-cover__photo.is-missing").count())
    .toBeGreaterThan(0);
  await page.screenshot({
    path: `${SHOTS}/世界书-封面失败入口.png`,
    fullPage: true,
  });
  await page.locator('.world-card[data-world-id="mist"]').click();
  await page.locator("#role-select").selectOption("villager");
  await page.getByRole("button", { name: "踏入雾中" }).click();
  await expect(page.locator("#identity")).toBeVisible();
  await expect(page.locator("html")).toHaveAttribute("data-world", "mist");
  await page.screenshot({
    path: `${SHOTS}/世界书-封面失败仍入镇.png`,
    fullPage: true,
  });
  expect(failures).toEqual([]);
});

test("世界书空目录给出提示且仍可入镇", async ({ page }) => {
  const failures = [];
  page.on("pageerror", (e) => failures.push(e.message));
  await page.route("**/api/worldbooks", (route) =>
    route.fulfill({
      contentType: "application/json",
      body: JSON.stringify({ default: "mist", worldbooks: [] }),
    }),
  );
  await page.goto("/");
  await expect(page.locator("#scene canvas")).toBeVisible();
  await expect(page.locator("#world-status")).toContainText("内置世界");
  await expect(page.locator("#world-list .world-card")).toHaveCount(4);
  await page.locator('.world-card[data-world-id="mist"]').click();
  await page.getByRole("button", { name: "踏入雾中" }).click();
  await expect(page.locator("#identity")).toBeVisible();
  await expect(page.locator("html")).toHaveAttribute("data-world", "mist");
  await page.screenshot({
    path: `${SHOTS}/世界书-空目录仍入镇.png`,
    fullPage: true,
  });
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
  await expect(page.locator("#phase-label")).toHaveText(state.chapter);
  await page.screenshot({
    path: `${SHOTS}/结局.png`,
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
    path: `${SHOTS}/断线提示.png`,
    fullPage: true,
  });
  await expect(page.locator("#submit-action")).toBeEnabled();
});

test("减少动效：系统偏好减少动效时仍可选择世界、入镇、行动并恢复", async ({
  page,
}) => {
  const failures = [];
  page.on("pageerror", (e) => failures.push(e.message));
  await page.emulateMedia({ reducedMotion: "reduce" });
  await page.goto("/");
  await expect(page.locator("html")).toHaveAttribute("data-motion", "reduced");
  await expect(page.locator("#scene canvas")).toBeVisible();
  await expect(page.locator("#world-list .world-card")).toHaveCount(4);
  await expect(page.locator("#debug-toggle")).toHaveAttribute(
    "aria-pressed",
    "true",
  );
  await expect(page.locator("#debug-panel")).toBeHidden();
  await page.locator('.world-card[data-world-id="threebody"]').click();
  await expect(page.locator("html")).toHaveAttribute("data-world", "threebody");
  await expect(
    page.locator('.world-card[data-world-id="threebody"]'),
  ).toHaveAttribute("aria-pressed", "true");
  await page.locator("#role-select").selectOption("wolf");
  await page.getByRole("button", { name: "踏入雾中" }).click();
  await expect(page.locator("#identity")).toBeVisible();
  await expect(page.locator("html")).toHaveAttribute("data-world", "threebody");
  await expect(page.locator("#debug-panel")).toBeVisible();
  await expect(page.locator("#role-title")).toContainText("潜伏者");
  await expect(page.locator("#phase-label")).toContainText(/静默夜|白昼/);
  await expect(page.locator("#waiting-text")).toContainText("频道中");
  await page.locator("#choice").selectOption("wolf_chat");
  await page.locator("#speech").fill("雾里先听，不急着开口。");
  await page.locator("#submit-action").click();
  await expect(page.locator("#story")).toContainText("雾里先听");
  await page.screenshot({
    path: `${SHOTS}/世界书-减少动效入镇.png`,
    fullPage: true,
  });
  await page.reload();
  await expect(page.locator("#identity")).toBeVisible();
  await expect(page.locator("#scene canvas")).toBeVisible();
  await expect(page.locator("html")).toHaveAttribute("data-world", "threebody");
  await expect(page.locator("#brand-name")).toHaveText("三体");
  expect(failures).toEqual([]);
});

test("调试默认开启、真实狼队对话、关闭清空并刷新保持", async ({ page }) => {
  const failures = [];
  page.on("pageerror", (e) => failures.push(e.message));
  await start(page, "wolf");

  await expect(page.locator("#debug-toggle")).toHaveAttribute(
    "aria-pressed",
    "true",
  );
  await expect(page.locator("#debug-panel")).toBeVisible();
  await expect(page.locator("#debug-status")).toContainText("对局", {
    timeout: 10000,
  });

  // 真实接口：人类狼提交的 wolf_chat 会作为真实事件出现在调试面板。
  const chat = `调试真实狼队密语 ${Date.now()}`;
  await page.locator("#choice").selectOption("wolf_chat");
  await page.locator("#speech").fill(chat);
  await page.locator("#submit-action").click();
  await expect(page.locator("#debug-wolf-chat")).toContainText(chat, {
    timeout: 10000,
  });
  await expect(
    page.locator("#debug-wolf-chat .debug-chat-item").first(),
  ).toBeVisible();
  await page.screenshot({
    path: `${SHOTS}/调试-默认开启.png`,
    fullPage: true,
  });

  const [offResponse] = await Promise.all([
    page.waitForResponse(
      (response) =>
        response.url().includes("/api/debug") &&
        response.request().method() === "POST",
    ),
    page.locator("#debug-toggle").click(),
  ]);
  expect(offResponse.ok()).toBeTruthy();
  expect(offResponse.request().postDataJSON()).toEqual({ enabled: false });
  await expect(page.locator("#debug-toggle")).toHaveAttribute(
    "aria-pressed",
    "false",
  );
  await expect(page.locator("#debug-panel")).toBeHidden();
  await expect(page.locator("#debug-rounds")).toHaveText("");
  await expect(page.locator("#debug-wolf-chat")).toHaveText("");
  await expect(page.locator("#debug-missing")).toHaveText("");
  await expect(page.locator("#debug-status")).toHaveText("");

  const offData = await (await page.request.get("/api/debug")).json();
  expect(offData.enabled).toBe(false);
  expect(offData.rounds).toEqual([]);
  expect(offData.wolf_chat).toEqual([]);
  expect(offData.missing).toEqual([]);

  // 关闭后停止轮询：等待一个轮询周期后不应再请求 /api/debug。
  await page.waitForTimeout(400);
  let debugRequests = 0;
  const countDebug = (request) => {
    if (request.url().endsWith("/api/debug")) debugRequests += 1;
  };
  page.on("request", countDebug);
  await page.waitForTimeout(2200);
  page.off("request", countDebug);
  expect(debugRequests).toBe(0);

  await page.reload();
  await expect(page.locator("#identity")).toBeVisible();
  await expect(page.locator("#debug-toggle")).toHaveAttribute(
    "aria-pressed",
    "false",
  );
  await expect(page.locator("#debug-panel")).toBeHidden();

  const [onResponse] = await Promise.all([
    page.waitForResponse(
      (response) =>
        response.url().includes("/api/debug") &&
        response.request().method() === "POST",
    ),
    page.locator("#debug-toggle").click(),
  ]);
  expect(onResponse.ok()).toBeTruthy();
  expect(onResponse.request().postDataJSON()).toEqual({ enabled: true });
  await expect(page.locator("#debug-toggle")).toHaveAttribute(
    "aria-pressed",
    "true",
  );
  await expect(page.locator("#debug-panel")).toBeVisible();
  await expect(page.locator("#debug-status")).toContainText("对局", {
    timeout: 10000,
  });

  await page.reload();
  await expect(page.locator("#identity")).toBeVisible();
  await expect(page.locator("#debug-toggle")).toHaveAttribute(
    "aria-pressed",
    "true",
  );
  await expect(page.locator("#debug-panel")).toBeVisible();
  expect(failures).toEqual([]);
});

test("调试面板按轮次/阶段/玩家展示显式说明、工具摘要、缺失与狼队对话", async ({
  page,
}) => {
  const failures = [];
  page.on("pageerror", (e) => failures.push(e.message));
  let mockData = {
    enabled: true,
    game_id: null,
    rounds: [],
    wolf_chat: [],
    missing: [],
  };
  await page.route("**/api/debug", async (route) => {
    if (route.request().method() === "GET")
      await route.fulfill({ json: mockData });
    else await route.continue();
  });
  await start(page, "wolf");
  await expect(page.locator("#debug-panel")).toBeVisible();

  mockData = {
    enabled: true,
    game_id: "mock-game-0001",
    rounds: [
      {
        round: 1,
        phases: [
          {
            phase: "night_wolves",
            phase_id: "phase-mock-1",
            label: "夜裔密谈",
            players: [
              {
                seat: 2,
                name: "灯匠",
                role: "夜裔",
                alive: true,
                decisions: [
                  {
                    time: "2026-10-25T17:00:00+00:00",
                    reason: "acted",
                    acted: true,
                    thinking: [
                      {
                        step: 1,
                        content:
                          "先听同伴的票型 <img src=x onerror=alert(1)>，再决定今夜的目标。",
                        has_content: true,
                        tool_calls: [
                          {
                            name: "wolf_chat",
                            args: { text: "先听后刀" },
                          },
                        ],
                      },
                    ],
                    calls: [
                      {
                        tool: "wolf_vote",
                        args: { target: 5 },
                        result: { accepted: true, version: 3 },
                      },
                    ],
                    missing: [],
                  },
                ],
              },
              {
                seat: 3,
                name: "苦修者",
                role: "夜裔",
                alive: true,
                decisions: [
                  {
                    time: "2026-10-25T17:00:02+00:00",
                    reason: "model_unavailable",
                    acted: true,
                    thinking: [
                      {
                        step: 1,
                        content: "",
                        has_content: false,
                        tool_calls: [],
                      },
                    ],
                    calls: [],
                    missing: [
                      {
                        reason: "no_content",
                        label: "模型未返回显式说明",
                      },
                    ],
                  },
                ],
              },
            ],
          },
        ],
      },
    ],
    wolf_chat: [
      {
        round: 1,
        phase: "night_wolves",
        seat: 2,
        name: "灯匠",
        text: "先听后刀",
        time: "2026-10-25T17:00:01+00:00",
      },
    ],
    missing: [
      {
        seat: 3,
        round: 1,
        phase: "night_wolves",
        reason: "no_content",
        label: "模型未返回显式说明",
      },
    ],
  };

  await expect(page.locator("#debug-rounds .debug-round")).toHaveCount(1, {
    timeout: 10000,
  });
  await expect(page.locator("#debug-rounds .debug-round")).toHaveAttribute(
    "data-round",
    "1",
  );
  const phase = page.locator('#debug-rounds .debug-phase[data-phase="night_wolves"]');
  await expect(phase).toBeVisible();
  await expect(phase).toContainText("夜裔密谈");
  await expect(
    phase.locator('.debug-player[data-seat="2"] .debug-role'),
  ).toContainText("夜裔");
  await expect(
    phase.locator('.debug-player[data-seat="2"] .debug-thinking-content'),
  ).toContainText("先听同伴的票型");
  await expect(
    phase.locator('.debug-player[data-seat="2"] .debug-thinking-content'),
  ).toContainText("<img src=x onerror=alert(1)>");
  await expect(page.locator("#debug-panel img")).toHaveCount(0);
  const toolCalls = phase.locator(
    '.debug-player[data-seat="2"] .debug-tool-call',
  );
  await expect(toolCalls.filter({ hasText: "wolf_chat" })).toContainText(
    "先听后刀",
  );
  await expect(toolCalls.filter({ hasText: "wolf_vote" })).toContainText(
    "accepted",
  );
  await expect(
    phase.locator('.debug-player[data-seat="3"] .debug-thinking-missing'),
  ).toContainText("未返回显式说明");
  await expect(
    phase.locator('.debug-player[data-seat="3"] .debug-thinking-content'),
  ).toHaveCount(0);
  await expect(page.locator("#debug-missing .debug-missing-item")).toContainText(
    "模型未返回显式说明",
  );
  await expect(page.locator("#debug-wolf-chat")).toContainText("先听后刀");
  await page.screenshot({
    path: `${SHOTS}/调试-缺失与工具摘要.png`,
    fullPage: true,
  });
  expect(failures).toEqual([]);
});

test("390px 调试面板可关闭再开启且不横向溢出", async ({ page }) => {
  const failures = [];
  page.on("pageerror", (e) => failures.push(e.message));
  await page.setViewportSize({ width: 390, height: 844 });
  await start(page, "wolf");
  await expect(page.locator("#debug-toggle")).toBeVisible();
  await expect(page.locator("#debug-panel")).toBeVisible();
  expect(
    await page.evaluate(() => document.documentElement.scrollWidth),
  ).toBeLessThanOrEqual(390);

  await page.locator("#debug-panel").scrollIntoViewIfNeeded();
  await page.screenshot({
    path: `${SHOTS}/调试-手机.png`,
    fullPage: false,
  });

  await page.locator("#debug-toggle").click();
  await expect(page.locator("#debug-toggle")).toHaveAttribute(
    "aria-pressed",
    "false",
  );
  await expect(page.locator("#debug-panel")).toBeHidden();
  await page.locator("#debug-toggle").click();
  await expect(page.locator("#debug-toggle")).toHaveAttribute(
    "aria-pressed",
    "true",
  );
  await expect(page.locator("#debug-panel")).toBeVisible();
  await expect(page.locator("#debug-status")).toContainText("对局", {
    timeout: 10000,
  });
  expect(
    await page.evaluate(() => document.documentElement.scrollWidth),
  ).toBeLessThanOrEqual(390);
  expect(failures).toEqual([]);
});
