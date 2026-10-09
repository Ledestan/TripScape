import { test, expect } from "@playwright/test";

test("进入 app 页：5 秒加载动画 -> 3D 地球 -> 搜索 -> 消息条", async ({ page }) => {
  await page.goto("/");
  // 启动动画存在
  await expect(page.locator("#boot-screen")).toBeVisible();
  // 等待动画结束（5s + 淡出）
  await page.waitForSelector("#boot-screen", { state: "detached", timeout: 10_000 });
  // 消息条（左下通知条形态）
  await expect(page.locator('button[title="展开智能问答"]')).toBeVisible({ timeout: 20_000 });
  // 地球 canvas 渲染
  await page.waitForSelector("canvas", { timeout: 15_000 });
});

test("灵动岛搜索：点击展开 -> 回车搜索 -> 结果浮窗", async ({ page }) => {
  await page.goto("/");
  await page.waitForSelector("#boot-screen", { state: "detached", timeout: 10_000 });
  const island = page.locator("div.cursor-pointer.flex.items-center.gap-2.rounded-full").first();
  await island.click();
  await page.getByPlaceholder("搜索地标、手账、评论、用户…").fill("塔");
  await page.keyboard.press("Enter");
  await expect(page.locator("text=的结果").first()).toBeVisible({ timeout: 10_000 });
});

test("登录页可达", async ({ page }) => {
  await page.goto("/login");
  await expect(page.getByText("行旅识景", { exact: false }).first()).toBeVisible({ timeout: 15_000 });
  await expect(page.getByText("登录", { exact: true }).first()).toBeVisible();
});

test("demo 账号登录成功", async ({ page }) => {
  await page.goto("/login");
  await page.getByPlaceholder("demo").fill("demo");
  await page.getByPlaceholder("••••••").fill("demo123456");
  await page.locator("form").getByRole("button", { name: "登录", exact: true }).click();
  await page.waitForURL("/", { timeout: 20_000 });
});

test("管理后台登录入口", async ({ page }) => {
  await page.goto("/admin");
  await expect(page.getByText("管理员登录")).toBeVisible({ timeout: 15_000 });
});

test("无效分享链接给出友好提示", async ({ page }) => {
  await page.goto("/share/invalid-token-123");
  await expect(page.getByText("分享链接不存在或已失效")).toBeVisible({ timeout: 15_000 });
});

test("搜索页可达并支持类型切换", async ({ page }) => {
  await page.goto("/search");
  await expect(page.getByText("全局搜索")).toBeVisible({ timeout: 15_000 });
  await page.getByRole("button", { name: "手账", exact: true }).click();
});
