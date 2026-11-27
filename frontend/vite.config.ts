/**
 * 行旅识景 TripScape / vite.config
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
         * 只拆"入口必需"的依赖（react / 数据层）。
         *
         * three 与 @react-three 故意不单独成 chunk：实测拆出来后入口会静态依赖它，
         * 网络慢时首屏要等 700KB 的 3D 引擎才能挂载，片头反而被拖住。
         * 让它留在 GlobeApp 的懒加载分包里，首屏只需等地球那一个 chunk。
         * 也不兜底聚成 vendor：全量 vendor 会与 three/react 形成循环，运行时报 TDZ。
         */
        manualChunks(id) {
          if (!id.includes("node_modules")) return undefined;
          if (id.includes("@tanstack")) return "query";
          // 必须精确匹配：宽泛的 /react 会把 lucide-react、@radix-ui/react-*、
          // @react-three/* 一起吸进来（实测该 chunk 从 150KB 膨胀到 999KB）
          if (
            /node_modules[\\/](react|react-dom|react-router|react-router-dom|scheduler)[\\/]/.test(
              id
            )
          ) {
            return "react";
          }
          return undefined;
        },
      },
    },
  },
});