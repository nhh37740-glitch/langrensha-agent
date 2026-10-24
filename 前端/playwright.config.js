import { defineConfig } from "@playwright/test";
export default defineConfig({
  testDir: "./tests",
  timeout: 180000,
  workers: 1,
  outputDir: "../临时/完整可玩版/浏览器结果",
  use: {
    baseURL: "http://127.0.0.1:8001",
    viewport: { width: 1440, height: 1100 },
    launchOptions: process.env.CHROMIUM_PATH
      ? { executablePath: process.env.CHROMIUM_PATH }
      : {},
    screenshot: "only-on-failure",
    trace: "retain-on-failure",
  },
  webServer: {
    command: `${process.env.PYTHON || "../.venv/bin/python"} ../tests/web_fixture.py`,
    url: "http://127.0.0.1:8001/api/health",
    reuseExistingServer: false,
  },
  reporter: [["list"]],
});
