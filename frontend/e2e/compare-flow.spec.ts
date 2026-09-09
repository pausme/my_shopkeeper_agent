import { expect, test } from "@playwright/test";

/**
 * N11.32 / N11.33 验收断言
 * - N11.33：对比托盘提交后留在对话页并展示对比表；
 *   对比托盘激活期间悬浮"新咨询"按钮隐藏（此前物理遮挡"开始对比"，点击实际触发回首页）
 * - N11.32：显式品型无货（蓝牙耳机）返回空推荐并明示"暂无"，不出现相邻品类商品卡
 */
const API_TOKEN = process.env.E2E_API_TOKEN ?? "";

test.describe("对比流程与品型无货", () => {
  test.beforeEach(async ({ page }) => {
    test.skip(!API_TOKEN, "需要 E2E_API_TOKEN（导购接口鉴权）");
    await page.addInitScript(
      (token) => localStorage.setItem("shopkeeper.apiToken", token),
      API_TOKEN,
    );
  });

  const visible = (loc: ReturnType<typeof page.locator>, ms: number) =>
    loc.waitFor({ state: "visible", timeout: ms }).then(() => true).catch(() => false);

  test("选两款点开始对比：留在对话页并出对比表（N11.33）", async ({ page }) => {
    test.setTimeout(300_000);
    await page.goto("/");

    // 厨房小电器多候选查询（空气炸锅仅 1 款在售，凑不满对比所需的两张卡）
    await page.getByPlaceholder(/描述你的购买需求/).fill("推荐几个厨房小电器，预算300以内，好清洗");
    await page.getByPlaceholder(/描述你的购买需求/).press("Enter");

    for (let round = 0; round < 4; round++) {
      if (await visible(page.locator("article").first(), 60_000)) break;
      for (const opt of ["好清洗", "跳过"]) {
        if (await visible(page.getByRole("button", { name: opt, exact: true }), 10_000)) {
          await page.getByRole("button", { name: opt, exact: true }).click();
          break;
        }
      }
    }
    await expect(page.locator("article").first()).toBeVisible({ timeout: 120_000 });

    const cards = page.locator("article");
    const count = await cards.count();
    expect(count).toBeGreaterThanOrEqual(2);
    for (let i = 0; i < 2; i++) {
      await cards.nth(i).getByRole("button", { name: "加入对比" }).click();
    }

    // N11.33 修复验收：开始对比按钮可见且可用（悬浮"新咨询"不再遮挡——
    // 若被遮挡，Playwright 的 click 会因 intercepts pointer events 失败）
    const compareButton = page.getByRole("button", { name: /开始对比/ });
    await expect(compareButton).toBeVisible();
    await expect(compareButton).toBeEnabled();

    await compareButton.click();

    // 对比表出现且仍停留在对话页（未回首页）
    await expect(page.getByText("商品横向对比").first()).toBeVisible({ timeout: 180_000 });
    await expect(page.getByRole("heading", { name: "买什么，先把条件说清楚" })).toBeHidden();
  });

  test("蓝牙耳机无货：空推荐并明示暂无品型（N11.32）", async ({ page }) => {
    test.setTimeout(300_000);
    await page.goto("/");

    await page.getByPlaceholder(/描述你的购买需求/).fill("想买一个蓝牙耳机，预算300以内，通勤使用，优先降噪");
    await page.getByPlaceholder(/描述你的购买需求/).press("Enter");

    for (let round = 0; round < 4; round++) {
      if (await visible(page.getByText(/暂无「耳机」/), 90_000)) break;
      for (const opt of ["通用", "跳过"]) {
        if (await visible(page.getByRole("button", { name: opt, exact: true }), 10_000)) {
          await page.getByRole("button", { name: opt, exact: true }).click();
          break;
        }
      }
    }

    // 明示暂无品型，且不出现任何相邻品类商品卡
    await expect(page.getByText(/暂无「耳机」/)).toBeVisible({ timeout: 120_000 });
    await expect(page.locator("article")).toHaveCount(0);
  });
});
