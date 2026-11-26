/**
 * 行旅识景 TripScape / 地标故事视图
 * 创建日期: 2026-11-25
 *
 * 把预置在数据库里的故事渲染成「整体介绍 → 时间轴 → 分节材料」，完成:
 *     1. 先读整体介绍，让读者知道这是什么地方
 *     2. 再读时间轴（按年份升序，年份缺失单独标注）
 *     3. 分节默认折叠两行，可单节展开，也可"查看全文"进文章详情页
 *
 * 依赖:
 *     依赖库: lucide-react
 *
 * 用法:
 *     <LandmarkStoryView story={story} onOpenArticle={() => ...} />
 *     <LandmarkStoryView story={story} expanded />   // 文章详情页
 *
 * 注意:
 *     1. 数据形状来自 GET /api/narrative/story/{id}，字段缺失时安全降级。
 *     2. 不拼接任何本地文案成"史实"，只做排版与顺序组织。
 */

import { ChevronDown, ChevronUp, Clock3, FileText } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import type { LandmarkStoryData } from "./types";

const PREVIEW_ITEMS = 2;

export default function LandmarkStoryView({
  story,
  onOpenArticle,
  expanded = false,
}: {
  story: LandmarkStoryData;
  /** 点"查看全文"时打开文章详情页 */
  onOpenArticle?: () => void;
  /** 文章详情页里全部展开，不再折叠 */
  expanded?: boolean;
}) {
  const rootRef = useRef<HTMLDivElement | null>(null);
  const [openSections, setOpenSections] = useState<Record<string, boolean>>({});

  // 阅读浮现：每块内容进入视口时上浮 10px 淡入，长页面读起来像在翻文献。
  // 只做一次（observe 后立即 unobserve），滚动回来不会反复闪。
  useEffect(() => {
    const root = rootRef.current;
    if (!root) return;
    if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) return;

    const blocks = Array.from(root.children) as HTMLElement[];
    blocks.forEach((el) => el.classList.add("ts-reveal"));

    const observer = new IntersectionObserver(
      (entries) => {
        entries.forEach((entry) => {
          if (!entry.isIntersecting) return;
          entry.target.classList.add("is-in");
          observer.unobserve(entry.target);
        });
      },
      { rootMargin: "0px 0px -12% 0px", threshold: 0.12 }
    );
    blocks.forEach((el) => observer.observe(el));
    return () => observer.disconnect();
  }, [story]);

  return (
    <div ref={rootRef} data-testid="narrative-story" className="space-y-3.5">
      {/* 整体介绍 */}
      {story.intro && (
        <p className="text-[12.5px] leading-[1.8] text-foreground/85">{story.intro}</p>
      )}

      {/* 时间轴 */}
      {story.timeline?.length > 0 && (
        <section>
          <h4 className="mb-1.5 flex items-center gap-1 text-[11px] font-semibold tracking-wide text-primary">
            <Clock3 className="h-3 w-3" />
            时间轴
          </h4>
          <ol className="relative space-y-2 border-l border-border/70 pl-3">
            {story.timeline.map((item, index) => (
              <li key={`${item.year}-${index}`} className="relative">
                <span className="absolute -left-[15px] top-1.5 h-1.5 w-1.5 rounded-full bg-primary" />
                <div className="mb-0.5 text-[10.5px] font-semibold tabular-nums text-primary">
                  {formatYear(item.year)}
                </div>
                <p className="text-[11.5px] leading-relaxed text-foreground/80">{item.text}</p>
              </li>
            ))}
          </ol>
        </section>
      )}

      {/* 分节材料：默认折叠，可单节展开 */}
      {story.sections?.map((section) => {
        const isOpen = expanded || openSections[section.heading];
        const items = isOpen ? section.items : section.items.slice(0, PREVIEW_ITEMS);
        const hiddenCount = section.items.length - items.length;

        return (
          <section key={section.heading}>
            <h4 className="mb-1 text-[11px] font-semibold tracking-wide text-foreground/80">
              {section.heading}
            </h4>
            <ul className="space-y-1">
              {items.map((item, index) => (
                <li
                  key={index}
                  className="flex gap-1.5 text-[11.5px] leading-relaxed text-foreground/80"
                >
                  <span className="mt-[7px] h-1 w-1 shrink-0 rounded-full bg-primary/60" />
                  <span className="min-w-0 flex-1">{item}</span>
                </li>
              ))}
            </ul>

            {!expanded && hiddenCount > 0 && (
              <button
                type="button"
                className="mt-1 flex items-center gap-0.5 text-[10.5px] text-primary hover:underline"
                onClick={() =>
                  setOpenSections((sections) => ({
                    ...sections,
                    [section.heading]: !isOpen,
                  }))
                }
              >
                {isOpen ? (
                  <>
                    <ChevronUp className="h-3 w-3" />
                    收起
                  </>
                ) : (
                  <>
                    <ChevronDown className="h-3 w-3" />
                    展开本节（还有 {hiddenCount} 条）
                  </>
                )}
              </button>
            )}

            {!expanded && isOpen && hiddenCount <= 0 && (
              <button
                type="button"
                className="mt-1 flex items-center gap-0.5 text-[10.5px] text-muted-foreground hover:text-primary"
                onClick={() =>
                  setOpenSections((sections) => ({
                    ...sections,
                    [section.heading]: !isOpen,
                  }))
                }
              >
                <ChevronUp className="h-3 w-3" />
                收起
              </button>
            )}
          </section>
        );
      })}

      {/* 查看全文 → 文章详情页 */}
      {onOpenArticle && !expanded && (
        <button
          type="button"
          data-testid="narrative-open-article"
          onClick={onOpenArticle}
          className="flex w-full items-center justify-center gap-1 rounded-card border border-border/70 px-2 py-1.5 text-[11px] text-foreground/80 transition hover:border-primary/50 hover:text-primary"
        >
          <FileText className="h-3 w-3" />
          查看全文
        </button>
      )}
    </div>
  );
}

/**
 * 年份显示：公元前用负数，1-999 年补"公元"，否则直接写年份。
 *
 * 为什么要补"公元"：罗马竞技场建于 72 年，只写"72 年"读起来像"72 年"这个时长。
 */
function formatYear(year: number | null): string {
  if (year === null) return "未记年";
  if (year < 0) return `公元前 ${-year} 年`;
  if (year < 1000) return `公元 ${year} 年`;
  return `${year} 年`;
}
