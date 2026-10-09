import { create } from "zustand";

type Theme = "light" | "dark";

const KEY = "tripscape-theme-plain";

/** 读初始主题：独立 key（裸字符串），避免与 zustand persist 的 JSON 冲突 */
function readInitialTheme(): Theme {
  if (typeof window === "undefined") return "light";
  const saved = localStorage.getItem(KEY);
  if (saved === "dark" || saved === "light") return saved;
  return window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light";
}

function applyTheme(t: Theme) {
  if (typeof document === "undefined") return;
  document.documentElement.classList.toggle("dark", t === "dark");
  // 同步 meta theme-color（PWA 状态栏）
  const meta = document.querySelector('meta[name="theme-color"]');
  if (meta) meta.setAttribute("content", t === "dark" ? "#0c1826" : "#9bb7d7");
}

interface ThemeState {
  theme: Theme;
  toggle: () => void;
}

export const useThemeStore = create<ThemeState>((set, get) => ({
  theme: readInitialTheme(),
  toggle: () => {
    const next: Theme = get().theme === "dark" ? "light" : "dark";
    localStorage.setItem(KEY, next);
    applyTheme(next);
    set({ theme: next });
  },
}));

// 初始化时立即应用一次
applyTheme(useThemeStore.getState().theme);
