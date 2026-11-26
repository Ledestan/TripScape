/**
 * 行旅识景 TripScape / e2e/journal-canvas.spec
 * 创建日期: 2026-11-26
 *
 * 写手账（创作浮窗）的端到端证据，覆盖:
 *     1. 从地标详情点「写手账」打开创作浮窗（不再走旧版表单）
 *     2. 加文字 + 直接在浮窗里上传照片 → 画布计数增加
 *     3. 保存后画布 JSON 落到 /api/journals，元素类型齐全
 *     4. 查看端能把画布渲染出来
 */

import { test, expect } from "@playwright/test";

test.describe("S2 写手账（创作浮窗）", () => {
  test("从地标写手账：加文字、上传照片、保存并可查看", async ({ page, request }) => {
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
    await expect(page.getByTestId("narrative-layer-landmark")).toBeVisible({ timeout: 30_000 });

    // 档案 → 手账页签 → 写手账
    await page.getByTestId("narrative-open-journal-edit").click();
    await expect(page.getByTestId("landmark-detail-window")).toBeVisible({ timeout: 10_000 });
    await page.getByRole("button", { name: "写手账" }).click();

    const compose = page.getByRole("dialog", { name: /写手账创作浮窗/ });
    await expect(compose).toBeVisible({ timeout: 20_000 });
    await expect(page.getByText("0/60 · 3:4")).toBeVisible();

    // 加一段文字
    await page.getByRole("button", { name: "加文字" }).click();
    await expect(page.getByText("1/60 · 3:4")).toBeVisible();

    // 在浮窗里直接上传一张照片，再从素材栏点进画布
    const png = Buffer.from(
      "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+ip1sAAAAASUVORK5CYII=",
      "base64"
    );
    await page.locator('input[type="file"]').setInputFiles({
      name: "trip.png",
      mimeType: "image/png",
      buffer: png,
    });
    await expect(page.getByRole("button", { name: "trip.png" })).toBeVisible({ timeout: 20_000 });
    await page.getByRole("button", { name: "trip.png" }).click();
    await expect(page.getByText("2/60 · 3:4")).toBeVisible();

    // 标题 + 保存
    const title = `拼贴手账 ${Date.now()}`;
    await page.getByTestId("journal-compose-title").fill(title);
    await page.getByTestId("compose-save-draft").click();
    await expect(page.getByText("草稿已保存")).toBeVisible({ timeout: 20_000 });

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
    expect(canvas.elements.map((element) => element.type)).toEqual(["text", "photo"]);

    // 查看端渲染画布
    await page.evaluate((id) => {
      window.dispatchEvent(new CustomEvent("ts:open-journal-view", { detail: id }));
    }, created!.id);
    await expect(page.getByRole("dialog").last()).toBeVisible({ timeout: 10_000 });
    await expect(page.locator('[role="dialog"] canvas').first()).toBeVisible({ timeout: 10_000 });
  });
});
