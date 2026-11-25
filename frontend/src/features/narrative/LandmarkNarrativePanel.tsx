/**
 * 行旅识景 TripScape / 地标叙事档案
 * 创建日期: 2026-11-25
 *
 * 地标层的右侧档案面板：把一张叙事卡片读成「一段被文献支撑的讲述」，完成:
 *     1. 封面、编号、地点、置信度的定场
 *     2. 纪年轴的纵向排列（按年份排序，未记年单独归类）
 *     3. 文献摘录（章节 + 命中强度）与三个动作
 *
 * 依赖:
 *     依赖库: lucide-react
 *
 * 用法:
 *     <LandmarkNarrativePanel card={card} loading={...} onAdd={...} ... />
 *
 * 注意:
 *     1. 面板里的每一句内容都直接来自后端字段，本组件不写任何历史解释。
 *     2. 卡片取不到时给出可重试的错误态，而不是一句「暂不可用」把用户留在死路。
 */

import { AlertCircle, BookmarkPlus, Loader2, MapPin, Quote, RefreshCw, Users } from "lucide-react";
import { useMemo } from "react";

import { Button } from "@/components/ui/button";
import { cn } from "@/utils/cn";

import type { NarrativeCardData, PickedFragment } from "./types";

import StoryDocument from "./StoryDocument";

/** 年份未知的片段排在最后，避免未记年内容打断时间感 */
function sortByYear<T extends { year: number | null }>(items: T[]): T[] {
  return [...items].sort((a, b) => {
    if (a.year === null && b.year === null) return 0;
    if (a.year === null) return 1;
    if (b.year === null) return -1;
    return a.year - b.year;
  });
}

