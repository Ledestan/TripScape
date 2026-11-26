/**
 * 行旅识景 TripScape / vite.config
 * 创建日期: 2026-10-09
 *
 * 前端构建配置，负责:
 *     1. 路径别名 @ -> src，开发代理到 Django（/api /media /landmarks）
 *     2. 产物分包：把 three、React、数据层拆成独立的长期缓存 chunk
 *
 * 依赖:
 *     依赖库: vite, @vitejs/plugin-react
 *
 * 用法:
 *     pnpm --dir frontend build
 *
 * 注意:
 *     1. three 与 @react-three/* 体积最大且极少变动，单独成 chunk：
 *        改业务代码时用户只需重下几十 KB，而不是整个 3D 栈。
 *     2. 事件总线（features/globe/bus.ts）已从 Globe.tsx 抽出，
 *        因此非地球模块不再把 three 拖进自己的分包。
 */

import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import path from "node:path";

export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      "@": path.resolve(__dirname, "./src"),
    },
  },
  server: {
    port: 5173,
    proxy: {
      "/api": {
        target: "http://127.0.0.1:8000",
        changeOrigin: true,
      },
      "/media": {
        target: "http://127.0.0.1:8000",
        changeOrigin: true,
      },
      "/landmarks": {
        target: "http://127.0.0.1:8000",
        changeOrigin: true,
      },
    },
  },
  build: {
    outDir: "dist",
    sourcemap: false,
    rollupOptions: {
      output: {
        /**
         * 用函数而不是包名数组：drei / fiber 大量走子路径导入
         * （@react-three/drei/core/...），数组形式匹配不到，会继续留在业务分包里。
         */
        manualChunks(id) {
          if (!id.includes("node_modules")) return undefined;
          if (
            id.includes("@react-three") ||
            id.includes("/three/") ||
            id.includes("three-stdlib") ||
            id.includes("@use-gesture")
          ) {
            return "three";
          }
          if (id.includes("@tanstack")) return "query";
          if (id.includes("/react") || id.includes("/scheduler")) return "react";
          // 不再兜底聚成 vendor：全量 vendor 包会与 three/react 形成循环，运行时报 TDZ
        },
      },
    },
  },
});
