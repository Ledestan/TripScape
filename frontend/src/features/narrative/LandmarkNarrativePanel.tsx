import type { NarrativeCardData, PickedFragment } from "./types";

import { Button } from "@/components/ui/button";

/**
 * 地标层（landmark）：正在被讲述的地点。
 *
 * 只读展示叙事卡片的"切面"——纪年、检索片段、置信度、坐标，
 * 并把三个动作交回父组件（加入手账 / 拾取碎片 / 投递碎片）。
 * 这里不写任何文化解释文案：卡片文字全部来自后端返回的字段。
 */
export default function LandmarkNarrativePanel({
  card,
  loading,
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
  onAdd: () => void;
  adding: boolean;
  onPick: () => void;
  picking: boolean;
  picked: PickedFragment | null;
  onDeliver: (cardId: number) => void;
  delivering: boolean;
}) {
  return (
    <div
      data-testid="narrative-layer-landmark"
      className="max-h-[34vh] overflow-y-auto px-3 py-2"
    >
      {loading && (
        <p className="py-6 text-center text-xs text-muted-foreground">
          正在取出这张照片的叙事切面…
        </p>
      )}

      {!loading && !card && (
        <p className="py-6 text-center text-xs text-muted-foreground">这张卡片暂不可用</p>
      )}

      {card && (
        <div className="flex gap-3">
          {card.photo && (
            <img
              src={card.photo}
              alt=""
              className="h-24 w-24 shrink-0 rounded-xl object-cover"
              onError={(e) => ((e.target as HTMLImageElement).style.display = "none")}
            />
          )}

          <div className="min-w-0 flex-1">
            <div className="flex flex-wrap items-center gap-1.5">
              <h3
                data-testid="narrative-card-title"
                className="truncate text-sm font-bold text-foreground"
              >
                {card.title}
              </h3>
              <span className="rounded-full bg-primary/10 px-1.5 py-0.5 text-[10px] font-medium text-primary">
                置信 {(card.confidence * 100).toFixed(0)}%
              </span>
              <span className="text-[10px] text-muted-foreground">
                {card.geo?.country || "—"} · {card.geo?.lat?.toFixed(2)}, {card.geo?.lon?.toFixed(2)}
              </span>
            </div>

            {/* 时间碎片（纪年切面） */}
            <div className="mt-1.5 space-y-1">
              {(card.timeFragments || []).slice(0, 2).map((f, i) => (
                <div key={`tf-${i}`} className="flex items-start gap-1.5 text-[11px] leading-snug">
                  <span className="mt-0.5 shrink-0 rounded bg-muted px-1 text-[10px] text-muted-foreground">
                    {f.year === null || f.year === undefined ? "未标年" : `${f.year} 年`}
                  </span>
                  <span className="line-clamp-2 text-foreground/85">{f.text}</span>
                </div>
              ))}
            </div>

            {/* RAG 检索片段（检索切面 + 章节切面） */}
            <div className="mt-1 space-y-1">
              {(card.ragSnippets || []).slice(0, 2).map((s, i) => (
                <div key={`rs-${i}`} className="flex items-start gap-1.5 text-[11px] leading-snug">
                  <span className="mt-0.5 shrink-0 rounded bg-accent px-1 text-[10px] text-muted-foreground">
                    {s.section || "检索"}
                  </span>
                  <span className="line-clamp-2 text-foreground/70">{s.text}</span>
                </div>
              ))}
            </div>

            <div className="mt-2 flex flex-wrap items-center gap-1.5">
              <Button
                size="sm"
                data-testid="narrative-add-to-journal"
                onClick={onAdd}
                disabled={adding}
              >
                {adding ? "保存中…" : "加入手账"}
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
                onClick={() => onDeliver(card.id)}
                disabled={delivering}
              >
                {delivering ? "投递中…" : "投递到此处"}
              </Button>
            </div>
          </div>
        </div>
      )}

      {picked && (
        <div
          data-testid="narrative-picked-fragment"
          className="mt-2 rounded-xl border border-dashed border-border p-2"
        >
          <div className="flex items-center gap-1.5 text-[11px] text-muted-foreground">
            <span className="rounded-full bg-primary/10 px-1.5 text-[10px] font-medium text-primary">
              拾到碎片 #{picked.id}
            </span>
            <span>{picked.anonymous ? "匿名投递" : ""}</span>
            <span>{new Date(picked.createdAt).toLocaleString("zh-CN")}</span>
          </div>
          <div className="mt-1 flex items-center gap-2">
            {picked.sourceCard.photo && (
              <img
                src={picked.sourceCard.photo}
                alt=""
                className="h-10 w-10 rounded-lg object-cover"
              />
            )}
            <div className="min-w-0">
              <div className="truncate text-xs font-medium">{picked.sourceCard.title}</div>
              <div className="line-clamp-2 text-[10px] text-muted-foreground">
                {picked.sourceCard.snippet}
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
