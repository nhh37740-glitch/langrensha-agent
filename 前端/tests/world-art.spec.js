import { test, expect } from "@playwright/test";
import { mkdirSync, readFileSync } from "node:fs";

// 截图默认写临时证据目录（临时/ 不入库）；验收时再把选定画面压缩到
// 文档/版本/v0.7.0/截图/。可用 WORLD_ART_SHOTS 覆盖输出目录。
const SHOTS =
  process.env.WORLD_ART_SHOTS ||
  "../临时/世界书视觉Issue/验证证据/浏览器截图";
mkdirSync(SHOTS, { recursive: true });

const PERSONAS = JSON.parse(
  readFileSync(new URL("../src/worlds/personas.json", import.meta.url), "utf8"),
);

const WORLDS = [
  { id: "mist", name: "雾钟镇" },
  { id: "hyperion", name: "海伯利安" },
  { id: "threebody", name: "三体" },
  { id: "tidal_archive", name: "潮汐档案馆" },
];

const ICON_KEYS = [
  "inspect",
  "antidote",
  "poison",
  "shoot",
  "explode",
  "badge",
  "vote",
  "speak",
  "abstain",
  "alive",
  "dead",
  "sheriff",
  "you",
  "disconnected",
  "night",
  "day",
];
const CATALOG_FORBIDDEN_KEYS = new Set([
  "entries",
  "guidance",
  "personas",
  "basis",
  "identity",
  "camp",
  "faction",
  "secret",
]);

function collectKeys(value, keys = []) {
  if (Array.isArray(value)) value.forEach((item) => collectKeys(item, keys));
  else if (value && typeof value === "object") {
    Object.entries(value).forEach(([key, nested]) => {
      keys.push(key);
      collectKeys(nested, keys);
    });
  }
  return keys;
}

function collectStrings(value, strings = []) {
  if (typeof value === "string") strings.push(value);
  else if (Array.isArray(value)) value.forEach((item) => collectStrings(item, strings));
  else if (value && typeof value === "object")
    Object.values(value).forEach((nested) => collectStrings(nested, strings));
  return strings;
}

async function openEntry(page) {
  await page.goto("/");
  await expect(page.locator("#scene canvas")).toBeVisible();
  await expect(page.locator("#world-picker")).toBeVisible();
  await expect(page.locator("#world-list")).toHaveAttribute("aria-busy", "false");
  await expect(page.locator("#world-list .world-card")).toHaveCount(4);
}

async function selectWorld(page, worldId) {
  await page.locator(`.world-card[data-world-id="${worldId}"]`).click();
  await expect(page.locator("html")).toHaveAttribute("data-world", worldId);
  await expect(
    page.locator(`.world-card[data-world-id="${worldId}"]`),
  ).toHaveAttribute("aria-pressed", "true");
  await expect(page.locator("#world-detail")).toBeVisible();
}

async function enterWorld(page, worldId, role = "villager") {
  await selectWorld(page, worldId);
  await page.locator("#role-select").selectOption(role);
  await page.getByRole("button", { name: "踏入雾中" }).click();
  await expect(page.locator("#identity")).toBeVisible();
  await expect(page.locator("html")).toHaveAttribute("data-world", worldId);
  await expect(page.locator("#scene canvas")).toBeVisible();
}

