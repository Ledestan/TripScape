/**
 * 行旅识景 TripScape / playwright.config
 * 创建日期: 2026-10-09
 *
 * 该模块的工具函数与类型定义；对外导出见文件内 export。
 */

import { defineConfig } from "@playwright/test";
import path from "node:path";
import { fileURLToPath } from "node:url";

const __dirname = path.dirname(fileURLToPath(import.meta.url));

export default defineConfig({
  testDir: path.resolve(__dirname, "./e2e"),
  timeout: 60_000,
  retries: 0,
  use: {
    baseURL: "http://127.0.0.1:8000",
    headless: true,
    viewport: { width: 1280, height: 800 },
  },
  reporter: [["list"]],
});
