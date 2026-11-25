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

import type { LandmarkStoryData } from "./types";

export default function LandmarkStoryView({ story }: { story: LandmarkStoryData }) {
  return (
    <div data-testid="narrative-story" className="space-y-3.5">
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
                  {item.year === null
                    ? "未记年"
                    : item.year < 0
                      ? `公元前 ${-item.year} 年`
                      : `${item.year} 年`}
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
