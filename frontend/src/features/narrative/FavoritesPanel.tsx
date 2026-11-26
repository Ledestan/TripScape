/**
 * 行旅识景 TripScape / 我的收藏
 * 创建日期: 2026-11-26
 *
 * 手记层的内容：只展示"我收藏过的地标"，完成:
 *     1. 按收藏时间倒序列出，每条给封面、名称、国家、收藏日期
 *     2. 点名称飞回该地标；点星标取消收藏
 *     3. 空列表给一句能继续走的引导，而不是一块空白
 *
 * 依赖:
 *     依赖库: lucide-react
 *
 * 用法:
 *     <FavoritesPanel items={favorites} onOpen={...} onRemove={...} onClose={...} />
 *
 * 注意:
 *     1. 数据来自 GET /api/auth/profile 的 favorites 字段（已按收藏时间倒序）。
 *     2. 这里不做任何内容解释，只有地标本身的信息。
 */

import { BookMarked, MapPin, Star, X } from "lucide-react";

export interface FavoriteItem {
  id: number;
  name: string;
  country?: string;
  photo?: string;
  favorited_at?: string;
}

export default function FavoritesPanel({
  items,
  onOpen,
  onRemove,
  removing,
  onClose,
}: {
  items: FavoriteItem[];
  onOpen: (landmarkId: number, name: string) => void;
  onRemove: (landmarkId: number) => void;
  removing: boolean;
  onClose: () => void;
}) {
  return (
    <section
      data-testid="narrative-layer-journal"
      className="flex max-h-[min(660px,calc(100vh-150px))] flex-col overflow-hidden rounded-panel border border-border/70 bg-card shadow-panel"
    >
      <header className="shrink-0 border-b border-border/60 px-3.5 py-2.5">
        <div className="flex items-start gap-2">
          <h2 className="flex flex-1 items-center gap-1.5 text-sm font-bold text-foreground">
            <BookMarked className="h-4 w-4 text-primary" />
            我的收藏
            <span className="rounded-full bg-primary/10 px-1.5 text-[10px] font-semibold text-primary">
              {items.length} 处
            </span>
          </h2>
          <button
            data-testid="narrative-back"
            onClick={onClose}
            aria-label="关闭收藏"
            className="rounded-full p-1 text-muted-foreground transition hover:bg-muted hover:text-foreground"
          >
            <X className="h-3.5 w-3.5" />
          </button>
        </div>
        <p className="mt-1 leading-relaxed text-[10.5px] text-muted-foreground">
          收藏只记地点，不替它解释。点名字回到那颗光点。
        </p>
      </header>

      <div className="min-h-0 flex-1 overflow-y-auto p-2.5">
        {items.length === 0 ? (
          <div className="px-2 py-10 text-center">
            <Star className="mx-auto mb-2 h-5 w-5 text-muted-foreground/60" />
            <p className="text-[12px] font-medium text-foreground/80">还没有收藏。</p>
            <p className="mt-1 text-[11px] leading-relaxed text-muted-foreground">
              在地标档案里点一下「收藏」，它就会留在这里，下次直接从手记进来。
            </p>
          </div>
        ) : (
          <ul className="space-y-2">
            {items.map((item) => (
              <li
                key={item.id}
                data-testid="narrative-journal-card"
                className="flex items-center gap-2 rounded-card border border-border/60 bg-background/70 p-2"
              >
                {item.photo && (
                  <img
                    src={item.photo}
                    alt=""
                    loading="lazy"
                    decoding="async"
                    className="h-12 w-12 shrink-0 rounded-lg object-cover"
                    onError={(e) => ((e.target as HTMLImageElement).style.visibility = "hidden")}
                  />
                )}
                <div className="min-w-0 flex-1">
                  <button
                    onClick={() => onOpen(item.id, item.name)}
                    className="block w-full truncate text-left text-[12.5px] font-semibold text-foreground transition hover:text-primary"
                  >
                    {item.name}
                  </button>
                  <div className="mt-0.5 flex items-center gap-1.5 text-[10px] text-muted-foreground">
                    {item.country && (
                      <span className="flex items-center gap-0.5">
                        <MapPin className="h-2.5 w-2.5" />
                        {item.country}
                      </span>
                    )}
                    {item.favorited_at && (
                      <span className="tabular-nums">
                        {new Date(item.favorited_at).toLocaleDateString("zh-CN")}
                      </span>
                    )}
                  </div>
                </div>
                <button
                  onClick={() => onRemove(item.id)}
                  disabled={removing}
                  aria-label={`取消收藏 ${item.name}`}
                  className="rounded-full p-1.5 text-amber-500 transition hover:bg-amber-500/10 disabled:opacity-50"
                >
                  <Star className="h-3.5 w-3.5 fill-amber-400" />
                </button>
              </li>
            ))}
          </ul>
        )}
      </div>
    </section>
  );
}
