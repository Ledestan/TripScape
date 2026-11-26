/**
 * 行旅识景 TripScape / e2e/narrative-journal.spec
 * 创建日期: 2026-11-25
 *
 * 叙事档案的端到端证据，覆盖:
 *     1. 地球层不常驻叙事 UI，点地标才进档案
 *     2. 档案里能收藏、看评论、看足迹、写手账
 *     3. 收藏同步到「手记」（收藏列表），刷新后仍在
 *     4. 手记与足迹都有独立入口（头像菜单），不依赖顶部返回
 */

import fs from "node:fs";
import path from "node:path";
import { test, expect } from "@playwright/test";

// 截图落在运行目录（不入库），便于本地人工复核
const SHOTS = path.resolve(__dirname, "../runtime/screenshots");

test.describe("S1 叙事档案、收藏与足迹", () => {
  test.beforeAll(async ({ request }) => {
    fs.mkdirSync(SHOTS, { recursive: true });
    // 预热：首次卡片组装要读预置页面，把冷启动排除在 UI 等待之外
    const spots = await request.get("/api/landmarks/spots");
    expect(spots.ok()).toBeTruthy();
    const firstSpotId = (await spots.json()).data[0].id as number;
    const warm = await request.get(`/api/narrative/card/${firstSpotId}`, { timeout: 120_000 });
    expect(warm.ok()).toBeTruthy();
  });

  test("档案可关闭、收藏进入手记、足迹与评论各有入口", async ({ page, request }) => {
    const spots = await (await request.get("/api/landmarks/spots")).json();
    const spot = spots.data[0];

    // ---- 登录 ----
    await page.goto("/login");
    await page.waitForSelector("#boot-screen", { state: "detached", timeout: 30_000 });
    await page.locator('input[autocomplete="username"]').fill("demo");
    await page.locator('input[autocomplete="current-password"]').fill("demo123456");
    await page.locator('form button[type="submit"]').click();
    await expect(page.locator('input[autocomplete="username"]')).toHaveCount(0, {
      timeout: 20_000,
    });

    // ---- 地球层没有常驻叙事 UI ----
    await page.goto("/");
    await page.waitForSelector("#boot-screen", { state: "detached", timeout: 30_000 });
    await expect(page.getByTestId("narrative-hud")).toHaveCount(1);
    await expect(page.getByTestId("narrative-layer-landmark")).toHaveCount(0);

    // ---- 进入档案 ----
    await page.goto(`/landmarks/${spot.id}`);
    await page.waitForSelector("#boot-screen", { state: "detached", timeout: 30_000 });
    await expect(page.getByTestId("narrative-layer-landmark")).toBeVisible({ timeout: 30_000 });
    await expect(page.getByTestId("narrative-card-title")).toContainText(spot.name, {
      timeout: 60_000,
    });
    await expect(page.getByTestId("narrative-story")).toBeVisible();

    // ---- 收藏（幂等：已收藏就不重复点）----
    const favoriteBtn = page.getByTestId("narrative-favorite");
    await expect(favoriteBtn).toBeVisible();
    if ((await favoriteBtn.innerText()).includes("收藏")) {
      await favoriteBtn.click();
    }
    await expect(favoriteBtn).toContainText("已收藏", { timeout: 20_000 });

    // ---- 手记 = 收藏列表 ----
    await page.getByTestId("narrative-open-journal").click();
    await expect(page.getByTestId("narrative-layer-journal")).toBeVisible();
    await expect(page.getByTestId("narrative-journal-card").first()).toContainText(spot.name);
    await page.screenshot({ path: path.join(SHOTS, "favorites-panel.png"), fullPage: true });

    // ---- 刷新：收藏仍在（服务端持久化）----
    await page.reload();
    await page.waitForSelector("#boot-screen", { state: "detached", timeout: 30_000 });
    await expect(page.getByTestId("narrative-layer-landmark")).toBeVisible({ timeout: 30_000 });
    await expect(page.getByTestId("narrative-favorite")).toContainText("已收藏", {
      timeout: 20_000,
    });
    await page.getByTestId("narrative-open-journal").click();
    await expect(page.getByTestId("narrative-journal-card").first()).toContainText(spot.name);
    await page.getByTestId("narrative-back").click();
    await expect(page.getByTestId("narrative-layer-journal")).toHaveCount(0);

    // ---- 足迹：面板按钮打开浮窗 ----
    await page.getByTestId("narrative-layer-landmark").waitFor();
    await page.getByTestId("narrative-footprints").click();
    await expect(page.getByRole("dialog").or(page.locator("text=我的足迹").first())).toBeVisible({
      timeout: 10_000,
    });
    await page.keyboard.press("Escape");

    // ---- 评论：打开地标浮窗（自带评论 Tab）----
    await page.getByTestId("narrative-open-comments").click();
    await expect(page.locator("text=评论").first()).toBeVisible({ timeout: 10_000 });
    await page.keyboard.press("Escape");

    // ---- 档案自带关闭 ----
    await page.getByTestId("narrative-back").click();
    await expect(page.getByTestId("narrative-layer-landmark")).toHaveCount(0);

    // ---- 头像菜单：手记与足迹都有独立入口 ----
    await expect(page.getByTestId("dock-avatar")).toBeVisible({ timeout: 10_000 });
    await page.getByTestId("dock-avatar").click();
    await expect(page.getByTestId("dock-menu-journal")).toBeVisible({ timeout: 10_000 });
    await expect(page.getByTestId("dock-menu-footprints")).toBeVisible();
    await page.getByTestId("dock-menu-footprints").click();
    await expect(page.locator("text=我的足迹").first()).toBeVisible({ timeout: 10_000 });
    await page.keyboard.press("Escape");
  });
});
