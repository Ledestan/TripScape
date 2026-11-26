/**
 * 行旅识景 TripScape / 地标故事视图
 * 创建日期: 2026-11-25
 *
 * 把预置在数据库里的故事渲染成「整体介绍 → 时间轴 → 分节材料」，完成:
 *     1. 先读整体介绍，让读者知道这是什么地方
 *     2. 再读时间轴（按年份升序，年份缺失单独标注）
 *     3. 最后读现场与到访信息，顺序与内容结构一一对应
 *
 * 依赖:
 *     依赖库: lucide-react
 *
 * 用法:
 *     <LandmarkStoryView story={story} />
 *
 * 注意:
 *     1. 数据形状来自 GET /api/narrative/story/{id}，字段缺失时安全降级。
 *     2. 不拼接任何本地文案成"史实"，只做排版与顺序组织。
 */

import { Clock3 } from "lucide-react";
import { useEffect, useRef } from "react";
import type { LandmarkStoryData } from "./types";

export default function LandmarkStoryView({ story }: { story: LandmarkStoryData }) {
  const rootRef = useRef<HTMLDivElement | null>(null);

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

      {/* 分节材料：站在这里 / 尺度与参数 / 到访之前 / 补记 */}
      {story.sections?.map((section) => (
        <section key={section.heading}>
          <h4 className="mb-1 text-[11px] font-semibold tracking-wide text-foreground/80">
            {section.heading}
          </h4>
          <ul className="space-y-1">
            {section.items.map((item, index) => (
              <li key={index} className="flex gap-1.5 text-[11.5px] leading-relaxed text-foreground/80">
                <span className="mt-[7px] h-1 w-1 shrink-0 rounded-full bg-primary/60" />
                <span className="min-w-0 flex-1">{item}</span>
              </li>
            ))}
          </ul>
        </section>
      ))}
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