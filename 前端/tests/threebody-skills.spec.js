import { test, expect } from "@playwright/test";
import { execFileSync } from "node:child_process";
import { fileURLToPath } from "node:url";

const headers = { "X-Mist-Request": "1" };
const database = process.env.TEST_DATABASE || fileURLToPath(new URL("../../临时/浏览器测试/对局.sqlite3", import.meta.url));
const driver = fileURLToPath(new URL("../../tests/helpers/推进技能验收.py", import.meta.url));
const python = process.env.PYTHON || "../.venv/bin/python";
const roles = { antidote: "witch", poison: "witch", shoot: "hunter", reveal: "idiot" };

function prepare(gameId, tool) {
  return JSON.parse(execFileSync(python, [driver, database, gameId, tool], { encoding: "utf8" }));
}

async function game(page, tool, world = "threebody") {
  const response = await page.request.post("/api/game", {
    data: { role: roles[tool], worldbook: world }, headers,
  });
  expect(response.ok(), await response.text()).toBe(true);
  const state = await response.json();
  return { state, prepared: prepare(state.game_id, tool) };
}

test("三体四技能真实规则窗口、实际施放、刷新及跨世界图标隔离", async ({ page }) => {
  const errors = [];
  page.on("pageerror", (error) => errors.push(error.message));
  // NPC只由上面的正常行动驱动器推进；页面轮询读取状态，不触发付费模型。
  await page.route("**/api/advance", async (route) => {
    const response = await page.request.get("/api/state");
    await route.fulfill({ response });
  });
  await page.goto("/");
  await page.request.post("/api/enter", { data: { password: "" }, headers });
  const pictures = [];
  for (const tool of Object.keys(roles)) {
    const { prepared } = await game(page, tool);
    expect(prepared.phase).toBe({ antidote: "night_witch", poison: "night_witch", shoot: "hunter", reveal: "idiot" }[tool]);
    if (tool === "shoot") expect(prepared.alive).toBe(false);
    await page.reload();
    const chip = page.locator(`.choice-chip[data-tool="${tool}"]`);
    const icon = chip.locator(`[data-skill-icon="${tool}"]`);
    await expect(icon).toBeVisible();
    await icon.locator("img").evaluate((image) => image.decode());
    expect(await icon.locator("img").getAttribute("src")).toContain("skill-icons");
    expect(await icon.locator(".world-icon__clip").evaluate((el) => getComputedStyle(el).overflow)).toBe("hidden");
    pictures.push(await icon.screenshot());
    await page.reload();
    await expect(chip.locator(`[data-skill-icon="${tool}"]`)).toBeVisible();
    await page.setViewportSize({ width: 390, height: 844 });
    expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBeLessThanOrEqual(390);
    await expect(chip).toBeVisible();
    await page.setViewportSize({ width: 1440, height: 1100 });
    await chip.click();
    const before = await (await page.request.get("/api/state")).json();
    const choice = before.choices.find((item) => item.tool === tool);
    if (choice.targets?.length) await page.locator("#target").selectOption(String(choice.targets[0]));
    const [response] = await Promise.all([
      page.waitForResponse((r) => r.url().endsWith("/api/action") && r.request().method() === "POST"),
      page.locator("#submit-action").click(),
    ]);
    expect(response.status()).toBe(200);
    const after = await response.json();
    expect(after.story.some((entry) => entry.actor === 1 && entry.effect === { antidote: "heal", poison: "harm", shoot: "shot", reveal: "oath" }[tool])).toBe(true);
    if (["antidote", "poison"].includes(tool)) {
      expect(after.resources[tool === "antidote" ? "修复预案" : "清除预案"]).toBe(false);
    }
  }
  for (let first = 0; first < pictures.length; first++) {
    for (let second = first + 1; second < pictures.length; second++) {
      expect(pictures[first].equals(pictures[second]), "四项技能必须显示不同真实像素").toBe(false);
    }
  }
  const signupResponse = await page.request.post("/api/game", {
    data: { role: "hunter", worldbook: "threebody" }, headers,
  });
  prepare((await signupResponse.json()).game_id, "signup");
  await page.reload();
  await expect(page.locator('.choice-chip[data-tool="signup"] [data-icon="badge"]')).toBeVisible();
  await expect(page.locator('.choice-chip[data-tool="signup"] [data-skill-icon]')).toHaveCount(0);
  await game(page, "antidote", "mist");
  await page.reload();
  await expect(page.locator(".choice-chip [data-skill-icon]")).toHaveCount(0);
  await expect(page.locator('.choice-chip[data-tool="antidote"] [data-icon="antidote"]')).toBeVisible();
  await game(page, "antidote");
  await page.reload();
  await expect(page.locator('.choice-chip[data-tool="antidote"] [data-skill-icon="antidote"]')).toBeVisible();
  // 存活状态仍使用普通图集，而非专用冬眠舱/预案图。
  expect(await page.locator('#roster [data-icon="alive"]').first().evaluate((el) => getComputedStyle(el).backgroundImage)).toContain("icons-");
  expect(errors).toEqual([]);
});
