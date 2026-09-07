import { expect, test } from "@playwright/test";

/**
 * 弹窗与键盘交互（N11.23 / 回归报告 #23）
 * - 设置浮层：点开、点外关闭
 * - 历史下拉与设置浮层互斥（N11 互斥）
 * - 登录弹窗：打开、Esc 关闭、遮罩点击关闭
 */
test.describe("浮层与键盘", () => {
  test("设置浮层点外关闭", async ({ page }) => {
    await page.goto("/");
    await page.getByRole("button", { name: "设置", exact: true }).click();
    await expect(page.getByText("登录 / 注册")).toBeVisible();
    // 点击遮罩（页面左上空白区）
    await page.mouse.click(40, 300);
    await expect(page.getByText("登录 / 注册")).toHaveCount(0);
  });

  test("历史与设置浮层互斥", async ({ page }) => {
    await page.goto("/");
    await page.getByRole("button", { name: "设置", exact: true }).click();
    await expect(page.getByText("登录 / 注册")).toBeVisible();
    // 打开历史应关闭设置
    await page.getByRole("button", { name: "历史" }).click();
    await expect(page.getByText("登录 / 注册")).toHaveCount(0);
    await expect(
      page.getByText("暂无历史会话").or(page.getByText("去发起第一次咨询")).first(),
    ).toBeVisible();
  });

  test("登录弹窗 Esc 与遮罩关闭", async ({ page }) => {
    await page.goto("/");
    await page.getByRole("button", { name: "设置", exact: true }).click();
    await page.getByRole("button", { name: "登录 / 注册" }).click();
    const dialog = page.getByRole("dialog");
    await expect(dialog).toBeVisible();
    await expect(page.getByPlaceholder(/用户名|2~64/).first()).toBeFocused();
    // Esc 关闭（设置面板仍开着）
    await page.keyboard.press("Escape");
    await expect(dialog).toHaveCount(0);
    // 直接从仍开着的设置面板重开对话框，通过遮罩点击关闭
    await page.getByRole("button", { name: "登录 / 注册" }).click();
    await expect(dialog).toBeVisible();
    await page.mouse.click(40, 300);
    await expect(dialog).toHaveCount(0);
  });
});
