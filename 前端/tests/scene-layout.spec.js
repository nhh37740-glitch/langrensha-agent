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
  await enter(page);
  for (const world of WORLDS) {
    await page.request.post("/api/game", {
      data: { role: "villager", worldbook: world },
      headers: { "X-Mist-Request": "1" },
    });
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
