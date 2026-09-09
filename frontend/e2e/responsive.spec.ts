import { expect, test } from "@playwright/test";

/**
 * 四宽度响应式截图（N9.1 / N0.8 / N12.15）
 * 每个宽度截首页与对话页基线；overflow 断言硬校验无横向滚动。
 * 截图存于 e2e/__screenshots__/{project}/ 便于人工走查与 CI 归档。
 */
const API_TOKEN = process.env.E2E_API_TOKEN ?? "";

test.describe("响应式视觉", () => {
  test.beforeEach(async ({ page }) => {
    // 首页用例不依赖令牌；对话页走真实导购需令牌（守卫在该用例内）
    if (API_TOKEN) {
      await page.addInitScript(
        (token) => localStorage.setItem("shopkeeper.apiToken", token),
        API_TOKEN,
      );
    }
  });

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
    // N12.24：对话页走真实导购需令牌——本地缺令牌可跳过，CI 缺令牌必须失败
    test.skip(!API_TOKEN && !process.env.CI, "需要 E2E_API_TOKEN（导购接口鉴权）");
    test.fail(!API_TOKEN && Boolean(process.env.CI), "CI 未注入 E2E_API_TOKEN，鉴权用例被静默跳过");
    test.setTimeout(150_000);
    await page.goto("/");
    // 走一轮真实导购（生产环境 DeepSeek，约 10s）
    await page.getByRole("button", { name: /想买一个空气炸锅/ }).first().click();
    // N12.24：等待真实进展信号（追问选项/推荐卡），不用乐观 UI 文案——
    // 避免令牌缺失时的错误态被误当成功截图
    await expect(
      page
        .getByRole("button", { name: "跳过", exact: true })
        .or(page.getByRole("button", { name: "好清洗", exact: true }))
        .or(page.locator("article").first())
        .first(),
    ).toBeVisible({ timeout: 90_000 });
    // 自动应答追问（如有）直至推荐卡出现
    for (let round = 0; round < 3; round++) {
      if (await page.locator("article").first().isVisible().catch(() => false)) break;
      const option = await page
        .getByRole("button", { name: "好清洗", exact: true })
        .or(page.getByRole("button", { name: "跳过", exact: true }))
        .first()
        .isVisible()
        .catch(() => false);
      if (option) {
        await page
          .getByRole("button", { name: "好清洗", exact: true })
          .or(page.getByRole("button", { name: "跳过", exact: true }))
          .first()
          .click();
      }
    }
    await expect(page.locator("article").first()).toBeVisible({ timeout: 120_000 });

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