async function resetToPicker(page) {
  if (await page.locator("#world-picker").isVisible()) return;
  page.once("dialog", (dialog) => dialog.accept());
  await page.locator("#reset").click();
  await expect(page.locator("#world-picker")).toBeVisible();
  await expect(page.locator("#world-list .world-card")).toHaveCount(4);
  await expect(page.locator("#world-list")).toHaveAttribute("aria-busy", "false");
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

async function expectNoHorizontalOverflow(page) {
  const metrics = await page.evaluate(() => ({
    viewport: document.documentElement.clientWidth,
    scroll: document.documentElement.scrollWidth,
  }));
  expect(metrics.viewport).toBeLessThanOrEqual(390);
  expect(metrics.scroll).toBeLessThanOrEqual(390);
}

function assetResponses(page) {
  const urls = [];
  page.on("response", (response) => {
    const url = response.url();
    if (/\.(webp|png)(\?|$)/i.test(url)) urls.push(url);
  });
  return urls;
}

test("四世界封面真实加载，目录接口只含公开字段", async ({ page }) => {
  const failures = [];
  page.on("pageerror", (error) => failures.push(error.message));
  const assets = assetResponses(page);
  await openEntry(page);

  const catalogResponse = await page.request.get("/api/worldbooks");
  expect(catalogResponse.ok()).toBeTruthy();
  const catalog = await catalogResponse.json();
  expect(catalog.worldbooks).toHaveLength(4);
  expect(collectKeys(catalog).filter((key) => CATALOG_FORBIDDEN_KEYS.has(key))).toEqual(
    [],
  );
  const catalogText = collectStrings(catalog).join("\n");
  expect(catalogText).not.toMatch(/阵营|暗牌|identity|undercover/i);
  expect(catalogText).not.toMatch(/\bentries\b|\bguidance\b/i);

  for (const world of WORLDS) {
    const card = page.locator(`.world-card[data-world-id="${world.id}"]`);
    const cover = card.locator(".world-cover__photo");
    await expect(cover, `${world.name} 封面图应存在`).toHaveCount(1);
    const src = await cover.getAttribute("src");
    expect(src, `${world.name} 应使用独立封面`).toContain("cover");
    await expect
      .poll(
        () =>
          cover.evaluate(
            (image) => image.complete && image.naturalWidth > 0,
          ),
        { message: `${world.name} 封面应真实加载` },
      )
      .toBe(true);
    const response = await page.request.get(src);
    expect(response.ok(), `${world.name} 封面请求应成功`).toBeTruthy();
    await selectWorld(page, world.id);
    const detailCover = page.locator("#world-detail-cover .world-cover__photo");
    await expect(detailCover).toHaveCount(1);
    await expect(detailCover).toHaveAttribute("src", /cover/);
    await expect
      .poll(() =>
        detailCover.evaluate((image) => image.complete && image.naturalWidth > 0),
      )
      .toBe(true);
  }
  expect(assets.some((url) => /cover/i.test(url))).toBe(true);
  await selectWorld(page, "mist");
  await page.screenshot({
    path: `${SHOTS}/世界美术-四世界封面-桌面.png`,
    fullPage: true,
  });
  expect(failures).toEqual([]);
});

test("四世界详情名册各有 12 名不同公开人物", async ({ page }) => {
  const failures = [];
  page.on("pageerror", (error) => failures.push(error.message));
  await openEntry(page);

  for (const world of WORLDS) {
    const expectedNames = PERSONAS.worlds[world.id].personas.map(
      (persona) => persona.name,
    );
    await selectWorld(page, world.id);
    await expect(page.locator("#world-detail-name")).toHaveText(world.name);
    const roster = page.locator("#world-detail-personas");
    await expect(roster, `${world.name} 应有公开人物名册`).toBeVisible();
    const tiles = roster.locator(".world-persona");
    await expect(tiles, `${world.name} 应有 12 名人物`).toHaveCount(12);

    const seats = await tiles.evaluateAll((nodes) =>
      nodes.map((node) => Number(node.dataset.seat)),
    );
    const slots = await tiles.evaluateAll((nodes) =>
      nodes.map((node) => Number(node.dataset.slot)),
    );
    expect(seats).toEqual([1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12]);
    expect(new Set(slots).size).toBe(12);
    expect(slots).toEqual([0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11]);

    const names = await roster.locator(".world-persona__name").allTextContents();
    expect(names).toEqual(expectedNames);
    expect(new Set(names).size).toBe(12);

    const portraits = roster.locator(".world-persona__portrait");
    await expect(portraits).toHaveCount(12);
    await expect(
      roster.locator('.world-persona__portrait[data-persona-state="ready"]'),
      `${world.name} 12 张图集画像都应加载完成`,
    ).toHaveCount(12);
    const styles = await portraits.evaluateAll((nodes) =>
      nodes.map((node) => {
        const style = getComputedStyle(node);
        return {
          image: style.backgroundImage,
          position: style.backgroundPosition,
        };
      }),
    );
    styles.forEach((style) => expect(style.image).toContain("personas"));
    expect(new Set(styles.map((style) => style.position)).size).toBe(12);

    const rosterText = (await roster.innerText()).replace(/\s+/g, " ");
    expect(rosterText).not.toMatch(/夜裔|荆棘使徒|潜伏者|噬名者|观星者|验潮员/);
    expect(rosterText).not.toMatch(/阵营|暗牌|狼人/);

    await page.screenshot({
      path: `${SHOTS}/世界美术-${world.id}-详情名册-桌面.png`,
      fullPage: true,
    });
  }
  expect(failures).toEqual([]);
});

test("四世界进入对局：世界/昼夜/场景/技能图标与动效可观察", async ({
  page,
}) => {
  const failures = [];
  page.on("pageerror", (error) => failures.push(error.message));
  const assets = assetResponses(page);
  await openEntry(page);

  for (const world of WORLDS) {
    await enterWorld(page, world.id);
    await expect(page.locator("html")).toHaveAttribute(
      "data-phase",
      /night|day/,
    );
    await expect(page.locator("#phase-label")).not.toHaveText("");
    await expect(page.locator("#day")).toContainText(/白昼|夜|昼/);
    const state = await (await page.request.get("/api/state")).json();
    expect(state.worldbook).toBe(world.id);
    expect(["night", "day"]).toContain(
      await page.locator("html").getAttribute("data-phase"),
    );

    // 公开状态/技能图标：使用图集 data-icon，不能回退成身份提示。
    await expect
      .poll(() => page.locator("[data-icon]").count())
      .toBeGreaterThan(0);
    const iconKeys = await page
      .locator("[data-icon]")
      .evaluateAll((nodes) => nodes.map((node) => node.dataset.icon));
    iconKeys.forEach((key) => expect(ICON_KEYS).toContain(key));

    await page.screenshot({
      path: `${SHOTS}/世界美术-${world.id}-对局-桌面.png`,
      fullPage: true,
    });
    await resetToPicker(page);
  }

  expect(assets.some((url) => /personas/i.test(url))).toBe(true);
  expect(
    assets.some((url) => /scene-(day|night)/i.test(url)),
  ).toBe(true);
  expect(assets.some((url) => /icons/i.test(url))).toBe(true);

  // 查验动效：以观星者入镇，推进到可查验，提交后等待真实动效图集。
  await enterWorld(page, "mist", "seer");
  page.on("dialog", (dialog) => dialog.accept());
  for (let i = 0; i < 12; i += 1) {
    const state = await post(page, "advance", {});
    if (state.choices.some((choice) => choice.tool === "inspect")) break;
  }
  await page.reload();
  await expect(page.locator("#identity")).toBeVisible();
  await page.locator("#choice").selectOption("inspect");
  const target = page.locator("#target");
  if (await target.isVisible()) {
    const value = await target.locator("option").first().getAttribute("value");
    if (value) await target.selectOption(value);
  }
  await page.locator("#submit-action").click();
  await expect
    .poll(() => assets.some((url) => /effects/i.test(url)), {
      message: "查验后应加载动效图集",
    })
    .toBe(true);
  await page.screenshot({
    path: `${SHOTS}/世界美术-查验动效-桌面.png`,
    fullPage: true,
  });
  expect(failures).toEqual([]);
});

test("390×844 手机视口：四世界选择/名册/对局无横向溢出", async ({ page }) => {
  const failures = [];
  page.on("pageerror", (error) => failures.push(error.message));
  await page.setViewportSize({ width: 390, height: 844 });
  await openEntry(page);
  await expectNoHorizontalOverflow(page);
  await page.screenshot({
    path: `${SHOTS}/世界美术-四世界封面-手机390.png`,
    fullPage: true,
  });

  for (const world of WORLDS) {
    await selectWorld(page, world.id);
    await expectNoHorizontalOverflow(page);
    await expect(page.locator("#world-detail-personas .world-persona")).toHaveCount(
      12,
    );
    await page.screenshot({
      path: `${SHOTS}/世界美术-${world.id}-详情名册-手机390.png`,
      fullPage: true,
    });
  }

  await enterWorld(page, "tidal_archive");
  await expectNoHorizontalOverflow(page);
  await expect(page.locator("#scene canvas")).toBeVisible();
  await page.screenshot({
    path: `${SHOTS}/世界美术-tidal_archive-对局-手机390.png`,
    fullPage: true,
  });
  expect(failures).toEqual([]);
});

test("减少动效模式：跨世界选择与入镇仍可用", async ({ page }) => {
  const failures = [];
  page.on("pageerror", (error) => failures.push(error.message));
  await page.emulateMedia({ reducedMotion: "reduce" });
  await openEntry(page);
  await expect(page.locator("html")).toHaveAttribute("data-motion", "reduced");
  await selectWorld(page, "threebody");
  await expect(page.locator("#world-detail-personas .world-persona")).toHaveCount(
    12,
  );
  await enterWorld(page, "threebody");
  await expect(page.locator("html")).toHaveAttribute("data-motion", "reduced");
  await expect(page.locator("#scene canvas")).toBeVisible();
  await page.screenshot({
    path: `${SHOTS}/世界美术-减少动效-桌面.png`,
    fullPage: true,
  });
  expect(failures).toEqual([]);
});
