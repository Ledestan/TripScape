/**
 * 行旅识景 TripScape / src/components/ui/date-picker
 * 创建日期: 2026-11-26
 *
 * 轻量日历选择器，完成:
 *     1. 按钮显示"2026年11月26日"，不显示 yyyy/mm/dd 那种输入框格式
 *     2. 点击弹出月历，可切月、选日、回今天、清除
 *     3. 输出固定 "YYYY-MM-DD" 字符串，和后端 visited_at 对齐
 *
 * 依赖:
 *     依赖库: lucide-react
 *
 * 用法:
 *     <DatePicker value={visitedAt} onChange={setVisitedAt} />
 *
 * 注意:
 *     1. 不引入日期库：月历只用到 Date，跨月/闰年由 Date 自己处理。
 *     2. 周一起始，和国内日历习惯一致。
 */

import { useEffect, useMemo, useRef, useState } from "react";
import { CalendarDays, ChevronLeft, ChevronRight } from "lucide-react";

import { cn } from "@/utils/cn";

const WEEKDAYS = ["一", "二", "三", "四", "五", "六", "日"];

function pad(value: number): string {
  return String(value).padStart(2, "0");
}

/** Date → "YYYY-MM-DD" */
export function toDateString(date: Date): string {
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}`;
}

/** "YYYY-MM-DD" → Date（非法值返回 null） */
export function parseDateString(value?: string | null): Date | null {
  if (!value) return null;
  const match = /^(\d{4})-(\d{2})-(\d{2})$/.exec(value);
  if (!match) return null;
  const date = new Date(Number(match[1]), Number(match[2]) - 1, Number(match[3]));
  return Number.isNaN(date.getTime()) ? null : date;
}

/** 展示用：2026年11月26日 */
function formatLabel(date: Date): string {
  return `${date.getFullYear()}年${date.getMonth() + 1}月${date.getDate()}日`;
}

export function DatePicker({
  value,
  onChange,
  placeholder = "选择日期",
  testId,
}: {
  value: string;
  onChange: (value: string) => void;
  placeholder?: string;
  testId?: string;
}) {
  const [open, setOpen] = useState(false);
  const selected = useMemo(() => parseDateString(value), [value]);
  const [view, setView] = useState(() => {
    const base = selected || new Date();
    return new Date(base.getFullYear(), base.getMonth(), 1);
  });
  const rootRef = useRef<HTMLDivElement | null>(null);

  // 打开时把视图定位到已选月份
  useEffect(() => {
    if (!open) return;
    const base = selected || new Date();
    setView(new Date(base.getFullYear(), base.getMonth(), 1));
  }, [open, selected]);

  // 点外面 / Esc 关闭
  useEffect(() => {
    if (!open) return;
    const onDown = (event: MouseEvent) => {
      if (!rootRef.current?.contains(event.target as Node)) setOpen(false);
    };
    const onKey = (event: KeyboardEvent) => {
      if (event.key === "Escape") setOpen(false);
    };
    document.addEventListener("mousedown", onDown);
    document.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("mousedown", onDown);
      document.removeEventListener("keydown", onKey);
    };
  }, [open]);

  const days = useMemo(() => {
    const first = new Date(view.getFullYear(), view.getMonth(), 1);
    const offset = (first.getDay() + 6) % 7; // 周一 = 0
    const total = new Date(view.getFullYear(), view.getMonth() + 1, 0).getDate();
    return { offset, total };
  }, [view]);

  const today = toDateString(new Date());
  const current = selected ? toDateString(selected) : "";

  return (
    <div ref={rootRef} className="relative">
      <button
        type="button"
        data-testid={testId}
        onClick={() => setOpen((value) => !value)}
        className={cn(
          "flex h-8 w-full items-center gap-1.5 rounded-control border border-border/70 bg-background px-2 text-left text-[12px]",
          "hover:border-primary/50 focus:outline-none focus-visible:ring-2 focus-visible:ring-ring",
          selected ? "text-foreground" : "text-muted-foreground"
        )}
        aria-haspopup="dialog"
        aria-expanded={open}
      >
        <CalendarDays className="h-3.5 w-3.5 shrink-0 text-muted-foreground" />
        <span className="truncate">{selected ? formatLabel(selected) : placeholder}</span>
      </button>

      {open && (
        <div
          role="dialog"
          aria-label="选择日期"
          className="absolute left-0 top-9 z-50 w-[248px] rounded-card border border-border/70 bg-card p-2 shadow-panel"
        >
          <div className="mb-1.5 flex items-center justify-between">
            <button
              type="button"
              className="rounded p-1 text-muted-foreground hover:bg-muted"
              onClick={() => setView(new Date(view.getFullYear(), view.getMonth() - 1, 1))}
              aria-label="上个月"
            >
              <ChevronLeft className="h-3.5 w-3.5" />
            </button>
            <span className="text-[12px] tabular-nums text-foreground">
              {view.getFullYear()} 年 {view.getMonth() + 1} 月
            </span>
            <button
              type="button"
              className="rounded p-1 text-muted-foreground hover:bg-muted"
              onClick={() => setView(new Date(view.getFullYear(), view.getMonth() + 1, 1))}
              aria-label="下个月"
            >
              <ChevronRight className="h-3.5 w-3.5" />
            </button>
          </div>

          <div className="grid grid-cols-7 gap-0.5 text-center text-[10px] text-muted-foreground">
            {WEEKDAYS.map((day) => (
              <span key={day} className="py-0.5">
                {day}
              </span>
            ))}
          </div>

          <div className="mt-0.5 grid grid-cols-7 gap-0.5">
            {Array.from({ length: days.offset }).map((_, index) => (
              <span key={`blank-${index}`} />
            ))}
            {Array.from({ length: days.total }).map((_, index) => {
              const date = new Date(view.getFullYear(), view.getMonth(), index + 1);
              const key = toDateString(date);
              const isSelected = key === current;
              const isToday = key === today;
              return (
                <button
                  key={key}
                  type="button"
                  onClick={() => {
                    onChange(key);
                    setOpen(false);
                  }}
                  className={cn(
                    "h-7 rounded text-[11px] tabular-nums transition-colors",
                    isSelected
                      ? "bg-primary text-primary-foreground"
                      : "text-foreground hover:bg-muted",
                    !isSelected && isToday && "ring-1 ring-inset ring-primary/40"
                  )}
                  aria-label={`${date.getFullYear()}年${date.getMonth() + 1}月${date.getDate()}日`}
                >
                  {index + 1}
                </button>
              );
            })}
          </div>

          <div className="mt-1.5 flex items-center justify-between border-t border-border/60 pt-1.5">
            <button
              type="button"
              className="rounded px-2 py-0.5 text-[11px] text-muted-foreground hover:bg-muted"
              onClick={() => {
                onChange(today);
                setOpen(false);
              }}
            >
              今天
            </button>
            <button
              type="button"
              className="rounded px-2 py-0.5 text-[11px] text-muted-foreground hover:bg-muted"
              onClick={() => {
                onChange("");
                setOpen(false);
              }}
            >
              清除
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
