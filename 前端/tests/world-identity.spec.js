import { test, expect } from "@playwright/test";
import { mkdirSync, writeFileSync } from "node:fs";

const output = "../临时/世界身份称谓验收";

test("四世界24身份从入场选择到真实对局、刷新与手机保持一致", async ({ page }) => {
  const errors = [];
  page.on("pageerror", (error) => errors.push(error.message));
  // 验收身份的初始状态；所有NPC轮询只读真实状态，不调用模型。
  await page.route("**/api/advance", async (route) => {
    const response = await page.request.get("/api/state");
    await route.fulfill({ response });
  });
  page.on("dialog", (dialog) => dialog.accept());
  await page.goto("/");
  const books = (await (await page.request.get("/api/worldbooks")).json()).worldbooks;
  const receipts = [];
  mkdirSync(output, { recursive: true });
  for (const book of books) {
    for (const [role, name] of Object.entries(book.role_labels)) {
      await expect(page.locator("#world-picker")).toBeVisible();
      await expect(page.locator("#world-list")).toHaveAttribute("aria-busy", "false");
      await page.locator(`.world-card[data-world-id="${book.id}"]`).click();
      await expect(page.locator(`#role-select option[value="${role}"]`)).toContainText(name);
      await page.locator("#role-select").selectOption(role);
      const [response] = await Promise.all([
        page.waitForResponse((result) => result.url().endsWith("/api/game") && result.request().method() === "POST"),
        page.getByRole("button", { name: "踏入雾中" }).click(),
      ]);
      expect(response.status()).toBe(200);
      const state = await response.json();
      expect(state.identity).toBe(name);
      expect(state.worldbook).toBe(book.id);
      expect(response.request().postDataJSON()).toEqual({ role, worldbook: book.id });
      await expect(page.locator("#role-title")).toHaveText(`${name} · 1号`);
      await page.reload();
      await expect(page.locator("#role-title")).toHaveText(`${name} · 1号`);
      const restored = await (await page.request.get("/api/state")).json();
      expect(restored.game_id).toBe(state.game_id);
      expect(restored.identity).toBe(name);
      await page.setViewportSize({ width: 390, height: 844 });
      expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBeLessThanOrEqual(390);
      await expect(page.locator("#role-title")).toBeVisible();
      if (role === "hunter") await page.screenshot({ path: `${output}/${book.id}-手机.png`, fullPage: true });
      await page.setViewportSize({ width: 1440, height: 1100 });
      if (role === "hunter") await page.screenshot({ path: `${output}/${book.id}-桌面.png`, fullPage: true });
      receipts.push({ world: book.id, role, name, created: true, refreshed: true, mobile: true });
      await page.locator("#reset").click();
    }
  }
  expect(errors).toEqual([]);
  expect(receipts).toHaveLength(24);
  writeFileSync(`${output}/24身份浏览器验收.json`, JSON.stringify({ all_pass: true, paid_model_calls: 0, receipts }, null, 2));
});
