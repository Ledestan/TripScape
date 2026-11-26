/**
 * 行旅识景 TripScape / e2e/creation-compose.spec
 * 创建日期: 2026-11-26
 *
 * 旅行拼贴创作浮窗的端到端证据，覆盖:
 *     1. 从地球页头像菜单打开，不跳转路由
 *     2. 加元素后出现"未保存"圆点，撤销/重做生效
 *     3. 导出图片能产出下载
 *     4. 有未保存修改时关闭要确认，Esc 先退确认
 */

import { test, expect } from "@playwright/test";

test.describe("S3 旅行拼贴创作浮窗", () => {
  test("打开、加元素、撤销重做、导出与关闭确认", async ({ page }) => {
    await page.goto("/login");
    await page.waitForSelector("#boot-screen", { state: "detached", timeout: 30_000 });
    await page.locator('input[autocomplete="username"]').fill("demo");
    await page.locator('input[autocomplete="current-password"]').fill("demo123456");
    await page.locator('form button[type="submit"]').click();
    await page.waitForTimeout(1200);

    await page.goto("/");
    await page.waitForSelector("#boot-screen", { state: "detached", timeout: 30_000 });
    await page.waitForTimeout(1200);

    await page.getByTestId("dock-avatar").click();
    await page.getByTestId("dock-menu-creation").click();

    const dialog = page.getByRole("dialog", { name: /创作浮窗/ });
    await expect(dialog).toBeVisible({ timeout: 10_000 });
    // 不跳路由：仍是地球页
    expect(new URL(page.url()).pathname).toBe("/");
    await expect(page.getByText("从左侧拖入照片或地标碎片开始")).toBeVisible();

    // 加一段文字 → 元素计数 1/60，出现未保存圆点
    await page.getByRole("button", { name: "加一段文字" }).click();
    await expect(page.getByText("1/60 · 3:4")).toBeVisible();
    await expect(page.getByTestId("compose-dirty-dot")).toBeVisible();

    // 导出：出现下载
    const downloadPromise = page.waitForEvent("download", { timeout: 20_000 });
    await page.getByRole("button", { name: "导出图片" }).click();
    const download = await downloadPromise;
    expect(download.suggestedFilename()).toMatch(/tripscape-collage-.*\.png/);

    // 撤销 / 重做
    await page.keyboard.press("Control+z");
    await expect(page.getByText("0/60 · 3:4")).toBeVisible();
    await page.keyboard.press("Control+Shift+z");
    await expect(page.getByText("1/60 · 3:4")).toBeVisible();

    // 关闭：有未保存修改 → 确认框；Esc 先退出确认
    await page.getByRole("button", { name: "关闭", exact: true }).click();
    await expect(page.getByText("还有未保存的修改")).toBeVisible();
    await page.keyboard.press("Escape");
    await expect(page.getByText("还有未保存的修改")).toHaveCount(0);
    await expect(dialog).toBeVisible();

    // 再次关闭 → 放弃修改 → 浮窗消失
    await page.getByRole("button", { name: "关闭", exact: true }).click();
    await page.getByRole("button", { name: "放弃修改" }).click();
    await expect(dialog).toHaveCount(0);
  });

  test("撤销重做至少 20 步", async ({ page }) => {
    await page.goto("/login");
    await page.waitForSelector("#boot-screen", { state: "detached", timeout: 30_000 });
    await page.locator('input[autocomplete="username"]').fill("demo");
    await page.locator('input[autocomplete="current-password"]').fill("demo123456");
    await page.locator('form button[type="submit"]').click();
    await page.waitForTimeout(1200);

    await page.goto("/");
    await page.waitForSelector("#boot-screen", { state: "detached", timeout: 30_000 });
    await page.waitForTimeout(1000);
    await page.evaluate(() => window.dispatchEvent(new CustomEvent("ts:open-creation")));
    await expect(page.getByRole("dialog", { name: /创作浮窗/ })).toBeVisible({ timeout: 10_000 });

    // 连加 22 个文字元素
    for (let index = 0; index < 22; index += 1) {
      await page.getByRole("button", { name: "加一段文字" }).click();
    }
    await expect(page.getByText("22/60 · 3:4")).toBeVisible();

    // 连续撤销 22 步 → 回到空白
    for (let index = 0; index < 22; index += 1) {
      await page.keyboard.press("Control+z");
    }
    await expect(page.getByText("0/60 · 3:4")).toBeVisible();
    await expect(page.getByText("从左侧拖入照片或地标碎片开始")).toBeVisible();

    // 连续重做 22 步 → 全部回来
    for (let index = 0; index < 22; index += 1) {
      await page.keyboard.press("Control+Shift+z");
    }
    await expect(page.getByText("22/60 · 3:4")).toBeVisible();
  });
});
