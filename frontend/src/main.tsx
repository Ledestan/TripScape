/**
 * 行旅识景 TripScape / src/main
 *
 * 应用入口与启动片头调度，负责:
 *     1. 挂载 React 根节点与查询客户端
 *     2. 片头退场时机：至少播到标题落完（2.6s），应用一就绪就淡出，最多等 8s
 *
 * 依赖:
 *     依赖库: react, react-dom, @tanstack/react-query, sonner
 *
 * 用法:
 *     由 index.html 以 <script type="module" src="/src/main.tsx"> 加载
 *
 * 注意:
 *     1. #boot-screen 在 #root 之外，React 不管它，所以由这里手动淡出。
 *     2. 就绪信号是 window 上的 `ts:app-ready`（App 挂载后派发），
 *        这样首屏不再是"固定 5 秒"，网络快就早一点进，网络慢也不会黑屏。
 */

import React from "react";
import ReactDOM from "react-dom/client";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { Toaster } from "sonner";
import App from "./App";
import "./styles/index.css";

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      retry: 1,
      staleTime: 30_000,
      refetchOnWindowFocus: false,
    },
  },
});

/** 片头最短停留：标题 2.55s 落完、进度条 3.2s 走满，留到 3.4s 再退场 */
const SPLASH_MIN_MS = 3400;
/** 兜底上限：地球迟迟不来也不让片头赖着不走 */
const SPLASH_MAX_MS = 8000;

let hidden = false;

function hideBootScreen() {
  if (hidden) return;
  hidden = true;
  const boot = document.getElementById("boot-screen");
  if (!boot) return;
  boot.style.transition = "opacity .4s ease";
  boot.style.opacity = "0";
  window.setTimeout(() => boot.remove(), 400);
}

function onAppReady() {
  // 用 performance.now()：从导航开始算，而不是从 JS 加载完算，
  // 否则慢网络下片头会整个补播一遍，看起来像卡住
  const wait = Math.max(SPLASH_MIN_MS - performance.now(), 0);
  window.setTimeout(hideBootScreen, wait);
}

window.addEventListener("ts:app-ready", onAppReady, { once: true });
window.setTimeout(hideBootScreen, SPLASH_MAX_MS);

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <QueryClientProvider client={queryClient}>
      <App />
      <Toaster position="top-center" richColors closeButton />
    </QueryClientProvider>
  </React.StrictMode>
);