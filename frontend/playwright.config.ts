/**
 * 行旅识景 TripScape / playwright.config
 * 创建日期: 2026-11-25
 *
 * e2e 唯一配置：用例在仓库根 e2e/ 下，覆盖叙事档案与手记的完整回路。
 *
 * 运行前置:
 *     1. 前端按当前源码构建：pnpm --dir frontend build
 *     2. 后端在 127.0.0.1:8000 运行：python backend/manage.py runserver 127.0.0.1:8000 --noreload
 *     3. 在 frontend/ 下执行：npx playwright test
 */

import { defineConfig } from "@playwright/test";
import path from "node:path";
import { fileURLToPath } from "node:url";

const __dirname = path.dirname(fileURLToPath(import.meta.url));

export default defineConfig({
  testDir: path.resolve(__dirname, "../e2e"),
  timeout: 120_000,
  retries: 0,
  fullyParallel: false,
  workers: 1,
  use: {
    baseURL: "http://127.0.0.1:8000",
    headless: true,
    viewport: { width: 1440, height: 900 },
  },
  reporter: [["list"]],
});
