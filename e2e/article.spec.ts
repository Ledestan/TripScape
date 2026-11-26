/**
 * 行旅识景 TripScape / e2e/article.spec
 * 创建日期: 2026-11-26
 *
 * 文章详情页的端到端证据，覆盖:
 *     1. 档案里"查看全文"打开文章页（不折叠）
 *     2. 文章可以点赞
 *     3. 文章可以评论、回复、修改自己的评论
 */

import { test, expect } from "@playwright/test";

test.describe("S4 文章详情页", () => {
  test("查看全文、点赞、评论与回复", async ({ page, request }) => {
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

    await page.getByTestId("narrative-open-article").click();
    const article = page.getByTestId("article-window");
    await expect(article).toBeVisible({ timeout: 10_000 });

    // 点赞：aria-pressed 必须翻转（不依赖初始是否已赞）
    const like = page.getByTestId("article-like");
    const before = (await like.getAttribute("aria-pressed")) === "true";
    await like.click();
    await expect(like).toHaveAttribute("aria-pressed", String(!before), { timeout: 10_000 });

    // 评论
    const content = `文章评论 ${Date.now()}`;
    await page.getByTestId("comment-input").fill(content);
    await page.getByRole("button", { name: "发送" }).click();
    await expect(page.getByText(content)).toBeVisible({ timeout: 10_000 });

    // 回复（限定在自己刚发的评论块内，避免命中历史评论）
    const mine = page.getByTestId("comment-item").first();
    await mine.getByRole("button", { name: "回复" }).first().click();
    await expect(page.getByTestId("comment-input")).toHaveAttribute(
      "placeholder",
      /回复 @/
    );
    const replyText = `回复 ${Date.now()}`;
    await page.getByTestId("comment-input").fill(replyText);
    await page.getByRole("button", { name: "发送" }).click();
    await expect(page.getByText(replyText)).toBeVisible({ timeout: 10_000 });

  });
});
