import path from "node:path";
import { test, expect } from "@playwright/test";

const EVIDENCE = path.resolve(__dirname, "../docs/competition/evidence");

/**
 * S1 功能证据（SPEC §3.1）：
 *   从 globe 出发 → 点击地标进入 landmark 层 → 把叙事卡片加入手账
 *   → 打开 journal 层 → **刷新页面** → 断言手账中卡片仍在 → 逐层返回。
 *
 * 断言目标：
 *   1. 三层切换可感知（每层有独立容器与标题）且可返回；
 *   2. 手账持久化在服务端（刷新后从 /api/narrative/journal 取回），不是前端内存；
 *   3. 刷新前后各截一张 journal 截图作为人工复核证据。
 *
 * 运行前置（见 plan.md §6）：前端按当前源码构建、后端启动即可（2.0 已是默认行为，无开关）。
 */
test.describe("S1 三层空间切换", () => {
  test.beforeAll(async ({ request }) => {
    // 预热：首次卡片组装要加载检索模型（bge-small-zh，冷启动数十秒）。
    // 预热对象就是测试将要点击的第一个地标，把模型冷启动排除在 UI 等待之外，
    // 避免把环境耗时误判成交互缺陷（断言本身不因此放宽）。
    const spots = await request.get("/api/landmarks/spots");
    expect(spots.ok()).toBeTruthy();
    const firstSpotId = (await spots.json()).data[0].id as number;
    const warm = await request.get(`/api/narrative/card/${firstSpotId}`, { timeout: 120_000 });
    expect(warm.ok()).toBeTruthy();
  });

  test("加入手账的叙事卡片刷新后仍在，且三层可返回", async ({ page }) => {
    // ---- 登录（真实 UI 登录，拿到真实 token）----
    await page.goto("/login");
    await page.waitForSelector("#boot-screen", { state: "detached", timeout: 30_000 });
    await page.locator('input[autocomplete="username"]').fill("demo");
    await page.locator('input[autocomplete="current-password"]').fill("demo123456");
    await page.locator('form button[type="submit"]').click();
    // 登录浮窗关闭即成功（token 持久化在 localStorage）；随后回地球页
    await expect(page.locator('input[autocomplete="username"]')).toHaveCount(0, {
      timeout: 20_000,
    });
    await page.goto("/");
    await page.waitForSelector("#boot-screen", { state: "detached", timeout: 30_000 });

    // ---- globe 层：叙事层入口可见 ----
    const hud = page.getByTestId("narrative-hud");
    await expect(hud).toBeVisible({ timeout: 30_000 });
    await expect(page.getByTestId("narrative-layer-globe")).toBeVisible();

    // ---- 点击地标：进入 landmark 层 ----
    const entry = page.getByTestId("narrative-landmark-entry").first();
    await expect(entry).toBeVisible({ timeout: 20_000 });
    const landmarkName = (await entry.getAttribute("data-landmark-name")) || "";
    expect(landmarkName.length).toBeGreaterThan(0);
    await entry.click();

    const landmarkLayer = page.getByTestId("narrative-layer-landmark");
    await expect(landmarkLayer).toBeVisible({ timeout: 20_000 });
    // 卡片标题包含地标名（卡片来自真实卡片接口）
    await expect(page.getByTestId("narrative-card-title")).toContainText(landmarkName, {
      timeout: 60_000,
    });

    // ---- 加入手账 ----
    await page.getByTestId("narrative-add-to-journal").click();
    // 手账计数从服务端刷新回来后 ≥1（同一账号历史手账会累加，故只断言正整数）
    await expect(page.getByTestId("narrative-journal-count")).toHaveText(/^[1-9]\d*$/, {
      timeout: 20_000,
    });

    // ---- journal 层：卡片在 ----
    await page.getByTestId("narrative-open-journal").click();
    await expect(page.getByTestId("narrative-layer-journal")).toBeVisible();
    const journalCard = page.getByTestId("narrative-journal-card").first();
    await expect(journalCard).toContainText(landmarkName);
    await page.screenshot({
      path: path.join(EVIDENCE, "s1-journal-before-refresh.png"),
      fullPage: true,
    });

    // ---- 刷新：手账内容仍在（服务端持久化）----
    await page.reload();
    await page.waitForSelector("#boot-screen", { state: "detached", timeout: 30_000 });
    await expect(page.getByTestId("narrative-hud")).toBeVisible({ timeout: 30_000 });
    await page.getByTestId("narrative-open-journal").click();
    await expect(page.getByTestId("narrative-layer-journal")).toBeVisible();
    await expect(page.getByTestId("narrative-journal-card").first()).toContainText(landmarkName);
    await page.screenshot({
      path: path.join(EVIDENCE, "s1-journal-after-refresh.png"),
      fullPage: true,
    });

    // ---- 可返回：刷新后无当前地标，journal → globe ----
    await page.getByTestId("narrative-back").click();
    await expect(page.getByTestId("narrative-layer-globe")).toBeVisible();

    // ---- 再进地标层后逐层返回：journal → landmark → globe ----
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
