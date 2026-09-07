import { expect, test } from "@playwright/test";

/**
 * 首页核心断言（N11.14 / N3.1）
 * - 首页任何状态下只有一个主输入入口（无底部对话 textarea）
 * - 场景快捷入口与热门问题可渲染
 * - 顶部导航"当前会话"在无会话时隐藏（N11.4）
 */
test.describe("首页", () => {
  test("首页仅一个输入入口，无底部 composer", async ({ page }) => {
    await page.goto("/");
    await expect(page.getByRole("heading", { name: "买什么，问导购" })).toBeVisible();

    // 底部对话输入栏（textarea）不应存在于首页
    const textareas = page.locator("textarea");
    await expect(textareas).toHaveCount(0);

    // 首页搜索框是唯一输入入口
    const search = page.locator('input[placeholder*="空气炸锅"]');
    await expect(search).toHaveCount(1);
  });

  test("无会话时隐藏'当前会话'导航", async ({ page }) => {
    await page.goto("/");
    await expect(page.getByRole("button", { name: "当前会话" })).toHaveCount(0);
  });

  test("场景快捷入口渲染", async ({ page }) => {
    await page.goto("/");
    for (const label of ["租房好物", "送礼", "母婴", "厨房小电器"]) {
      await expect(page.getByRole("button", { name: label, exact: true })).toBeVisible();
    }
  });
});
