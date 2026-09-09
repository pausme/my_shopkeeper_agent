import { expect, test } from "@playwright/test";

/**
 * 三宽度响应式截图（N9.1 / N0.8）
 * 每个宽度截首页与对话页基线；overflow 断言硬校验无横向滚动。
 * 截图存于 e2e/__screenshots__/{project}/ 便于人工走查与 CI 归档。
 */
test.describe("响应式视觉", () => {
  test("首页无横向溢出并截图", async ({ page }, testInfo) => {
    await page.goto("/");
    await expect(page.getByRole("heading", { name: "买什么，先把条件说清楚" })).toBeVisible();

    const overflow = await page.evaluate(
      () => document.documentElement.scrollWidth > document.documentElement.clientWidth,
    );
    expect(overflow, "页面不应横向溢出").toBe(false);

    await page.screenshot({
      path: `e2e/__screenshots__/${testInfo.project.name}/home.png`,
      fullPage: true,
    });
  });

  test("对话页无横向溢出并截图", async ({ page }, testInfo) => {
    test.setTimeout(150_000);
    await page.goto("/");
    // 走一轮真实导购（生产环境 DeepSeek，约 10s）
    await page.getByRole("button", { name: /想买一个空气炸锅/ }).first().click();
    // 等待推荐或追问出现（任一都进入对话页）
    await expect(
      page
        .getByText("正在理解你的需求")
        .or(page.getByText("正在筛选候选商品"))
        .or(page.getByRole("button", { name: "跳过", exact: true }))
        .or(page.locator("article").first())
        .first(),
    ).toBeVisible({ timeout: 90_000 });

    const overflow = await page.evaluate(
      () => document.documentElement.scrollWidth > document.documentElement.clientWidth,
    );
    expect(overflow, "对话页不应横向溢出").toBe(false);

    await page.screenshot({
      path: `e2e/__screenshots__/${testInfo.project.name}/chat.png`,
      fullPage: true,
    });
  });
});
