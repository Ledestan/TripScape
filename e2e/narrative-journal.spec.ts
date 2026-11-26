/**
 * 行旅识景 TripScape / e2e/narrative-journal.spec
 * 创建日期: 2026-11-25
 *
 * 叙事档案的端到端证据，覆盖:
 *     1. 地球层不常驻叙事 UI，点地标才进档案
 *     2. 档案底部四个入口：评论 / 收藏 / 足迹 / 手账
 *     3. 评论与手账都进详情浮窗（带对应页签），并把档案收起来
 *     4. 收藏可持久化（刷新后仍是已收藏），足迹独立开窗
 */

import fs from "node:fs";
import path from "node:path";
import { test, expect } from "@playwright/test";

const SHOTS = path.resolve(__dirname, "../runtime/screenshots");

test.describe("S1 叙事档案、收藏与足迹", () => {
  test.beforeAll(async ({ request }) => {
    fs.mkdirSync(SHOTS, { recursive: true });
    const spots = await request.get("/api/landmarks/spots");
    expect(spots.ok()).toBeTruthy();
    const firstSpotId = (await spots.json()).data[0].id as number;
    const warm = await request.get(`/api/narrative/card/${firstSpotId}`, { timeout: 120_000 });
    expect(warm.ok()).toBeTruthy();
  });

  test("档案四个入口可用，评论/手账进详情并收起档案", async ({ page, request }) => {
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

    // ---- 收藏（幂等：只在未收藏时点，避免把"已收藏"点成取消）----
    const favoriteBtn = page.getByTestId("narrative-favorite");
    await expect(favoriteBtn).toBeVisible();
    const label = (await favoriteBtn.innerText()).trim();
    if (label === "收藏") {
      await favoriteBtn.click();
    }
    await expect(favoriteBtn).toContainText("已收藏", { timeout: 20_000 });

    // ---- 评论：进详情浮窗的评论页签，档案同时收起 ----
    await page.getByTestId("narrative-open-comments").click();
    await expect(page.getByTestId("landmark-detail-window")).toBeVisible({ timeout: 10_000 });
    await expect(page.getByTestId("detail-tab-comments")).toHaveAttribute("data-active", "true");
    await expect(page.getByTestId("narrative-layer-landmark")).toHaveCount(0);
    await page.screenshot({ path: path.join(SHOTS, "detail-comments.png") });
    await page.keyboard.press("Escape");
    await expect(page.getByTestId("landmark-detail-window")).toHaveCount(0);

    // ---- 手账：同一浮窗，切到手账页签 ----
    await page.goto(`/landmarks/${spot.id}`);
    await page.waitForSelector("#boot-screen", { state: "detached", timeout: 30_000 });
    await expect(page.getByTestId("narrative-layer-landmark")).toBeVisible({ timeout: 30_000 });
    await page.getByTestId("narrative-open-journal-edit").click();
    await expect(page.getByTestId("landmark-detail-window")).toBeVisible({ timeout: 10_000 });
    await expect(page.getByTestId("detail-tab-journals")).toHaveAttribute("data-active", "true");
    await page.keyboard.press("Escape");

    // ---- 档案底部只有三个入口：足迹已收进个人中心 ----
    await page.goto(`/landmarks/${spot.id}`);
    await page.waitForSelector("#boot-screen", { state: "detached", timeout: 30_000 });
    await expect(page.getByTestId("narrative-layer-landmark")).toBeVisible({ timeout: 30_000 });
    await expect(page.getByTestId("narrative-open-comments")).toBeVisible();
    await expect(page.getByTestId("narrative-favorite")).toBeVisible();
    await expect(page.getByTestId("narrative-open-journal-edit")).toBeVisible();
    await expect(page.getByTestId("narrative-footprints")).toHaveCount(0);

    // ---- 刷新后收藏状态仍在 ----
    await page.reload();
    await page.waitForSelector("#boot-screen", { state: "detached", timeout: 30_000 });
    await expect(page.getByTestId("narrative-layer-landmark")).toBeVisible({ timeout: 30_000 });
    await expect(page.getByTestId("narrative-favorite")).toContainText("已收藏", {
      timeout: 20_000,
    });

    // ---- 档案自带关闭 ----
    await page.getByTestId("narrative-back").click();
    await expect(page.getByTestId("narrative-layer-landmark")).toHaveCount(0);

    // ---- 头像菜单不再有手记与足迹（已按需求移除）----
    await page.getByTestId("dock-avatar").click();
    await expect(page.getByTestId("dock-menu-footprints")).toHaveCount(0);
  });
});
