/**
 * 行旅识景 TripScape / src/components/FloatingWindow
 *
 * 通用浮窗容器：居中卡片、Esc/遮罩关闭、可定制宽度与高度。
 */

import { useEffect, useRef } from "react";
import { X } from "lucide-react";
import { cn } from "@/utils/cn";

// 浮窗叠放顺序：Esc 只关最上面那层（之前每个浮窗都监听 keydown，
// 叠了"详情 + 手账查看"之类两层时按一次 Esc 会把两层一起关掉）
const windowStack: symbol[] = [];

/**
 * 小窗口容器（替代全屏 Dialog）：
 * 居中卡片式浮窗，右上角 X 关闭，不铺满全屏、不遮挡地球交互（点遮罩关闭但遮罩近乎透明）。
 */
export function FloatingWindow({
  open,
  onClose,
  title,
  children,
  width = 460,
  maxHeight = "70vh",
  fixedHeight,
  testId,
}: {
  open: boolean;
  onClose: () => void;
  title?: React.ReactNode;
  children: React.ReactNode;
  width?: number;
  maxHeight?: string;
  /** 固定高度（不随内容扩展），如 "480px" */
  fixedHeight?: string;
  /** 可选测试锚点 */
  testId?: string;
}) {
  const stackId = useRef<symbol>(Symbol("floating-window"));

  useEffect(() => {
    if (!open) return;
    const id = stackId.current;
    windowStack.push(id);
    const onKey = (e: KeyboardEvent) => {
      if (e.key !== "Escape") return;
      if (windowStack[windowStack.length - 1] !== id) return;
      e.stopPropagation();
      onClose();
    };
    document.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("keydown", onKey);
      const index = windowStack.indexOf(id);
      if (index >= 0) windowStack.splice(index, 1);
    };
  }, [open, onClose]);

  if (!open) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-2 sm:p-4">
      {/* 极轻遮罩：保留背景可见度，点击关闭 */}
      <div className="absolute inset-0 bg-black/25" onClick={onClose} />
      <div
        data-testid={testId}
        role="dialog"
        aria-modal="true"
        aria-label={typeof title === "string" ? title : "浮窗"}
        className={cn(
          "relative flex max-h-[85vh] w-full flex-col overflow-hidden rounded-panel border border-border/60 bg-card text-card-foreground shadow-panel",
          "animate-in zoom-in-95 fade-in duration-200"
        )}
        style={{ maxWidth: width, ...(fixedHeight ? { height: fixedHeight, maxHeight: fixedHeight } : {}) }}
      >
        <div className="flex items-center justify-between border-b px-4 py-2.5 sm:px-5 sm:py-3.5">
          <div className="text-sm font-semibold">{title}</div>
          <button
            onClick={onClose}
            data-testid="window-close"
            aria-label="关闭"
            className="rounded-lg p-1.5 text-muted-foreground transition hover:bg-muted hover:text-foreground"
          >
            <X className="h-4 w-4" />
          </button>
        </div>
        <div className="flex-1 overflow-y-auto p-3.5 sm:p-5" style={fixedHeight ? undefined : { maxHeight }}>
          {children}
        </div>
      </div>
    </div>
  );
}