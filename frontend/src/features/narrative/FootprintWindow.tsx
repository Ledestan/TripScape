/**
 * 行旅识景 TripScape / 我的足迹
 * 创建日期: 2026-11-26
 *
 * 浮窗：列出"我的足迹"，完成:
 *     1. 按最近到访倒序列出地标、到访次数、首次到访日期
 *     2. 点一行飞回该地标；无足迹时说明足迹是怎么产生的
 *
 * 依赖:
 *     依赖库: lucide-react, @tanstack/react-query
 *
 * 用法:
 *     <FootprintWindow open={open} onClose={() => setOpen(false)} onLocate={...} />
 *
 * 注意:
 *     1. 足迹由手账自动汇总（每写一篇手账记一次），本组件不手动写入。
 *     2. 未登录时不请求接口，直接显示引导。
 */

import { useQuery } from "@tanstack/react-query";
import { Footprints, MapPin, X } from "lucide-react";

import { api } from "@/api/client";
import { FloatingWindow } from "@/components/FloatingWindow";
import { SkeletonRows } from "@/components/ui/skeleton";
import { useAuthStore } from "@/stores/auth";

interface FootprintItem {
  landmark_id: number;
  name: string;
  visits: number;
  hidden?: boolean;
  first_visited_at?: string;
  last_visited_at?: string;
}

export default function FootprintWindow({
  open,
  onClose,
  onLocate,
}: {
  open: boolean;
  onClose: () => void;
  onLocate: (landmarkId: number, name: string) => void;
}) {
  const token = useAuthStore((s) => s.token);

  const { data = [], isLoading } = useQuery({
    queryKey: ["footprints", "mine"],
    queryFn: async () => (await api.get("/footprints/mine")).data.data as FootprintItem[],
    enabled: open && !!token,
    retry: 0,
  });

  return (
    <FloatingWindow open={open} onClose={onClose} title="我的足迹" width={440} maxHeight="70vh">
      {!token ? (
        <div className="px-5 py-10 text-center text-[12px] text-muted-foreground">
          登录后，这里会记录你去过的地标。
        </div>
      ) : isLoading ? (
        <SkeletonRows rows={4} />
      ) : data.length === 0 ? (
        <div className="px-6 py-10 text-center">
          <Footprints className="mx-auto mb-2 h-5 w-5 text-muted-foreground/60" />
          <p className="text-[12px] font-medium text-foreground/80">还没有足迹。</p>
          <p className="mt-1 text-[11px] leading-relaxed text-muted-foreground">
            每写一篇手账，地标就会被记下一次到访——足迹是按你的手账自动汇总的。
          </p>
        </div>
      ) : (
        <ul className="divide-y divide-border/60">
          {data.map((fp) => (
            <li key={fp.landmark_id}>
              <button
                onClick={() => onLocate(fp.landmark_id, fp.name)}
                className="flex w-full items-center gap-3 px-4 py-3 text-left transition hover:bg-muted/40"
              >
                <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-primary/10 text-[11px] font-bold tabular-nums text-primary">
                  {fp.visits}
                </span>
                <span className="min-w-0 flex-1">
                  <span className="block truncate text-[12.5px] font-semibold text-foreground">
                    {fp.name}
                  </span>
                  <span className="mt-0.5 flex items-center gap-1 text-[10px] text-muted-foreground">
                    <MapPin className="h-2.5 w-2.5" />
                    {fp.first_visited_at
                      ? `首次 ${new Date(fp.first_visited_at).toLocaleDateString("zh-CN")}`
                      : "到访记录"}
                    {fp.hidden && <span>· 已隐藏</span>}
                  </span>
                </span>
                <X className="h-3 w-3 rotate-45 text-transparent" aria-hidden="true" />
              </button>
            </li>
          ))}
        </ul>
      )}
    </FloatingWindow>
  );
}
