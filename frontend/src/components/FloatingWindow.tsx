import { useEffect } from "react";
import { X } from "lucide-react";
import { cn } from "@/utils/cn";

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
}: {
  open: boolean;
  onClose: () => void;
  title?: React.ReactNode;
  children: React.ReactNode;
  width?: number;
  maxHeight?: string;
  /** 固定高度（不随内容扩展），如 "480px" */
  fixedHeight?: string;
}) {
  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [open, onClose]);

  if (!open) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
      {/* 极轻遮罩：保留背景可见度，点击关闭 */}
      <div className="absolute inset-0 bg-black/25" onClick={onClose} />
      <div
        className={cn(
          "relative flex max-h-[85vh] w-full flex-col overflow-hidden rounded-2xl border border-border/60 bg-card text-card-foreground shadow-[0_8px_40px_-8px_rgb(0_0_0/0.28)] dark:shadow-[0_8px_44px_-6px_rgb(0_0_0/0.65),0_0_0_1px_rgb(255_255_255/0.04)]",
          "animate-in zoom-in-95 fade-in duration-200"
        )}
        style={{ maxWidth: width, ...(fixedHeight ? { height: fixedHeight, maxHeight: fixedHeight } : {}) }}
      >
        <div className="flex items-center justify-between border-b px-5 py-3.5">
          <div className="text-sm font-semibold">{title}</div>
          <button
            onClick={onClose}
            className="rounded-lg p-1.5 text-muted-foreground transition hover:bg-muted hover:text-foreground"
          >
            <X className="h-4 w-4" />
          </button>
        </div>
        <div className="flex-1 overflow-y-auto p-5" style={fixedHeight ? undefined : { maxHeight }}>
          {children}
        </div>
      </div>
    </div>
  );
}
