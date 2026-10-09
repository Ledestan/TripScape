import { useEffect, useRef, useState } from "react";
import { Compass, Maximize2, Minimize2, Navigation, RotateCcw, ChevronUp, X, Minus, Plus } from "lucide-react";
import { globeBus } from "@/features/globe/Globe";

/**
 * 右下角地球控件（一行布局）：
 * [重置] | [方向角▲（上方弹可拖条浮窗，条右=回正）] | [−|+ 分裂式缩放] | [全屏]
 * - 方向角真实旋转相机（globeBus.setBearing -> setAzimuthalAngle）
 * - 重置 = 方向角归零 + 缩放距离恢复默认，不改变看向地点
 * - 尺寸间距走 var(--ui-*)，随窗口动态；narrow 折叠成精简按钮
 */
export default function GlobeControls({
  compact,
  narrow,
}: {
  compact?: boolean;
  narrow?: boolean;
}) {
  const [expanded, setExpanded] = useState<boolean | null>(null);
  const [isFull, setIsFull] = useState(false);
  const [bearingOpen, setBearingOpen] = useState(false);
  const [bearing, setBearing] = useState(80);
  const barRef = useRef<HTMLDivElement>(null);
  const dragging = useRef(false);

  useEffect(() => {
    setExpanded(null);
  }, [compact, narrow]);
  const isExpanded = expanded ?? !narrow;

  useEffect(() => {
    const onFs = () => setIsFull(!!document.fullscreenElement);
    document.addEventListener("fullscreenchange", onFs);
    return () => document.removeEventListener("fullscreenchange", onFs);
  }, []);

  const zoomBy = (delta: number) => {
    const el = document.querySelector("canvas");
    if (!el) return;
    const rect = el.getBoundingClientRect();
    for (let i = 0; i < Math.abs(delta); i++) {
      el.dispatchEvent(
        new WheelEvent("wheel", {
          clientX: rect.left + rect.width / 2,
          clientY: rect.top + rect.height / 2,
          deltaY: delta > 0 ? -160 : 160,
          bubbles: true,
        })
      );
    }
  };

  const toggleFullscreen = async () => {
    try {
      if (document.fullscreenElement) await document.exitFullscreen();
      else await document.documentElement.requestFullscreen();
    } catch {
      /* ignore */
    }
  };

  // 方向条拖拽（0-359，实时旋转相机）
  const updateFromPointer = (clientX: number) => {
    const bar = barRef.current;
    if (!bar) return;
    const rect = bar.getBoundingClientRect();
    const pct = Math.min(1, Math.max(0, (clientX - rect.left) / rect.width));
    const deg = Math.round(pct * 179);
    setBearing(deg);
    globeBus.setBearing(deg);
  };
  const onBarDown = (e: React.PointerEvent) => {
    dragging.current = true;
    (e.target as HTMLElement).setPointerCapture(e.pointerId);
    updateFromPointer(e.clientX);
  };
  const onBarMove = (e: React.PointerEvent) => {
    if (dragging.current) updateFromPointer(e.clientX);
  };
  const onBarUp = () => {
    dragging.current = false;
  };

  const btn =
    "flex items-center justify-center rounded-full border border-border/60 bg-card text-card-foreground shadow-[0_2px_12px_-2px_rgb(0_0_0/0.25)] dark:shadow-[0_2px_14px_-2px_rgb(0_0_0/0.6)] transition hover:bg-accent hover:text-accent-foreground active:scale-95";

  // 窄屏：精简成一个按钮
  if (narrow && !isExpanded) {
    return (
      <button
        onClick={() => setExpanded(true)}
        className={btn}
        style={{ width: "var(--icon-btn)", height: "var(--icon-btn)" }}
        title="地球控件"
      >
        <Compass className="h-[45%] w-[45%]" />
      </button>
    );
  }

  return (
    <div className="relative flex flex-col items-end gap-[var(--ui-gap)]">
      {/* 方向角浮窗（按钮上方弹出） */}
      {bearingOpen && (
        <div
          className="absolute bottom-full right-0 mb-[var(--ui-gap)] w-[min(34vw,300px)] rounded-[var(--ui-radius)] border border-border/60 bg-card p-3 shadow-[0_8px_36px_-6px_rgb(0_0_0/0.3)] dark:shadow-[0_8px_40px_-4px_rgb(0_0_0/0.7)]"
          style={{ fontSize: "var(--ui-fs-sm)" }}
        >
          <div className="mb-2 flex items-center justify-between">
            <span className="font-medium">纬度视角 {bearing}°</span>
            <div className="flex items-center gap-1">
              <button
                onClick={() => {
                  setBearing(80);
                  globeBus.setBearing(80);
                }}
                className="flex items-center gap-1 rounded-full border border-border/70 bg-background px-2.5 py-1 transition hover:bg-accent"
                title="回正方向"
              >
                <Navigation className="h-3 w-3" /> 回正
              </button>
              <button
                onClick={() => setBearingOpen(false)}
                className="rounded-full p-1 text-muted-foreground hover:bg-muted hover:text-foreground"
              >
                <X className="h-3.5 w-3.5" />
              </button>
            </div>
          </div>
          {/* 可拖方向条 */}
          <div
            ref={barRef}
            onPointerDown={onBarDown}
            onPointerMove={onBarMove}
            onPointerUp={onBarUp}
            className="relative h-6 cursor-pointer select-none rounded-full border border-border/70 bg-background"
          >
            {[0, 90, 180].map((d) => (
              <div
                key={d}
                className="absolute top-0 h-full border-l border-border/50"
                style={{ left: `${(d / 180) * 100}%` }}
              />
            ))}
            <div
              className="absolute top-1/2 h-4 w-4 -translate-x-1/2 -translate-y-1/2 rounded-full border-2 border-foreground bg-card shadow"
              style={{ left: `${(bearing / 180) * 100}%` }}
            />
            <span className="absolute left-1.5 top-1/2 -translate-y-1/2 text-[9px] text-foreground/80">北</span>
            <span className="absolute right-1.5 top-1/2 -translate-y-1/2 text-[9px] text-foreground/80">南</span>
          </div>
        </div>
      )}

      {/* 一行控件 */}
      <div
        className="flex items-center gap-[calc(var(--ui-gap)*0.6)] rounded-full border border-border/60 bg-card p-[calc(var(--ui-gap)*0.55)] shadow-[0_4px_24px_-4px_rgb(0_0_0/0.28)] dark:shadow-[0_4px_28px_-4px_rgb(0_0_0/0.65)]"
        style={{ fontSize: "var(--ui-fs-sm)" }}
      >
        {/* 重置：方向角+缩放，不改地点 */}
        <button
          onClick={() => {
            setBearing(80);
            globeBus.resetView();
          }}
          className={btn}
          style={{ width: "calc(var(--icon-btn)*1.0)", height: "calc(var(--icon-btn)*1.0)" }}
          title="重置（方向角与缩放）"
        >
          <RotateCcw className="h-[42%] w-[42%]" />
        </button>

        <div className="h-[calc(var(--icon-btn)*0.7)] w-px bg-border/60" />

        {/* 方向角 */}
        <button
          onClick={() => setBearingOpen((v) => !v)}
          className={`${btn} relative`}
          style={{ width: "calc(var(--icon-btn)*1.0)", height: "calc(var(--icon-btn)*1.0)" }}
          title="方向角"
        >
          <Compass className="h-[44%] w-[44%]" style={{ transform: `rotate(${bearing}deg)` }} />
          <ChevronUp className="absolute -top-0.5 right-0 h-2.5 w-2.5 text-muted-foreground" />
        </button>

        <div className="h-[calc(var(--icon-btn)*0.7)] w-px bg-border/60" />

        {/* 分裂式缩放：一个圆角按钮中间平分，左− 右+ */}
        <div
          className="flex overflow-hidden rounded-full border border-border/60 bg-card shadow-[0_2px_12px_-2px_rgb(0_0_0/0.25)] dark:shadow-[0_2px_14px_-2px_rgb(0_0_0/0.6)]"
          style={{
            height: "calc(var(--icon-btn)*1.0)",
            width: "calc(var(--icon-btn)*1.75)",
          }}
          title="缩放"
        >
          <button
            onClick={() => zoomBy(-2)}
            className="flex flex-1 items-center justify-center transition hover:bg-accent hover:text-accent-foreground active:scale-95"
            title="缩小"
          >
            <Minus className="h-[38%] w-[38%]" />
          </button>
          <div className="my-1 w-px bg-border/60" />
          <button
            onClick={() => zoomBy(2)}
            className="flex flex-1 items-center justify-center transition hover:bg-accent hover:text-accent-foreground active:scale-95"
            title="放大"
          >
            <Plus className="h-[38%] w-[38%]" />
          </button>
        </div>

        <div className="h-[calc(var(--icon-btn)*0.7)] w-px bg-border/60" />

        {/* 全屏 */}
        <button
          onClick={toggleFullscreen}
          className={btn}
          style={{ width: "calc(var(--icon-btn)*1.0)", height: "calc(var(--icon-btn)*1.0)" }}
          title={isFull ? "退出全屏" : "全屏"}
        >
          {isFull ? <Minimize2 className="h-[42%] w-[42%]" /> : <Maximize2 className="h-[42%] w-[42%]" />}
        </button>
      </div>

      {narrow && (
        <button
          onClick={() => setExpanded(false)}
          className="text-[10px] text-muted-foreground hover:text-foreground"
        >
          收起
        </button>
      )}
    </div>
  );
}
