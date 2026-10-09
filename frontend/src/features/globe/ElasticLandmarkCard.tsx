import { useEffect, useRef, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { MapPin, Eye, MessageSquare, NotebookPen, ChevronUp, ChevronDown, Compass, X } from "lucide-react";

import { api } from "@/api/client";
import type { Spot } from "@/features/globe/Globe";
import { globeBus } from "@/features/globe/Globe";
import { cn } from "@/utils/cn";

/**
 * 弹性资料卡片（点光点弹出，地球下方居中）：
 * - 默认：图 + 简介 + 操作按钮；上滑展开 / 下拉收成小条
 * - 拖动地球时自动收成小条（forceDocked）
 * - 标题/统计在图片下方实底区，不压图
 */
export default function ElasticLandmarkCard({
  spot,
  onClose,
  narrow,
  forceDocked,
  onOpenDetail,
}: {
  spot: Spot | null;
  onClose: () => void;
  narrow?: boolean;
  forceDocked?: boolean;
  onOpenDetail?: () => void;
}) {
  const [state, setState] = useState<"docked" | "normal" | "expanded">("normal");
  const dragStart = useRef<number | null>(null);
  const [dragDelta, setDragDelta] = useState(0);

  const { data: detail } = useQuery({
    queryKey: ["landmark", spot?.id],
    queryFn: async () => (await api.get(`/landmarks/${spot!.id}`)).data.data as Spot & { intro: string },
    enabled: !!spot,
  });

  useEffect(() => {
    if (forceDocked) setState("docked");
  }, [forceDocked]);

  useEffect(() => {
    setState("normal");
  }, [spot?.id]);

  if (!spot) return null;

  const onDragStart = (e: React.PointerEvent) => {
    dragStart.current = e.clientY;
    (e.target as HTMLElement).setPointerCapture(e.pointerId);
  };
  const onDragMove = (e: React.PointerEvent) => {
    if (dragStart.current === null) return;
    setDragDelta(e.clientY - dragStart.current);
  };
  const onDragEnd = () => {
    if (dragStart.current === null) return;
    if (dragDelta < -40) setState("expanded");
    else if (dragDelta > 40) setState("docked");
    dragStart.current = null;
    setDragDelta(0);
  };

  /* 收成小条 */
  if (state === "docked") {
    return (
      <div className="absolute left-1/2 z-40 -translate-x-1/2" style={{ bottom: "calc(var(--ui-pad) + 8px)" }}>
        <button
          onClick={() => setState("normal")}
          className="flex items-center gap-2 rounded-full border border-border/70 bg-card px-4 py-2 text-card-foreground shadow-2xl backdrop-blur transition hover:bg-accent"
          style={{ fontSize: "var(--ui-fs)" }}
        >
          <MapPin className="h-4 w-4 text-amber-500" />
          <span className="font-medium">{spot.name}</span>
          <ChevronUp className="h-3.5 w-3.5 text-muted-foreground" />
        </button>
      </div>
    );
  }

  const isExpanded = state === "expanded";

  return (
    <div
      className="absolute left-1/2 z-40 w-[min(88vw,420px)] -translate-x-1/2"
      style={{ bottom: "calc(var(--ui-pad) + 8px)" }}
    >
      <div
        className="overflow-hidden rounded-[var(--ui-radius)] border border-border/70 bg-card/95 text-card-foreground shadow-2xl backdrop-blur"
        onPointerDown={onDragStart}
        onPointerMove={onDragMove}
        onPointerUp={onDragEnd}
        style={{
          fontSize: "var(--ui-fs)",
          transform: dragDelta ? `translateY(${Math.max(-16, Math.min(16, dragDelta * 0.2))}px)` : undefined,
        }}
      >
        {/* 图片（无文字叠加） */}
        {detail?.image_url ? (
          <img
            src={detail.image_url}
            alt={spot.name}
            className={cn(
              "w-full cursor-grab rounded-t-[var(--ui-radius)] object-cover",
              isExpanded ? "h-[22vh]" : "h-[15vh]"
            )}
            onError={(e) => ((e.target as HTMLImageElement).style.display = "none")}
            draggable={false}
          />
        ) : (
          <div
            className={cn(
              "flex items-center justify-center bg-muted text-primary",
              isExpanded ? "h-[22vh]" : "h-[15vh]"
            )}
          >
            <MapPin className="h-9 w-9" />
          </div>
        )}

        {/* 标题/统计：图片下方实底区 */}
        <div className="flex items-start justify-between gap-2 px-3.5 pt-2.5">
          <div className="min-w-0 flex-1">
            <h3 className="truncate text-[15px] font-bold text-foreground">{spot.name}</h3>
            <div className="mt-0.5 flex flex-wrap items-center gap-2 text-[var(--ui-fs-sm)] text-muted-foreground">
              {spot.country && <span>{spot.country}</span>}
              {spot.region && (
                <span className="rounded-full bg-muted px-1.5 py-0.5 text-[10px]">{spot.region}</span>
              )}
            </div>
          </div>
          <div className="flex shrink-0 items-center gap-1">
            <button
              onClick={() => setState(isExpanded ? "normal" : "expanded")}
              className="rounded-full p-1.5 text-muted-foreground transition hover:bg-muted hover:text-foreground"
              title={isExpanded ? "收起" : "展开"}
            >
              {isExpanded ? <ChevronDown className="h-4 w-4" /> : <ChevronUp className="h-4 w-4" />}
            </button>
            <button
              onClick={() => setState("docked")}
              className="rounded-full p-1.5 text-muted-foreground transition hover:bg-muted hover:text-foreground"
              title="缩成小条"
            >
              <ChevronDown className="h-4 w-4 rotate-45" />
            </button>
            <button
              onClick={onClose}
              className="rounded-full p-1.5 text-muted-foreground transition hover:bg-muted hover:text-foreground"
              title="关闭"
            >
              <X className="h-4 w-4" />
            </button>
          </div>
        </div>

        {/* 统计条 */}
        <div className="mt-1.5 flex items-center gap-3 border-b border-border/50 px-3.5 pb-2 text-[var(--ui-fs-sm)] text-muted-foreground">
          <span className="flex items-center gap-1">
            <Eye className="h-3.5 w-3.5" /> {spot.view_count}
          </span>
          <span className="flex items-center gap-1">
            <MessageSquare className="h-3.5 w-3.5" /> {spot.comment_count ?? 0}
          </span>
          <span className="flex items-center gap-1">
            <NotebookPen className="h-3.5 w-3.5" /> {spot.journal_count ?? 0}
          </span>
          {spot.visitor_count !== undefined && <span className="ml-auto">到访 {spot.visitor_count} 人</span>}
        </div>

        {/* 简介 */}
        <div
          className={cn(
            "overflow-y-auto px-3.5 py-2.5 leading-relaxed text-foreground/90",
            isExpanded ? "max-h-[24vh]" : "max-h-[6vh]"
          )}
        >
          {detail?.intro || "暂无介绍"}
        </div>

        {/* 操作（预览浮窗不提供写手账，入口在详情页） */}
        <div className="flex flex-wrap items-center justify-end gap-2 border-t border-border/50 px-3.5 py-2.5">
          <button
            onClick={() => globeBus.flyTo(spot.lat, spot.lon, spot.id)}
            className="flex items-center gap-1.5 rounded-full bg-primary px-3 py-1.5 text-[var(--ui-fs-sm)] font-medium text-primary-foreground transition hover:bg-primary/90"
          >
            <Compass className="h-3.5 w-3.5" /> 飞过去
          </button>
          <button
            onClick={onOpenDetail}
            className="flex items-center gap-1.5 rounded-full border border-border/60 bg-muted px-3 py-1.5 text-[var(--ui-fs-sm)] transition hover:bg-accent"
          >
            详情与评论
          </button>
        </div>

        <div className="border-t border-border/30 py-1 text-center text-[10px] text-muted-foreground/70">
          上滑展开 · 下拉收起
        </div>
      </div>
    </div>
  );
}
