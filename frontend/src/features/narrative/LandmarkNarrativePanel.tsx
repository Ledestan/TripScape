/**
 * 行旅识景 TripScape / 地标叙事档案
 * 创建日期: 2026-11-25
 *
 * 地标层的右侧档案浮窗：把「整体介绍 → 时间轴 → 材料」讲成一段可读的叙事，完成:
 *     1. 封面上给出地标、国家、坐标与卡片编号
 *     2. 正文先读故事，再读背后的文献材料
 *     3. 底部提供收进手记 / 拾取 / 匿名留下，以及评论收藏与写手账的入口
 *
 * 依赖:
 *     依赖库: lucide-react
 *
 * 用法:
 *     <LandmarkNarrativePanel card={card} story={story} onBack={...} ... />
 *
 * 注意:
 *     1. 文案只来自接口字段，本组件不写任何历史解释。
 *     2. 浮窗自带关闭（✕）与手记入口，不依赖页面顶部的返回。
 */

import {
  AlertCircle,
  BookmarkPlus,
  BookOpen,
  Loader2,
  MapPin,
  MessageSquare,
  NotebookPen,
  RefreshCw,
  X,
} from "lucide-react";

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
  journalCount,
  onBack,
  onOpenJournal,
  onAdd,
  adding,
  onPick,
  picking,
  onDeliver,
  delivering,
  onOpenComments,
  onOpenJournalEditor,
}: {
  card?: NarrativeCardData;
  loading: boolean;
  failed: boolean;
  errorText: string;
  onRetry: () => void;
  landmarkName: string;
  story?: LandmarkStoryData;
  journalCount: number;
  onBack: () => void;
  onOpenJournal: () => void;
  onAdd: () => void;
  adding: boolean;
  onPick: () => void;
  picking: boolean;
  onDeliver: (cardId: number) => void;
  delivering: boolean;
  onOpenComments: () => void;
  onOpenJournalEditor: () => void;
}) {
  const title = card?.title || story?.title || landmarkName || "地标档案";

  return (
    <section className="flex max-h-[min(660px,calc(100vh-150px))] flex-col overflow-hidden rounded-[18px] border border-border/70 bg-card/95 shadow-[0_24px_60px_-28px_rgb(0_0_0/0.65)] backdrop-blur-xl">
      {/* 封面 */}
      <header className="relative h-[124px] shrink-0 overflow-hidden">
        {card?.photo ? (
          <img
            src={card.photo}
            alt=""
            className="h-full w-full object-cover"
            onError={(e) => ((e.target as HTMLImageElement).style.visibility = "hidden")}
          />
        ) : (
          <div className="h-full w-full bg-gradient-to-br from-primary/25 via-muted to-background" />
        )}
        <div className="absolute inset-0 bg-gradient-to-t from-black/80 via-black/30 to-transparent" />

        {/* 浮窗自带的关闭与手记入口 */}
        <div className="absolute right-1.5 top-1.5 flex items-center gap-1">
          <button
            data-testid="narrative-open-journal"
            onClick={onOpenJournal}
            className="flex items-center gap-1 rounded-full bg-black/35 px-2 py-1 text-[10.5px] text-white/90 backdrop-blur transition hover:bg-black/50"
          >
            <BookOpen className="h-3 w-3" />
            手记
            <span
              data-testid="narrative-journal-count"
              className="rounded-full bg-white/20 px-1 text-[10px] font-bold"
            >
              {journalCount}
            </span>
          </button>
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

      {/* 动作区 */}
      <footer className="shrink-0 border-t border-border/60 bg-card/80 px-3 py-2.5">
        <div className="flex flex-wrap items-center gap-1.5">
          <Button
            size="sm"
            data-testid="narrative-add-to-journal"
            onClick={onAdd}
            disabled={adding || !card}
          >
            <BookmarkPlus className="mr-1 h-3.5 w-3.5" />
            {adding ? "收进中…" : "收进手记"}
          </Button>
          <Button
            size="sm"
            variant="outline"
            data-testid="narrative-pick"
            onClick={onPick}
            disabled={picking}
          >
            {picking ? "拾取中…" : "拾取碎片"}
          </Button>
          <Button
            size="sm"
            variant="ghost"
            data-testid="narrative-deliver"
            onClick={() => card && onDeliver(card.id)}
            disabled={delivering || !card}
          >
            {delivering ? "投递中…" : "匿名留在此处"}
          </Button>
        </div>
        <div className="mt-1.5 flex items-center gap-1 border-t border-border/40 pt-1.5">
          <Button
            size="sm"
            variant="ghost"
            className="h-7 text-[11px] text-muted-foreground hover:text-foreground"
            data-testid="narrative-open-comments"
            onClick={onOpenComments}
          >
            <MessageSquare className="mr-1 h-3 w-3" />
            评论与收藏
          </Button>
          <Button
            size="sm"
            variant="ghost"
            className="h-7 text-[11px] text-muted-foreground hover:text-foreground"
            data-testid="narrative-open-journal-edit"
            onClick={onOpenJournalEditor}
          >
            <NotebookPen className="mr-1 h-3 w-3" />
            写手账
          </Button>
        </div>
      </footer>
    </section>
  );
}
