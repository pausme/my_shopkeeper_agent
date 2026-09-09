import { expect, test } from "@playwright/test";

/**
 * N11.34 管理台返回导购的来源上下文恢复
 * - 首页进入管理台 → 返回 → 回首页
 * - 会话页进入管理台 → 返回 → 恢复原会话页（内存态保留）
 * - 会话页进入管理台 → 刷新 → 返回 → 从服务端回放原会话（sessionStorage 兜底）
 */
const API_TOKEN = process.env.E2E_API_TOKEN ?? "";

test.describe("管理台返回上下文", () => {
  test.beforeEach(async ({ page }) => {
    test.skip(!API_TOKEN, "需要 E2E_API_TOKEN（导购接口鉴权）");
    await page.addInitScript(
      (token) => localStorage.setItem("shopkeeper.apiToken", token),
      API_TOKEN,
    );
  });

  const visible = (loc: ReturnType<typeof page.locator>, ms: number) =>
    loc.waitFor({ state: "visible", timeout: ms }).then(() => true).catch(() => false);

  async function startConsultation(page: import("@playwright/test").Page) {
    await page.goto("/");
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
  }

  test("首页进入管理台：返回回首页", async ({ page }) => {
    await page.goto("/");
    await expect(page.getByRole("heading", { name: "买什么，先把条件说清楚" })).toBeVisible();

    await page.evaluate(() => {
      window.location.hash = "#/admin";
    });
    await expect(page.getByText("商品数据管理台").first()).toBeVisible({ timeout: 15_000 });

    await page.getByRole("link", { name: "返回导购" }).click();
    await expect(page.getByRole("heading", { name: "买什么，先把条件说清楚" })).toBeVisible({ timeout: 15_000 });
  });

  test("会话页进入管理台：返回恢复原会话（不刷新）", async ({ page }) => {
    test.setTimeout(300_000);
    await startConsultation(page);

    await page.evaluate(() => {
      window.location.hash = "#/admin";
    });
    await expect(page.getByText("商品数据管理台").first()).toBeVisible({ timeout: 15_000 });

    await page.getByRole("link", { name: "返回导购" }).click();
    // 回到原会话页：推荐卡仍在，未回首页
    await expect(page.locator("article").first()).toBeVisible({ timeout: 15_000 });
    await expect(page.getByRole("heading", { name: "买什么，先把条件说清楚" })).toBeHidden();
  });

  test("会话页进入管理台并刷新：返回从服务端回放会话", async ({ page }) => {
    test.setTimeout(300_000);
    await startConsultation(page);

    await page.evaluate(() => {
      window.location.hash = "#/admin";
    });
    await expect(page.getByText("商品数据管理台").first()).toBeVisible({ timeout: 15_000 });

    // 刷新管理台：内存态丢失，凭 sessionStorage 记录的来源会话恢复
    await page.reload();
    await expect(page.getByText("商品数据管理台").first()).toBeVisible({ timeout: 15_000 });

    await page.getByRole("link", { name: "返回导购" }).click();
    await expect(page.locator("article").first()).toBeVisible({ timeout: 60_000 });
    await expect(page.getByRole("heading", { name: "买什么，先把条件说清楚" })).toBeHidden();
  });
});