export default function LandmarkNarrativePanel({
  card,
  loading,
  failed,
  errorText,
  onRetry,
  landmarkName,
  storyMarkdown,
  onAdd,
  adding,
  onPick,
  picking,
  picked,
  onDeliver,
  delivering,
}: {
  card?: NarrativeCardData;
  loading: boolean;
  failed: boolean;
  errorText: string;
  onRetry: () => void;
  landmarkName: string;
  storyMarkdown: string;
  onAdd: () => void;
  adding: boolean;
  onPick: () => void;
  picking: boolean;
  picked: PickedFragment | null;
  onDeliver: (cardId: number) => void;
  delivering: boolean;
}) {
  const fragments = useMemo(() => sortByYear(card?.timeFragments || []), [card]);

  return (
    <section
      data-testid="narrative-layer-landmark"
      className="flex h-full flex-col overflow-hidden rounded-[20px] border border-border/70 bg-card/95 shadow-[0_24px_60px_-28px_rgb(0_0_0/0.65)] backdrop-blur-xl"
    >
      {/* 封面：照片 + 标题叠层 */}
      <header className="relative h-[142px] shrink-0 overflow-hidden">
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
        <div className="absolute inset-0 bg-gradient-to-t from-black/75 via-black/25 to-transparent" />
        <div className="absolute inset-x-0 bottom-0 p-3">
          <div className="mb-1 flex items-center gap-1.5 text-[10px] text-white/70">
            <span className="rounded-full bg-white/15 px-1.5 py-0.5 backdrop-blur">
              叙事档案 {card ? `#${card.id}` : ""}
            </span>
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
            className="line-clamp-2 text-base font-bold leading-snug text-white drop-shadow"
          >
            {card?.title || landmarkName || "正在读取这段叙事"}
          </h2>
        </div>
      </header>

      {/* 正文：加载 / 失败 / 内容 三态 */}
      <div className="min-h-0 flex-1 overflow-y-auto px-3.5 py-3">
        {loading && (
          <div className="space-y-2">
            <p className="flex items-center gap-1.5 text-[11px] text-muted-foreground">
              <Loader2 className="h-3.5 w-3.5 animate-spin" />
              正在翻阅文献，把这段讲述取出来…
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

        {!loading && !failed && card && (
          <div className="space-y-3.5">
            {/* 故事正文：一个地标一篇，来自 stories/*.md */}
            {storyMarkdown && (
              <section data-testid="narrative-story" className="rounded-xl bg-background/40 p-3">
                <StoryDocument markdown={storyMarkdown} />
              </section>
            )}

            {/* 材料区：故事背后的可核对字段 */}
            <div className="flex items-center gap-1.5 border-b border-border/50 pb-1">
              <span className="text-[10.5px] font-semibold tracking-wide text-muted-foreground">
                材料与出处
              </span>
              <span className="text-[10px] text-muted-foreground/70">
                {fragments.length} 条纪年 · {(card.ragSnippets || []).length} 段文献
              </span>
            </div>

            {/* 一句话说明这段叙事的构成（全部是可核对的事实计数） */}
            <p className="text-[11px] leading-relaxed text-muted-foreground">
              {card.source === "landmark"
                ? "这张卡片按地标资料现建，没有经过照片识别。"
                : `识别置信度 ${(card.confidence * 100).toFixed(0)}%${
                    card.confidence < 0.35 ? "（偏低，请人工核对）" : ""
                  }。`}
            </p>

            {/* 纪年轴 */}
            {fragments.length > 0 && (
              <div>
                <h3 className="mb-1.5 text-[11px] font-semibold tracking-wide text-foreground/80">
                  纪年轴
                </h3>
                <ol className="relative space-y-2 border-l border-border/70 pl-3">
                  {fragments.map((f, i) => (
                    <li key={`${f.targetId}-${i}`} className="relative">
                      <span className="absolute -left-[15px] top-1.5 h-1.5 w-1.5 rounded-full bg-primary" />
                      <div className="mb-0.5 flex items-center gap-1.5">
                        <span className="rounded bg-primary/10 px-1.5 py-0.5 text-[10px] font-semibold tabular-nums text-primary">
                          {f.year === null ? "未记年" : `${f.year} 年`}
                        </span>
                        {f.section && (
                          <span className="text-[10px] text-muted-foreground">{f.section}</span>
                        )}
                      </div>
                      <p className="text-[11.5px] leading-relaxed text-foreground/85">{f.text}</p>
                    </li>
                  ))}
                </ol>
              </div>
            )}

            {/* 文献摘录 */}
            {(card.ragSnippets || []).length > 0 && (
              <div>
                <h3 className="mb-1.5 flex items-center gap-1 text-[11px] font-semibold tracking-wide text-foreground/80">
                  <Quote className="h-3 w-3 text-primary" />
                  文献摘录
                </h3>
                <ul className="space-y-1.5">
                  {(card.ragSnippets || []).map((s, i) => (
                    <li
                      key={`${s.targetId}-${i}`}
                      className="rounded-xl border border-border/60 bg-background/60 p-2.5"
                    >
                      <div className="mb-1 flex items-center gap-1.5 text-[10px] text-muted-foreground">
                        <span className="rounded bg-accent px-1.5 py-0.5 font-medium">
                          {s.section || "检索"}
                        </span>
                        {s.score !== null && (
                          <span className="tabular-nums">命中 {s.score.toFixed(4)}</span>
                        )}
                      </div>
                      <p className="text-[11.5px] leading-relaxed text-foreground/80">{s.text}</p>
                    </li>
                  ))}
                </ul>
              </div>
            )}

            {/* 拾到的碎片：别人留在这里的一段讲述 */}
            {picked && (
              <div
                data-testid="narrative-picked-fragment"
                className="rounded-xl border border-dashed border-primary/40 bg-primary/5 p-2.5"
              >
                <div className="mb-1 flex items-center gap-1.5 text-[10px] text-muted-foreground">
                  <Users className="h-3 w-3 text-primary" />
                  有一条叙事漂流到这里
                  {picked.anonymous && <span className="rounded-full bg-primary/10 px-1.5 text-primary">匿名</span>}
                  <span className="ml-auto tabular-nums">
                    {new Date(picked.createdAt).toLocaleString("zh-CN")}
                  </span>
                </div>
                <div className="flex items-center gap-2">
                  {picked.sourceCard.photo && (
                    <img
                      src={picked.sourceCard.photo}
                      alt=""
                      className="h-11 w-11 shrink-0 rounded-lg object-cover"
                      onError={(e) => ((e.target as HTMLImageElement).style.visibility = "hidden")}
                    />
                  )}
                  <div className="min-w-0">
                    <div className="truncate text-xs font-medium text-foreground">
                      {picked.sourceCard.title}
                    </div>
                    <p className="line-clamp-2 text-[10.5px] leading-relaxed text-muted-foreground">
                      {picked.sourceCard.snippet}
                    </p>
                  </div>
                </div>
              </div>
            )}
          </div>
        )}
      </div>

      {/* 动作区：固定在底部，不随内容滚走 */}
      {card && (
        <footer className="shrink-0 border-t border-border/60 bg-card/80 px-3 py-2.5">
          <div className="flex flex-wrap items-center gap-1.5">
            <Button size="sm" data-testid="narrative-add-to-journal" onClick={onAdd} disabled={adding}>
              <BookmarkPlus className="mr-1 h-3.5 w-3.5" />
              {adding ? "收进中…" : "收进手记"}
            </Button>
            <Button
              size="sm"
              variant="outline"
              data-testid="narrative-pick"
              onClick={onPick}
              disabled={picking}
              className={cn(picking && "opacity-80")}
            >
              {picking ? "拾取中…" : "拾取碎片"}
            </Button>
            <Button
              size="sm"
              variant="ghost"
              data-testid="narrative-deliver"
              onClick={() => onDeliver(card.id)}
              disabled={delivering}
            >
              {delivering ? "投递中…" : "匿名留在此处"}
            </Button>
          </div>
        </footer>
      )}
    </section>
  );
}
