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

/** 首屏加载动画固定展示 5 秒（即使页面已加载完成，也完整走完启动动画） */
const SPLASH_MS = 5000;
const splashKey = "ts-splash-start";

function splashUntil(): number {
  const start = Number(sessionStorage.getItem(splashKey) || 0);
  const now = Date.now();
  if (!start || now - start > SPLASH_MS + 3000) {
    sessionStorage.setItem(splashKey, String(now));
    return now + SPLASH_MS;
  }
  return start + SPLASH_MS;
}

const hideAt = splashUntil();

function hideBootScreen() {
  // boot 节点位于 #root 之外（index.html 中 #boot-screen），React 不管理它
  const boot = document.getElementById("boot-screen");
  if (boot) {
    boot.style.transition = "opacity .4s ease";
    boot.style.opacity = "0";
    setTimeout(() => boot.remove(), 400);
  }
}

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <QueryClientProvider client={queryClient}>
      <App />
      <Toaster position="top-center" richColors closeButton />
    </QueryClientProvider>
  </React.StrictMode>
);

// 无论挂载快慢，都在启动时间线满 5 秒后淡出加载动画
const remaining = hideAt - Date.now();
setTimeout(hideBootScreen, Math.max(remaining, 0));
