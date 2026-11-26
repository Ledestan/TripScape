/**
 * 行旅识景 TripScape / e2e/journal-canvas.spec
 * 创建日期: 2026-11-26
 *
 * 手账画布编辑器的端到端证据，覆盖:
 *     1. 从地标页打开写手账，画布 3:4 可用（加文字 / 加碎片）
 *     2. 发布后画布 JSON 落到 /api/journals，元素按类型存下来
 *     3. 图层计数与后端结构一致（2 个元素、ratio=3:4）
 */

import { test, expect } from "@playwright/test";

test.describe("S2 手账画布", () => {
  test("加文字与碎片后发布，画布 JSON 存进手账", async ({ page, request }) => {
    const spots = await (await request.get("/api/landmarks/spots")).json();
    const landmark = spots.data[0];

    await page.goto("/login");
    await page.waitForSelector("#boot-screen", { state: "detached", timeout: 30_000 });
    await page.locator('input[autocomplete="username"]').fill("demo");
    await page.locator('input[autocomplete="current-password"]').fill("demo123456");
    await page.locator('form button[type="submit"]').click();
    await page.waitForTimeout(1200);

    await page.goto(`/landmarks/${landmark.id}`);
    await page.waitForSelector("#boot-screen", { state: "detached", timeout: 30_000 });
    await page.waitForTimeout(1200);

    // 档案里的"写手账"入口由事件驱动；这里直接派发，等价于点按钮
    await page.evaluate((id) => {
      window.dispatchEvent(new CustomEvent("ts:open-journal-edit", { detail: id }));
    }, landmark.id);

    await expect(page.getByText("手账画布（3:4）")).toBeVisible({ timeout: 20_000 });
    await expect(page.getByText("3:4 · 0/40")).toBeVisible();

    await page.getByRole("button", { name: "文字" }).click();
    await expect(page.getByText("3:4 · 1/40")).toBeVisible();

    await page.getByRole("button", { name: "碎片" }).click();
    await expect(page.getByText("3:4 · 2/40")).toBeVisible();

    // 直接在画布里上传照片（新版写手账不再走旧版九宫格）
    const png = Buffer.from(
      "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+ip1sAAAAASUVORK5CYII=",
      "base64"
    );
    await page.locator('input[type="file"]').setInputFiles({
      name: "trip.png",
      mimeType: "image/png",
      buffer: png,
    });
    await expect(page.getByText("3:4 · 3/40")).toBeVisible({ timeout: 20_000 });

    const title = `画布 e2e ${Date.now()}`;
    await page.locator('input[maxlength="128"]').first().fill(title);
    await page.getByRole("button", { name: /发布手账/ }).click();
    await expect(page.getByText("手账已发布，足迹 +1")).toBeVisible({ timeout: 20_000 });

    const token = await page.evaluate(() => {
      const raw = localStorage.getItem("tripscape-auth");
      return raw ? (JSON.parse(raw) as { state: { token: string } }).state.token : "";
    });
    const mine = await (
      await request.get("/api/journals/mine", { headers: { Authorization: `Bearer ${token}` } })
    ).json();
    const created = (mine.data as { id: number; title: string }[]).find((j) => j.title === title);
    expect(created).toBeTruthy();

    const detail = await (
      await request.get(`/api/journals/${created!.id}`, {
        headers: { Authorization: `Bearer ${token}` },
      })
    ).json();
    const canvas = detail.data.canvas as { ratio: string; elements: { type: string }[] };
    expect(canvas.ratio).toBe("3:4");
    expect(canvas.elements.map((element) => element.type)).toEqual(["text", "fragment", "photo"]);

    // 查看端要能把画布渲染出来（否则存了也看不见）
    await page.evaluate((id) => {
      window.dispatchEvent(new CustomEvent("ts:open-journal-view", { detail: id }));
    }, created!.id);
    await expect(page.getByRole("dialog")).toBeVisible({ timeout: 10_000 });
    await expect(page.locator('[role="dialog"] canvas').first()).toBeVisible({ timeout: 10_000 });
  });
});
