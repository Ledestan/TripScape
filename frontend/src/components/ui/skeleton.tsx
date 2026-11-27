/**
 * 行旅识景 TripScape / src/components/ui/skeleton
 *
 * 统一的加载占位，替代各处手写的"加载中…"文字，完成:
 *     1. Skeleton：一块带呼吸动画的占位条（宽度可调）
 *     2. SkeletonRows：若干行占位的组合，用于列表/段落加载
 *
 * 为什么不用文字：
 *     文字会带来"内容已到、只是没加载"的错觉，还会在不同浮窗里出现字号/颜色不一致；
 *     骨架屏保持版面结构，浮窗打开时不会跳一下。
 */

import { cn } from "@/utils/cn";

/** 单块占位条 */
export function Skeleton({ className }: { className?: string }) {
  return <div className={cn("animate-pulse rounded-control bg-muted/60", className)} />;
}

/**
 * 多行占位
 *
 * 参数：
 *     rows : number，行数（默认 3）
 *     className : string，外层间距/内边距
 */
export function SkeletonRows({ rows = 3, className }: { rows?: number; className?: string }) {
  return (
    <div className={cn("space-y-2.5 p-4", className)} aria-busy="true" aria-live="polite">
      {Array.from({ length: rows }).map((_, index) => (
        <Skeleton
          key={index}
          className={cn("h-3.5", index === rows - 1 ? "w-2/5" : index % 2 ? "w-4/5" : "w-full")}
        />
      ))}
    </div>
  );
}

/** 卡片列表占位：一张标题 + 两行正文，用于手记/评论等列表 */
export function SkeletonCards({ count = 2, className }: { count?: number; className?: string }) {
  return (
    <div className={cn("space-y-2.5 p-4", className)} aria-busy="true" aria-live="polite">
      {Array.from({ length: count }).map((_, index) => (
        <div key={index} className="rounded-card border border-border/60 p-3">
          <Skeleton className="mb-2 h-3.5 w-1/3" />
          <Skeleton className="mb-1.5 h-3 w-full" />
          <Skeleton className="h-3 w-3/5" />
        </div>
      ))}
    </div>
  );
}