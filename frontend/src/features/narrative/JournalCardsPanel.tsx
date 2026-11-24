import type { JournalEntry } from "./types";

import { Button } from "@/components/ui/button";

/**
 * 手账层（journal）：已被沉淀的个人叙事。
 *
 * 卡片是**只读快照**：这里没有编辑入口，也没有改写接口——
 * 沉淀过的叙事不能被本人事后改写，只能被匿名投递出去。
 */
export default function JournalCardsPanel({
  entries,
  onDeliver,
  delivering,
  onWake,
}: {
  entries: JournalEntry[];
  onDeliver: (cardId: number, landmarkId: number) => void;
  delivering: boolean;
  onWake: (landmarkId: number, landmarkName: string) => void;
}) {
  return (
    <div
      data-testid="narrative-layer-journal"
      className="max-h-[34vh] overflow-y-auto px-3 py-2"
    >
      {entries.length === 0 ? (
        <p className="py-6 text-center text-xs text-muted-foreground">
          手账还是空的：回到地标层，把一张叙事卡片加入手账
        </p>
      ) : (
        <ul className="space-y-1.5">
          {entries.map((entry) => (
            <li
              key={entry.card.id}
              data-testid="narrative-journal-card"
              className="flex items-center gap-2 rounded-xl border border-border/60 bg-background px-2 py-1.5"
            >
              {entry.card.photo && (
                <img
                  src={entry.card.photo}
                  alt=""
                  className="h-9 w-9 shrink-0 rounded-lg object-cover"
                  onError={(e) => ((e.target as HTMLImageElement).style.display = "none")}
                />
              )}
              <div className="min-w-0 flex-1">
                <button
                  className="block w-full truncate text-left text-xs font-medium hover:text-primary"
                  onClick={() =>
                    onWake(entry.card.landmarkId, entry.card.geo?.place || entry.card.title)
                  }
                >
                  {entry.card.title}
                </button>
                <div className="text-[10px] text-muted-foreground">
                  {new Date(entry.addedAt).toLocaleString("zh-CN")} · 只读快照 ·{" "}
                  {(entry.card.timeFragments || []).length} 条纪年记录
                </div>
              </div>
              <Button
                size="sm"
                variant="outline"
                data-testid="narrative-deliver"
                disabled={delivering}
                onClick={() => onDeliver(entry.card.id, entry.card.landmarkId)}
              >
                {delivering ? "投递中…" : "匿名投递"}
              </Button>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
