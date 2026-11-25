import fs from "node:fs";
import path from "node:path";
import { test, expect } from "@playwright/test";

// 截图落在运行目录（不入库），便于本地人工复核
const SHOTS = path.resolve(__dirname, "../runtime/screenshots");

/**
 * 三层空间切换的功能证据：
 *   地球层 → 点地标进入地标层 → 把叙事卡片收进手记
 *   → 打开手记层 → 刷新页面 → 手记里的卡片仍在 → 逐层返回。
 *
 * 断言目标：
 *   1. 三层切换可感知（每层有独立容器）且可返回；
 *   2. 手记持久化在服务端（刷新后从 /api/narrative/journal 取回），不是前端内存；
 *   3. 刷新前后各截一张手记截图作为人工复核材料。
 *
 * 运行前置：前端按当前源码构建、后端启动即可（2.0 已是默认行为，无开关）。
 */
test.describe("S1 三层空间切换", () => {
  test.beforeAll(async ({ request }) => {
    fs.mkdirSync(SHOTS, { recursive: true });

    // 预热：首次卡片组装要加载检索模型（冷启动数十秒），先把冷启动排除在 UI 等待之外
    const spots = await request.get("/api/landmarks/spots");
    expect(spots.ok()).toBeTruthy();
    const firstSpotId = (await spots.json()).data[0].id as number;
    const warm = await request.get(`/api/narrative/card/${firstSpotId}`, { timeout: 120_000 });
    expect(warm.ok()).toBeTruthy();
  });

  test("收进手记的叙事卡片刷新后仍在，且三层可返回", async ({ page }) => {
    // ---- 登录（真实 UI 登录，拿到真实 token）----
    await page.goto("/login");
    await page.waitForSelector("#boot-screen", { state: "detached", timeout: 30_000 });
    await page.locator('input[autocomplete="username"]').fill("demo");
    await page.locator('input[autocomplete="current-password"]').fill("demo123456");
    await page.locator('form button[type="submit"]').click();
    await expect(page.locator('input[autocomplete="username"]')).toHaveCount(0, {
      timeout: 20_000,
    });
    await page.goto("/");
    await page.waitForSelector("#boot-screen", { state: "detached", timeout: 30_000 });

    // ---- 地球层：故事胶片可见 ----
    const hud = page.getByTestId("narrative-hud");
    await expect(hud).toBeVisible({ timeout: 30_000 });
    await expect(page.getByTestId("narrative-layer-globe")).toBeVisible();

    // ---- 点一个地标：进入地标层 ----
    const entry = page.getByTestId("narrative-landmark-entry").first();
    await expect(entry).toBeVisible({ timeout: 20_000 });
    const landmarkName = (await entry.getAttribute("data-landmark-name")) || "";
    expect(landmarkName.length).toBeGreaterThan(0);
    await entry.click();

    await expect(page.getByTestId("narrative-layer-landmark")).toBeVisible({ timeout: 20_000 });
    await expect(page.getByTestId("narrative-card-title")).toContainText(landmarkName, {
      timeout: 60_000,
    });

    // ---- 收进手记 ----
    await page.getByTestId("narrative-add-to-journal").click();
    // 同一账号历史手记会累加，故只断言正整数
    await expect(page.getByTestId("narrative-journal-count")).toHaveText(/^[1-9]\d*$/, {
      timeout: 20_000,
    });

    // ---- 手记层：卡片在 ----
    await page.getByTestId("narrative-open-journal").click();
    await expect(page.getByTestId("narrative-layer-journal")).toBeVisible();
    await expect(page.getByTestId("narrative-journal-card").first()).toContainText(landmarkName);
    await page.screenshot({
      path: path.join(SHOTS, "journal-before-refresh.png"),
      fullPage: true,
    });

    // ---- 刷新：手记内容仍在（服务端持久化）----
    await page.reload();
    await page.waitForSelector("#boot-screen", { state: "detached", timeout: 30_000 });
    await expect(page.getByTestId("narrative-hud")).toBeVisible({ timeout: 30_000 });
    await page.getByTestId("narrative-open-journal").click();
    await expect(page.getByTestId("narrative-layer-journal")).toBeVisible();
    await expect(page.getByTestId("narrative-journal-card").first()).toContainText(landmarkName);
    await page.screenshot({
      path: path.join(SHOTS, "journal-after-refresh.png"),
      fullPage: true,
    });

    // ---- 刷新后无当前地标：手记 → 地球层 ----
    await page.getByTestId("narrative-back").click();
    await expect(page.getByTestId("narrative-layer-globe")).toBeVisible();

    // ---- 再进地标层后逐层返回：手记 → 地标 → 地球 ----
    await page.getByTestId("narrative-landmark-entry").first().click();
    await expect(page.getByTestId("narrative-layer-landmark")).toBeVisible();
    await page.getByTestId("narrative-open-journal").click();
    await expect(page.getByTestId("narrative-layer-journal")).toBeVisible();
    await page.getByTestId("narrative-back").click();
    await expect(page.getByTestId("narrative-layer-landmark")).toBeVisible();
    await page.getByTestId("narrative-back").click();
    await expect(page.getByTestId("narrative-layer-globe")).toBeVisible();
  });
});
