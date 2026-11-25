/**
 * 行旅识景 TripScape / 故事胶片
 * 创建日期: 2026-11-25
 *
 * 地球层的叙事入口：把 26 个地点排成一条可横向滑动的胶片，
 * 点击即进入该地标的叙事档案，完成:
 *     1. 提供不占满屏的入口（替代原来的整条底栏）
 *     2. 让「被讲述的地点」在地球层就可见
 *
 * 依赖:
 *     依赖库: lucide-react
 *
 * 用法:
 *     <StoryStrip spots={spots} onEnter={...} journalCount={n} onOpenJournal={...} />
 *
 * 注意:
 *     1. 只使用 /api/landmarks/spots 已有字段，不额外请求接口。
 *     2. 缩略图加载失败时隐藏图片，不改变条目高度，避免胶片抖动。
 */

import { BookOpen, Film } from "lucide-react";

import type { NarrativeSpot } from "./types";

export default function StoryStrip({
  spots,
  onEnter,
  journalCount,
  onOpenJournal,
}: {
  spots: NarrativeSpot[];
  onEnter: (spot: NarrativeSpot) => void;
  journalCount: number;
  onOpenJournal: () => void;
}) {
  return (
    <div className="w-full rounded-2xl border border-border/60 bg-card/80 p-2 shadow-[0_10px_30px_-18px_rgb(0_0_0/0.55)] backdrop-blur-md">
      <div className="mb-1.5 flex items-center gap-1.5 px-1">
        <Film className="h-3.5 w-3.5 text-primary" />
        <span className="text-[11px] font-semibold tracking-wide text-foreground">
          故事胶片
        </span>
        <span className="text-[10px] text-muted-foreground">
          {spots.length} 个被讲述的地点
        </span>
        <button
          onClick={onOpenJournal}
          className="ml-auto flex items-center gap-1 rounded-full border border-border/70 px-2 py-0.5 text-[10px] text-muted-foreground transition hover:border-primary/60 hover:text-foreground"
        >
          <BookOpen className="h-3 w-3" />
          手记 {journalCount}
        </button>
      </div>

      <div className="flex gap-1.5 overflow-x-auto pb-1 [scrollbar-width:none] [&::-webkit-scrollbar]:hidden">
        {spots.map((spot) => (
          <button
            key={spot.id}
            data-testid="narrative-landmark-entry"
            data-landmark-name={spot.name}
            onClick={() => onEnter(spot)}
            className="group flex w-[124px] shrink-0 flex-col overflow-hidden rounded-xl border border-transparent bg-background/70 text-left transition hover:border-primary/50 hover:bg-background"
          >
            <div className="relative h-[58px] w-full overflow-hidden bg-muted">
              {spot.image_url && (
                <img
                  src={spot.image_url}
                  alt=""
                  loading="lazy"
                  className="h-full w-full object-cover transition duration-500 group-hover:scale-[1.06]"
                  onError={(e) => ((e.target as HTMLImageElement).style.visibility = "hidden")}
                />
              )}
              <span className="absolute inset-x-0 bottom-0 h-6 bg-gradient-to-t from-black/55 to-transparent" />
            </div>
            <span className="px-1.5 py-1 leading-tight">
              <span className="block truncate text-[11px] font-medium text-foreground">
                {spot.name}
              </span>
              <span className="block truncate text-[10px] text-muted-foreground">
                {spot.country || spot.region || "—"}
              </span>
            </span>
          </button>
        ))}
      </div>
    </div>
  );
}
