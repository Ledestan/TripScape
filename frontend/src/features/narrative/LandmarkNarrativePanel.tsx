/**
 * 行旅识景 TripScape / 地标叙事档案
 * 创建日期: 2026-11-25
 *
 * 地标层的右侧档案浮窗：把「整体介绍 → 时间轴 → 材料」讲成一段可读的叙事，完成:
 *     1. 封面上给出地标、国家、坐标与卡片编号
 *     2. 正文先读故事，再读背后的文献材料
 *     3. 底部提供收藏 / 拾取 / 匿名留下，以及评论、足迹与写手账的入口
 *
 * 依赖:
 *     依赖库: lucide-react
 *
 * 用法:
 *     <LandmarkNarrativePanel card={card} story={story} onBack={...} ... />
 *
 * 注意:
 *     1. 文案只来自接口字段，本组件不写任何历史解释。
 *     2. 浮窗自带关闭（✕）与收藏列表入口，不依赖页面顶部的返回。
 */

import {
  AlertCircle,
  Footprints,
  Loader2,
  MapPin,
  MessageSquare,
  NotebookPen,
  RefreshCw,
  Star,
  X,
} from "lucide-react";
import { useLayoutEffect, useRef } from "react";

import { Button } from "@/components/ui/button";
import LandmarkStoryView from "./LandmarkStoryView";
import type { LandmarkStoryData, NarrativeCardData } from "./types";

