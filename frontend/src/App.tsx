/**
 * 行旅识景 TripScape / src/App
 *
 * 路由入口：登录、地球主页、地标页、分享页与 404 的分发。
 */

import { lazy, Suspense, useEffect } from "react";
import { BrowserRouter, Route, Routes, useLocation, useSearchParams } from "react-router-dom";
import { useThemeStore } from "@/stores/theme";

// 地球 + 浮窗类页面（全部功能在浮窗内，无独立网页版）
const GlobeApp = lazy(() => import("@/pages/GlobeApp"));
const SearchWindow = lazy(() => import("@/features/search/SearchWindow"));

// 独立页（仅分享，供站外打开）
const SharePage = lazy(() => import("@/pages/Share"));

/**
 * 分包加载期间的占位：只铺一层深色底，不放任何文字与转圈。
 *
 * 首屏的片头由 index.html 里的 #boot-screen 负责（5 秒后淡出），
 * 这里如果放"加载中"组件，会在片头之上再叠一层旧界面，形成闪屏。
 */
function LazyFallback() {
  return <div className="fixed inset-0 bg-[#04070d]" aria-hidden="true" />;
}

function ScrollToTop() {
  const { pathname } = useLocation();
  useEffect(() => {
    window.scrollTo(0, 0);
  }, [pathname]);
  return null;
}

export default function App() {
  const theme = useThemeStore((s) => s.theme);
  useEffect(() => {
    document.documentElement.classList.toggle("dark", theme === "dark");
  }, [theme]);

  // 挂载即通知 main.tsx：可以开始给片头倒计时了（最短 2.6s，最长 8s 兜底）
  useEffect(() => {
    window.dispatchEvent(new Event("ts:app-ready"));
  }, []);

  return (
    <BrowserRouter>
      <ScrollToTop />
      <Suspense fallback={<LazyFallback />}>
        <Routes>
          {/* 公开分享页（独立布局，站外入口） */}
          <Route path="/share/:token" element={<SharePage />} />

          {/* 地球 + 浮窗（全部功能浮窗化） */}
          <Route path="/" element={<GlobeApp />} />
          <Route path="/login" element={<LoginRoute />} />
          <Route path="/landmarks/:id" element={<GlobeApp />} />
          <Route path="/journals/:id" element={<GlobeApp />} />
          <Route path="/search" element={<SearchRoute />} />

          {/* 旧网页版路由统一回地球 */}
          <Route path="/profile" element={<GlobeApp />} />
          <Route path="/qa-history" element={<GlobeApp />} />
          <Route path="/admin/*" element={<GlobeApp />} />
          <Route path="/dashboard" element={<GlobeApp />} />
        </Routes>
      </Suspense>
    </BrowserRouter>
  );
}

/** /login：地球 + 自动弹登录浮窗 */
function LoginRoute() {
  useEffect(() => {
    const t = setTimeout(() => window.dispatchEvent(new CustomEvent("ts:open-login")), 800);
    return () => clearTimeout(t);
  }, []);
  return <GlobeApp />;
}

/** /search：地球 + 搜索浮窗（?q= 预填） */
function SearchRoute() {
  const [params] = useSearchParams();

  return (
    <div className="relative h-screen w-full">
      <GlobeApp />
      <Suspense fallback={null}>
        <SearchWindow initialQuery={params.get("q") || ""} onClose={() => undefined} />
      </Suspense>
    </div>
  );
}