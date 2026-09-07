import { expect, test } from "@playwright/test";

/**
 * 导购 UI 质量断言（回归报告 UI 部分）
 * - 品型一致性 UI 层：空气炸锅推荐卡全为空气炸锅（N11.25 UI 断言）
 * - 推荐卡不暴露后端 product_id（F-REG-003 DOM 断言）
 * - 普通推荐轮不自动展开对比表（N11.27 UI 断言）
 */
// 完整导购链路需要访问令牌：从环境变量注入（本地/CI 提供，不入仓库）
const API_TOKEN = process.env.E2E_API_TOKEN ?? "";

test.describe("导购质量 UI", () => {
  test.beforeEach(async ({ page }) => {
    test.skip(!API_TOKEN, "需要 E2E_API_TOKEN（导购接口鉴权）");
    await page.addInitScript(
      (token) => localStorage.setItem("shopkeeper.apiToken", token),
      API_TOKEN,
    );
  });

  test("空气炸锅推荐只出空气炸锅且无后端 ID", async ({ page }) => {
    test.setTimeout(180_000);
    await page.goto("/");

    await page.getByRole("button", { name: /想买一个空气炸锅/ }).first().click();

    // 自动应答追问（如有）：真等待卡片或追问选项（isVisible 不等待，必须用 waitFor）
    const waitFor = (locator: ReturnType<typeof page.locator> | ReturnType<typeof page.getByRole>, ms: number) =>
      locator.waitFor({ state: "visible", timeout: ms }).then(() => true).catch(() => false);

    for (let round = 0; round < 3; round++) {
      if (await waitFor(page.locator("article").first(), 45_000)) break;
      if (await waitFor(page.getByRole("button", { name: "好清洗", exact: true }), 15_000)) {
        await page.getByRole("button", { name: "好清洗", exact: true }).click();
        continue;
      }
      if (await waitFor(page.getByRole("button", { name: "跳过", exact: true }), 10_000)) {
        await page.getByRole("button", { name: "跳过", exact: true }).click();
      }
    }

    // 等推荐卡出现
    const firstCard = page.locator("article").first();
    await expect(firstCard).toBeVisible({ timeout: 120_000 });

    // N11.25：所有卡片标题含"空气炸锅"
    const cards = page.locator("article");
    const count = await cards.count();
    expect(count).toBeGreaterThanOrEqual(1);
    for (let i = 0; i < count; i++) {
      const title = await cards.nth(i).locator("button.line-clamp-2").innerText();
      expect(title, `卡片 ${i + 1} 应为空气炸锅`).toContain("空气炸锅");
    }

    // F-REG-003：卡片可见文本不出现 P0001 式后端 ID
    const cardText = await cards.allInnerTexts();
    for (const text of cardText) {
      expect(text, "卡片文案不应包含后端商品 ID").not.toMatch(/P\d{4}/);
    }

    // N11.27：普通推荐轮不自动展开完整对比表
    await expect(page.getByText("商品横向对比")).toHaveCount(0);
  });
});
