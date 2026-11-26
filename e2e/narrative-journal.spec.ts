/**
 * 行旅识景 TripScape / e2e/narrative-journal.spec
 * 创建日期: 2026-11-25
 *
 * 该模块的工具函数与类型定义；对外导出见文件内 export。
 */

import fs from "node:fs";
import path from "node:path";
import { test, expect } from "@playwright/test";

// 截图落在运行目录（不入库），便于本地人工复核
const SHOTS = path.resolve(__dirname, "../runtime/screenshots");

/**
 * 叙事档案的功能证据：
 *   点地标 → 右侧档案（故事 + 材料）→ 收进手记 → 手记里能翻到
 *   → 刷新后仍在（服务端持久化）→ 从头像菜单进手记 → 关闭回地球。
 *
 * 断言目标：
 *   1. 地球层不再常驻叙事 UI（没有胶片、没有面板）；
 *   2. 档案浮窗自带关闭，手记内容刷新后仍在；
 *   3. 手记有独立入口（头像菜单），不依赖页面顶部的返回。
 */
test.describe("S1 叙事档案与手记", () => {
  test.beforeAll(async ({ request }) => {
    fs.mkdirSync(SHOTS, { recursive: true });
    // 预热：首次卡片组装要加载检索模型，把冷启动排除在 UI 等待之外
    const spots = await request.get("/api/landmarks/spots");
    expect(spots.ok()).toBeTruthy();
    const firstSpotId = (await spots.json()).data[0].id as number;
    const warm = await request.get(`/api/narrative/card/${firstSpotId}`, { timeout: 120_000 });
    expect(warm.ok()).toBeTruthy();
  });

  test("档案可关闭、手记刷新后仍在，且首页不常驻叙事 UI", async ({ page, request }) => {
    const spots = await (await request.get("/api/landmarks/spots")).json();
    const spot = spots.data[0];

    // ---- 登录（真实 UI 登录，拿到真实 token）----
    await page.goto("/login");
    await page.waitForSelector("#boot-screen", { state: "detached", timeout: 30_000 });
    await page.locator('input[autocomplete="username"]').fill("demo");
    await page.locator('input[autocomplete="current-password"]').fill("demo123456");
    await page.locator('form button[type="submit"]').click();
    await expect(page.locator('input[autocomplete="username"]')).toHaveCount(0, {
      timeout: 20_000,
    });

    // ---- 地球层：没有叙事面板，也没有故事胶片 ----
    await page.goto("/");
    await page.waitForSelector("#boot-screen", { state: "detached", timeout: 30_000 });
    await expect(page.getByTestId("narrative-hud")).toHaveCount(1);
    await expect(page.getByTestId("narrative-layer-landmark")).toHaveCount(0);
    await expect(page.getByTestId("narrative-landmark-entry")).toHaveCount(0);

    // ---- 进入地标档案 ----
    await page.goto(`/landmarks/${spot.id}`);
    await page.waitForSelector("#boot-screen", { state: "detached", timeout: 30_000 });
    await expect(page.getByTestId("narrative-layer-landmark")).toBeVisible({ timeout: 30_000 });
    await expect(page.getByTestId("narrative-card-title")).toContainText(spot.name, {
      timeout: 60_000,
    });
    // 故事正文来自预置数据
    await expect(page.getByTestId("narrative-story")).toBeVisible();

    // ---- 收进手记 ----
    await page.getByTestId("narrative-add-to-journal").click();
    await expect(page.getByTestId("narrative-journal-count")).toHaveText(/^[1-9]\d*$/, {
      timeout: 20_000,
    });

    // ---- 手记层：卡片在 ----
    await page.getByTestId("narrative-open-journal").click();
    await expect(page.getByTestId("narrative-layer-journal")).toBeVisible();
    await expect(page.getByTestId("narrative-journal-card").first()).toContainText(spot.name);
    await page.screenshot({ path: path.join(SHOTS, "journal-before-refresh.png"), fullPage: true });

    // ---- 刷新：手记内容仍在（服务端持久化）----
    await page.reload();
    await page.waitForSelector("#boot-screen", { state: "detached", timeout: 30_000 });
    // 刷新后 URL 仍是 /landmarks/:id，档案会自动重开；从档案里切到手记
    await expect(page.getByTestId("narrative-layer-landmark")).toBeVisible({ timeout: 30_000 });
    await page.getByTestId("narrative-open-journal").click();
    await expect(page.getByTestId("narrative-layer-journal")).toBeVisible();
    await expect(page.getByTestId("narrative-journal-card").first()).toContainText(spot.name);
    await page.screenshot({ path: path.join(SHOTS, "journal-after-refresh.png"), fullPage: true });

    // ---- 手记自带关闭：回到地球层，不留面板 ----
    await page.getByTestId("narrative-back").click();
    await expect(page.getByTestId("narrative-layer-journal")).toHaveCount(0);

    // ---- 手记的独立入口：头像菜单（不依赖页面顶部返回）----
    await expect(page.getByTestId("dock-avatar")).toBeVisible({ timeout: 10_000 });
    await page.getByTestId("dock-avatar").click();
    const journalMenuItem = page.getByTestId("dock-menu-journal");
    await expect(journalMenuItem).toBeVisible({ timeout: 10_000 });
    await journalMenuItem.click();
    await expect(page.getByTestId("narrative-layer-journal")).toBeVisible();
    await expect(page.getByTestId("narrative-journal-card").first()).toContainText(spot.name);
    await page.getByTestId("narrative-back").click();
    await expect(page.getByTestId("narrative-layer-journal")).toHaveCount(0);

    // ---- 档案也自带关闭 ----
    await page.goto(`/landmarks/${spot.id}`);
    await page.waitForSelector("#boot-screen", { state: "detached", timeout: 30_000 });
    await expect(page.getByTestId("narrative-layer-landmark")).toBeVisible({ timeout: 30_000 });
    await page.getByTestId("narrative-back").click();
    await expect(page.getByTestId("narrative-layer-landmark")).toHaveCount(0);
  });
});
