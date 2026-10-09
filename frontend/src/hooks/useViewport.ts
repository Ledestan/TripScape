import { useEffect, useState } from "react";

/**
 * 视口动态尺寸系统：
 * - 把边距/面板宽/字号/图标/圆角全部写成 CSS 变量（基于视口比例 + clamp），
 *   组件用 var(--ui-*) 引用，窗口缩放时整套 UI 等比伸缩。
 * - compact / narrow 两级折叠档位，控制行为级收起（搜索收成图标、控件精简等）。
 *
 * 档位：
 *   wide    (>=1100) 全展开：聊天默认展开、控件全量、搜索常显输入框
 *   compact (<1100)  收缩：搜索收成图标、控件精简、聊天收成条
 *   narrow  (<680)   最小：只留图标级浮层，保地球视野
 */
export function useViewport() {
  const [dim, setDim] = useState({ w: 1280, h: 800 });

  useEffect(() => {
    const apply = () => {
      const w = window.innerWidth;
      const h = window.innerHeight;
      setDim({ w, h });

      const root = document.documentElement;
      const clamp = (v: number, lo: number, hi: number) => Math.min(hi, Math.max(lo, v));

      // 边距：1.4vw，10~24px
      root.style.setProperty("--ui-pad", `${Math.round(clamp(w * 0.014, 10, 24))}px`);
      // 浮层间距：0.9vw，6~14px
      root.style.setProperty("--ui-gap", `${Math.round(clamp(w * 0.009, 6, 14))}px`);
      // 面板最大宽：30vw，260~430px
      root.style.setProperty("--ui-panel-max", `${Math.round(clamp(w * 0.3, 260, 430))}px`);
      // 常规字号：11~14px 随宽度线性
      root.style.setProperty("--ui-fs", `${clamp(11 + (w - 900) / 300, 11, 14).toFixed(1)}px`);
      root.style.setProperty("--ui-fs-sm", `${clamp(10 + (w - 900) / 400, 10, 12.5).toFixed(1)}px`);
      // 图标按钮直径：3vw，32~46px
      root.style.setProperty("--icon-btn", `${Math.round(clamp(w * 0.032, 36, 52))}px`);
      // 圆角：1.3vw，10~18px
      root.style.setProperty("--ui-radius", `${Math.round(clamp(w * 0.013, 10, 18))}px`);
      // 消息条宽度：26vw，180~340px
      root.style.setProperty("--ui-strip-w", `${Math.round(clamp(w * 0.26, 180, 340))}px`);
    };
    apply();
    window.addEventListener("resize", apply);
    return () => window.removeEventListener("resize", apply);
  }, []);

  return {
    w: dim.w,
    h: dim.h,
    wide: dim.w >= 1100,
    compact: dim.w < 1100,
    narrow: dim.w < 680,
  };
}