export default function LandmarkNarrativePanel({
  card,
  loading,
  failed,
  errorText,
  onRetry,
  landmarkName,
  story,
  onBack,
  onOpenComments,
  onOpenJournalEditor,
  favorited,
  favoriteBusy,
  onToggleFavorite,
  onOpenFootprints,
}: {
  card?: NarrativeCardData;
  loading: boolean;
  failed: boolean;
  errorText: string;
  onRetry: () => void;
  landmarkName: string;
  story?: LandmarkStoryData;
  onBack: () => void;
  onOpenComments: () => void;
  onOpenJournalEditor: () => void;
  favorited: boolean;
  favoriteBusy: boolean;
  onToggleFavorite: () => void;
  onOpenFootprints: () => void;
}) {
  const title = card?.title || story?.title || landmarkName || "地标档案";

  const panelRef = useRef<HTMLElement | null>(null);

  // 共享元素：档案从被点的那个光点"长出来"，而不是凭空出现在右边。
  // 拿光点的屏幕坐标算位移，再缩放到原尺寸；找不到光点（比如深链进入）就只做淡入。
  useLayoutEffect(() => {
    const el = panelRef.current;
    if (!el) return;
    const id = card?.landmarkId;
    const marker = id ? document.querySelector<HTMLElement>(`[data-ts-spot="${id}"]`) : null;

    if (!marker) {
      el.animate(
        [
          { opacity: 0, transform: "translateX(14px) scale(.98)" },
          { opacity: 1, transform: "none" },
        ],
        { duration: 260, easing: "cubic-bezier(.22,.68,.28,1)" }
      );
      return;
    }

    const from = marker.getBoundingClientRect();
    const to = el.getBoundingClientRect();
    const dx = from.left + from.width / 2 - (to.left + to.width / 2);
    const dy = from.top + from.height / 2 - (to.top + to.height / 2);

    // 只动 transform 与 opacity：两者走合成层，不会被大圆角/阴影的逐帧重绘拖慢
    el.animate(
      [
        { transform: `translate(${dx}px, ${dy}px) scale(.22)`, opacity: 0.15 },
        { transform: "none", opacity: 1 },
      ],
      { duration: 420, easing: "cubic-bezier(.22,.68,.28,1)" }
    );
  }, [card?.landmarkId]);

  return (
    <section
      ref={panelRef}
      className="flex max-h-[min(660px,calc(100vh-150px))] flex-col overflow-hidden rounded-panel border border-border/70 bg-card shadow-panel"
    >
      {/* 封面 */}
      <header className="relative h-[124px] shrink-0 overflow-hidden">
        {card?.photo ? (
          <img
            src={card.photo}
            alt=""
            className="h-full w-full object-cover"
            decoding="async"
            onError={(e) => ((e.target as HTMLImageElement).style.visibility = "hidden")}
          />
        ) : (
          <div className="h-full w-full bg-gradient-to-br from-primary/25 via-muted to-background" />
        )}
        <div className="absolute inset-0 bg-gradient-to-t from-black/80 via-black/30 to-transparent" />

        {/* 浮窗自带关闭：不依赖页面顶部返回 */}
        <div className="absolute right-1.5 top-1.5 flex items-center gap-1">
          <button
            data-testid="narrative-back"
            onClick={onBack}
            aria-label="关闭叙事档案"
            className="rounded-full bg-black/35 p-1 text-white/90 backdrop-blur transition hover:bg-black/50"
          >
            <X className="h-3.5 w-3.5" />
          </button>
        </div>

        <div className="absolute inset-x-0 bottom-0 p-3">
          <div className="mb-1 flex items-center gap-1.5 text-[10px] text-white/70">
            {card?.id ? <span>档案 #{card.id}</span> : null}
            {card?.geo?.country && (
              <span className="flex items-center gap-1">
                <MapPin className="h-3 w-3" />
                {card.geo.country}
              </span>
            )}
            {card?.geo?.lat !== undefined && (
              <span className="tabular-nums">
                {card.geo.lat.toFixed(2)}, {card.geo.lon.toFixed(2)}
              </span>
            )}
          </div>
          <h2
            data-testid="narrative-card-title"
            className="line-clamp-2 text-[15px] font-bold leading-snug text-white drop-shadow"
          >
            {title}
          </h2>
        </div>
      </header>

      {/* 正文 */}
      <div className="min-h-0 flex-1 overflow-y-auto px-3.5 py-3">
        {loading && (
          <div className="space-y-2">
            <p className="flex items-center gap-1.5 text-[11px] text-muted-foreground">
              <Loader2 className="h-3.5 w-3.5 animate-spin" />
              正在读这一段…
            </p>
            {[0, 1, 2].map((i) => (
              <div key={i} className="animate-pulse space-y-1.5 rounded-xl border border-border/50 p-2.5">
                <div className="h-2.5 w-16 rounded bg-muted" />
                <div className="h-2.5 w-full rounded bg-muted" />
                <div className="h-2.5 w-4/5 rounded bg-muted" />
              </div>
            ))}
          </div>
        )}

        {!loading && failed && (
          <div className="rounded-xl border border-destructive/40 bg-destructive/5 p-3">
            <p className="flex items-center gap-1.5 text-xs font-medium text-destructive">
              <AlertCircle className="h-3.5 w-3.5" />
              这段叙事没有取出来
            </p>
            <p className="mt-1 break-all text-[11px] leading-relaxed text-muted-foreground">
              {errorText || "接口没有返回卡片数据"}
            </p>
            <Button size="sm" variant="outline" className="mt-2" onClick={onRetry}>
              <RefreshCw className="mr-1 h-3.5 w-3.5" />
              重新取出
            </Button>
          </div>
        )}

        {!loading && !failed && (
          <div className="space-y-3.5">
            {story ? (
              <LandmarkStoryView story={story} />
            ) : (
              <p className="text-[11px] text-muted-foreground">这个地标还没有预置故事内容。</p>
            )}
          </div>
        )}
      </div>

      {/* 动作区：评论 / 收藏 / 足迹 / 手账，四个各自独立的按钮 */}
      <footer className="shrink-0 border-t border-border/60 bg-card px-3 py-2.5">
        <div className="grid grid-cols-4 gap-1.5">
          <Button
            size="sm"
            variant="outline"
            className="h-8 px-0 text-[11px]"
            data-testid="narrative-open-comments"
            onClick={onOpenComments}
          >
            <MessageSquare className="mr-1 h-3 w-3" />
            评论
          </Button>
          <Button
            size="sm"
            variant="outline"
            className={`h-8 px-0 text-[11px] ${
              favorited
                ? "border-amber-400/70 text-amber-500 hover:text-amber-500"
                : "text-muted-foreground hover:text-foreground"
            }`}
            data-testid="narrative-favorite"
            onClick={onToggleFavorite}
            disabled={favoriteBusy}
          >
            <Star className={`mr-1 h-3 w-3 ${favorited ? "fill-amber-400 text-amber-400" : ""}`} />
            {favorited ? "已收藏" : "收藏"}
          </Button>
          <Button
            size="sm"
            variant="outline"
            className="h-8 px-0 text-[11px] text-muted-foreground hover:text-foreground"
            data-testid="narrative-footprints"
            onClick={onOpenFootprints}
          >
            <Footprints className="mr-1 h-3 w-3" />
            足迹
          </Button>
          <Button
            size="sm"
            variant="outline"
            className="h-8 px-0 text-[11px] text-muted-foreground hover:text-foreground"
            data-testid="narrative-open-journal-edit"
            onClick={onOpenJournalEditor}
          >
            <NotebookPen className="mr-1 h-3 w-3" />
            手账
          </Button>
        </div>
      </footer>
    </section>
  );
}
