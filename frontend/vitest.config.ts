/**
 * 行旅识景 TripScape / vitest.config
 * 创建日期: 2026-10-09
 *
 * 该模块的工具函数与类型定义；对外导出见文件内 export。
 */

import { defineConfig } from "vitest/config";
import react from "@vitejs/plugin-react";
import path from "node:path";

export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      "@": path.resolve(__dirname, "./src"),
    },
  },
  test: {
    environment: "node",
    include: ["tests/frontend/**/*.test.{ts,tsx}"],
  },
});
