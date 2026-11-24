import { defineConfig } from "@playwright/test";
import path from "node:path";
import { fileURLToPath } from "node:url";

const __dirname = path.dirname(fileURLToPath(import.meta.url));

/**
 * TripScape 2.0 证据测试配置（SPEC §3.1：测试写在仓库根 e2e/ 下）。
 *
 * 与既有 `playwright.config.ts`（testDir=./e2e）并存，互不影响：
 * - 该配置服务 S1 三层空间切换的 e2e 证据；
 * - 复用 frontend/node_modules 的 @playwright/test 与同一 baseURL（127.0.0.1:8000）。
 *
 * 运行前置（见 plan.md §6）：
 *   1. 前端已按当前源码构建：corepack pnpm --dir frontend build
 *   2. 后端以 tripScape2 开启运行：
 *      $env:DB_ENGINE='sqlite'; $env:TRIPSCAPE2_ENABLED='true'
 *      .venv\Scripts\python.exe backend\manage.py runserver 127.0.0.1:8000 --noreload
 */
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
