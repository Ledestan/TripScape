import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { MapPin, User as UserIcon, Search as SearchIcon } from "lucide-react";

import { api } from "@/api/client";
import { FloatingWindow } from "@/components/FloatingWindow";
import { globeBus } from "@/features/globe/Globe";
import UserProfileWindow from "@/features/profile/UserProfileWindow";

interface SearchItem {
  kind: string;
  id: number;
  title: string;
  subtitle: string;
  image_url: string;
}

/**
 * 全局搜索浮窗（在地球上打开，固定尺寸）：
 * - Tab：地标 / 用户（只搜这两类）
 * - 地标：飞行 + 详情
 * - 用户：打开用户主页浮窗
 */
export default function SearchWindow({ initialQuery = "", onClose }: { initialQuery?: string; onClose: () => void }) {
  const [tab, setTab] = useState<"landmark" | "journal" | "user">("landmark");
  const [q, setQ] = useState(initialQuery);
  const [submitted, setSubmitted] = useState(initialQuery);
  const [userOpen, setUserOpen] = useState<number | null>(null);

  const { data, isFetching } = useQuery({
    queryKey: ["global-search", submitted, tab],
    queryFn: async () =>
      (
        await api.get("/search/", { params: { q: submitted, kind: tab, page_size: 30 } })
      ).data.data as SearchItem[],
    enabled: submitted.length > 0,
  });

  const doSearch = () => setSubmitted(q.trim());

  return (
    <>
      <FloatingWindow open onClose={onClose} title="全局搜索" width={480} fixedHeight="min(66vh, 580px)">
        {/* 搜索框 */}
        <div className="flex items-center gap-2 rounded-xl border border-border/70 bg-background px-3 py-2 focus-within:border-primary">
          <SearchIcon className="h-4 w-4 shrink-0 text-muted-foreground" />
          <input
            autoFocus
            value={q}
            onChange={(e) => setQ(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && doSearch()}
            placeholder="输入关键词，回车搜索"
            className="min-w-0 flex-1 bg-transparent text-sm outline-none placeholder:text-muted-foreground"
          />
          <button
            onClick={doSearch}
            className="shrink-0 rounded-lg bg-primary px-3 py-1 text-xs font-medium text-primary-foreground"
          >
            搜索
          </button>
        </div>

        {/* Tab：地标 / 手账 / 用户 */}
        <div className="mt-3 grid grid-cols-3 gap-1 rounded-xl bg-muted p-1">
          {(["landmark", "journal", "user"] as const).map((t) => (
            <button
              key={t}
              onClick={() => setTab(t)}
              className={`rounded-lg py-1.5 text-sm font-medium transition ${
                tab === t ? "bg-background shadow" : "text-muted-foreground hover:text-foreground"
              }`}
            >
              {t === "landmark" ? "地标" : t === "journal" ? "手账" : "用户"}
            </button>
          ))}
        </div>

        {/* 结果 */}
        <div className="mt-3 max-h-[40vh] space-y-1 overflow-y-auto pr-0.5">
          {isFetching && <p className="py-8 text-center text-sm text-muted-foreground">搜索中…</p>}
          {!isFetching && submitted && !data?.length && (
            <p className="py-8 text-center text-sm text-muted-foreground">没有找到相关内容</p>
          )}
          {data?.map((item, i) => (
            <button
              key={`${item.kind}-${item.id}-${i}`}
              onClick={() => {
                if (item.kind === "journal") {
                  window.dispatchEvent(new CustomEvent("ts:open-journal-view", { detail: item.id }));
                } else if (item.kind === "landmark") {
                  // 飞行 + 打开详情
                  api.get(`/landmarks/${item.id}`).then((r) => {
                    const lm = r.data.data;
                    globeBus.flyTo(lm.lat, lm.lon, lm.id);
                  });
                  window.dispatchEvent(new CustomEvent("ts:open-detail", { detail: item.id }));
                } else {
                  setUserOpen(item.id);
                }
              }}
              className="flex w-full items-center gap-2.5 rounded-xl px-2.5 py-2 text-left transition hover:bg-accent"
            >
              {item.image_url ? (
                <img
                  src={item.image_url}
                  alt=""
                  className={`shrink-0 object-cover ${item.kind === "user" ? "h-8 w-8 rounded-full" : "h-8 w-8 rounded-lg"}`}
                />
              ) : (
                <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-muted">
                  {item.kind === "user" ? (
                    <UserIcon className="h-4 w-4 text-muted-foreground" />
                  ) : (
                    <MapPin className="h-4 w-4 text-muted-foreground" />
                  )}
                </div>
              )}
              <div className="min-w-0 flex-1">
                <div className="truncate text-sm">{item.title || "(无标题)"}</div>
                <div className="truncate text-xs text-muted-foreground">{item.subtitle}</div>
              </div>
            </button>
          ))}
          {!submitted && (
            <p className="py-10 text-center text-sm text-muted-foreground">
              搜索地标（点击飞过去看详情）或用户（打开主页）
            </p>
          )}
        </div>
      </FloatingWindow>

      {userOpen !== null && <UserProfileWindow userId={userOpen} onClose={() => setUserOpen(null)} />}
    </>
  );
}

