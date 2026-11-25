/**
 * 行旅识景 TripScape / 旅行手记抽屉
 * 创建日期: 2026-11-25
 *
 * 手账层的右侧抽屉：把收下的叙事排成一本可翻阅的手记，完成:
 *     1. 按收录时间倒序列出，只读呈现（沉淀过的叙事不允许事后改写）
 *     2. 提供「回到那段叙事」与「匿名留在此处」两个动作
 *     3. 空手记时给出一句能继续走的引导，而不是一块空白
 *
 * 依赖:
 *     依赖库: lucide-react
 *
 * 用法:
 *     <JournalCardsPanel entries={entries} onDeliver={...} onWake={...} />
 *
 * 注意:
 *     1. entries 来自服务端 /api/narrative/journal，刷新后由服务端取回。
 *     2. 这里的「投递」与地标层的「匿名留在此处」是同一个接口，只是入口不同。
 */

import { BookOpen, Compass, MapPin, Send } from "lucide-react";
import { useMemo } from "react";

import { Button } from "@/components/ui/button";

import type { JournalEntry } from "./types";

export default function JournalCardsPanel({
  entries,
  onDeliver,
  delivering,
  onWake,
  onPickHere,
  canPick,
}: {
  entries: JournalEntry[];
  onDeliver: (cardId: number, landmarkId: number) => void;
  delivering: boolean;
  onWake: (landmarkId: number, landmarkName: string) => void;
  onPickHere: () => void;
  canPick: boolean;
}) {
  const sorted = useMemo(
    () => [...entries].sort((a, b) => (a.addedAt < b.addedAt ? 1 : -1)),
    [entries]
  );

  return (
    <section
      data-testid="narrative-layer-journal"
      className="flex h-full flex-col overflow-hidden rounded-[20px] border border-border/70 bg-card/95 shadow-[0_24px_60px_-28px_rgb(0_0_0/0.65)] backdrop-blur-xl"
    >
      <header className="shrink-0 border-b border-border/60 px-3.5 py-2.5">
        <h2 className="flex items-center gap-1.5 text-sm font-bold text-foreground">
          <BookOpen className="h-4 w-4 text-primary" />
          旅行手记
          <span className="rounded-full bg-primary/10 px-1.5 text-[10px] font-semibold text-primary">
            {entries.length} 段
          </span>
        </h2>
        <p className="mt-0.5 text-[10.5px] leading-relaxed text-muted-foreground">
          收下的叙事是只读快照：可以匿名留给后来的人，但不能再改写。
        </p>
      </header>

      <div className="min-h-0 flex-1 overflow-y-auto px-3 py-2.5">
        {sorted.length === 0 ? (
          <div className="mt-6 rounded-xl border border-dashed border-border/70 px-3 py-6 text-center">
            <Compass className="mx-auto mb-1.5 h-5 w-5 text-muted-foreground/70" />
            <p className="text-[11.5px] leading-relaxed text-muted-foreground">
              手记还是空的。
              <br />
              回到地球，点一个地标，把它的那段叙事收下来。
            </p>
          </div>
        ) : (
          <ul className="space-y-2">
            {sorted.map((entry) => (
              <li
                key={entry.card.id}
                data-testid="narrative-journal-card"
                className="overflow-hidden rounded-xl border border-border/60 bg-background/70"
              >
                <div className="flex gap-2 p-2">
                  {entry.card.photo && (
                    <img
                      src={entry.card.photo}
                      alt=""
                      loading="lazy"
                      className="h-14 w-14 shrink-0 rounded-lg object-cover"
                      onError={(e) => ((e.target as HTMLImageElement).style.visibility = "hidden")}
                    />
                  )}
                  <div className="min-w-0 flex-1">
                    <button
                      onClick={() =>
                        onWake(entry.card.landmarkId, entry.card.geo?.place || entry.card.title)
                      }
                      className="block w-full truncate text-left text-[12.5px] font-semibold text-foreground transition hover:text-primary"
                    >
                      {entry.card.title}
                    </button>
                    <div className="mt-0.5 flex flex-wrap items-center gap-x-1.5 text-[10px] text-muted-foreground">
                      <span className="flex items-center gap-0.5">
                        <MapPin className="h-2.5 w-2.5" />
                        {entry.card.geo?.country || "—"}
                      </span>
                      <span className="tabular-nums">
                        {new Date(entry.addedAt).toLocaleDateString("zh-CN")}
                      </span>
                      <span>{(entry.card.timeFragments || []).length} 条纪年</span>
                    </div>
                    <p className="mt-1 line-clamp-2 text-[10.5px] leading-relaxed text-muted-foreground">
                      {entry.card.ragSnippets?.[0]?.text || entry.card.timeFragments?.[0]?.text || ""}
                    </p>
                  </div>
                </div>
                <div className="flex items-center justify-end gap-1 border-t border-border/50 px-2 py-1.5">
                  <Button
                    size="sm"
                    variant="ghost"
                    className="h-7 text-[11px]"
                    onClick={() =>
                      onWake(entry.card.landmarkId, entry.card.geo?.place || entry.card.title)
                    }
                  >
                    回到那段叙事
                  </Button>
                  <Button
                    size="sm"
                    variant="outline"
                    className="h-7 text-[11px]"
                    data-testid="narrative-deliver"
                    disabled={delivering}
                    onClick={() => onDeliver(entry.card.id, entry.card.landmarkId)}
                  >
                    <Send className="mr-1 h-3 w-3" />
                    {delivering ? "投递中…" : "匿名留在此处"}
                  </Button>
                </div>
              </li>
            ))}
          </ul>
        )}
      </div>

      {canPick && (
        <footer className="shrink-0 border-t border-border/60 px-3 py-2">
          <Button
            size="sm"
            variant="ghost"
            className="w-full text-[11px] text-muted-foreground hover:text-foreground"
            onClick={onPickHere}
          >
            在当前地标拾取一条漂流而来的叙事
          </Button>
        </footer>
      )}
    </section>
  );
}
