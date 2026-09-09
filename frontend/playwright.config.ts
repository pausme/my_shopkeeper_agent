import { defineConfig, devices } from "@playwright/test";

/**
 * PickMate AI E2E 套件（N9.1 / N0.8）
 *
 * 目标站点默认为线上生产（通过 env 覆盖为本地 dev）：
 *   E2E_BASE_URL=http://localhost:5173 pnpm test:e2e
 *
 * 截图基线存于 e2e/__screenshots__（三宽度验收 N9.1）。
 */
export default defineConfig({
  testDir: "./e2e",
  timeout: 120_000,
  // 直打生产：必须单 worker 串行——多文件并行会集中触发导购接口
  // query 10/min 限流（deploy #70/#71 E2E 失败根因：429）
  fullyParallel: false,
  workers: 1,
  retries: process.env.CI ? 1 : 0,
  reporter: process.env.CI ? "line" : "list",
  use: {
    baseURL: process.env.E2E_BASE_URL ?? "http://1.13.255.225",
    trace: "retain-on-failure",
    screenshot: "only-on-failure",
    // 需要访问令牌的接口：测试前由 globalSetup 注入 localStorage
  },
  projects: [
    { name: "desktop-1024", use: { ...devices["Desktop Chrome"], viewport: { width: 1024, height: 800 } } },
    // N12.15：四档桌面宽度验收（1024/1280/1440/1920）
    { name: "desktop-1280", use: { ...devices["Desktop Chrome"], viewport: { width: 1280, height: 800 } } },
    { name: "desktop-1440", use: { ...devices["Desktop Chrome"], viewport: { width: 1440, height: 900 } } },
    { name: "desktop-1920", use: { ...devices["Desktop Chrome"], viewport: { width: 1920, height: 1080 } } },
  ],
});
