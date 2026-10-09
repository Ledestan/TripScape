import { useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { MapPin, NotebookPen, MessageSquare, Star, Award, Compass, EyeOff } from "lucide-react";

import { api } from "@/api/client";
import { FloatingWindow } from "@/components/FloatingWindow";
import { globeBus } from "@/features/globe/Globe";
import { JournalViewWindow } from "@/layouts/JournalViewWindow";

interface PublicProfile {
  user: { id: number; username: string; nickname: string; avatar: string; bio: string; created_at: string };
  privacy: { footprints: boolean; journals: boolean; comments: boolean; favorites: boolean; badges: boolean };
  counts: { footprints: number; journals: number; comments: number; favorites: number };
  footprints: { landmark_id: number; name: string; lat: number; lon: number; visits: number }[];
  journals: { id: number; title: string; content?: string; landmark: string; landmark_id: number; lat: number; lon: number; visited_at: string | null; images?: string[] }[];
  comments: { id: number; landmark: string; landmark_id: number; lat?: number; lon?: number; content: string; created_at: string }[];
  favorites: { id: number; name: string; lat: number; lon: number }[];
  badges: { code: string; name: string; icon: string; description: string }[];
}

type Tab = "footprints" | "journals" | "comments" | "favorites" | "badges";

/**
 * 用户公开主页浮窗（五 Tab + 隐私过滤 + 固定尺寸，与个人中心一致）
 */
export default function UserProfileWindow({ userId, onClose }: { userId: number; onClose: () => void }) {
  const [tab, setTab] = useState<Tab>("footprints");
  const [viewJournal, setViewJournal] = useState<number | null>(null);

  const { data } = useQuery({
    queryKey: ["user-public", userId],
    queryFn: async () => (await api.get(`/auth/${userId}/public`)).data as PublicProfile,
  });

  const flyTo = (lat: number, lon: number, id?: number) => {
    globeBus.flyTo(lat, lon, id);
    onClose();
  };

  const p = data?.privacy;

  return (
    <>
    <FloatingWindow
      open
      onClose={onClose}
      title={data ? `${data.user.nickname} 的主页` : "用户主页"}
      width={540}
      fixedHeight="min(72vh, 620px)"
    >
      {!data ? (
        <div className="py-10 text-center text-sm text-muted-foreground">加载中…</div>
      ) : (
        <>
          {/* 用户信息头 */}
          <div className="flex items-center gap-3">
            {data.user.avatar ? (
              <img src={data.user.avatar} alt="" className="h-12 w-12 rounded-full object-cover" />
            ) : (
              <div className="flex h-12 w-12 items-center justify-center rounded-full bg-primary/15 text-lg font-bold text-primary">
                {data.user.nickname.slice(0, 1)}
              </div>
            )}
            <div className="min-w-0 flex-1">
              <div className="truncate font-semibold">{data.user.nickname}</div>
              <div className="truncate text-xs text-muted-foreground">
                @{data.user.username} · {new Date(data.user.created_at).toLocaleDateString("zh-CN")} 加入
              </div>
            </div>
          </div>
          {data.user.bio && <p className="mt-2 text-sm text-muted-foreground">{data.user.bio}</p>}

          {/* Tab 头（隐藏的 Tab 显示关闭图标且不可点） */}
          <div className="mt-3 grid grid-cols-5 gap-1 rounded-xl bg-muted p-1">
            {([
              { key: "footprints", label: "足迹", value: data.counts.footprints, on: p?.footprints, icon: <MapPin className="h-4 w-4" /> },
              { key: "journals", label: "手账", value: data.counts.journals, on: p?.journals, icon: <NotebookPen className="h-4 w-4" /> },
              { key: "comments", label: "评论", value: data.counts.comments, on: p?.comments, icon: <MessageSquare className="h-4 w-4" /> },
              { key: "favorites", label: "收藏", value: data.counts.favorites, on: p?.favorites, icon: <Star className="h-4 w-4" /> },
              { key: "badges", label: "徽章", value: data.badges?.length ?? 0, on: p?.badges, icon: <Award className="h-4 w-4" /> },
            ] as const).map((it) => (
              <button
                key={it.key}
                onClick={() => it.on !== false && setTab(it.key)}
                disabled={it.on === false}
                className={`flex flex-col items-center gap-0.5 rounded-lg py-1.5 text-sm font-medium transition ${
                  it.on === false
                    ? "cursor-not-allowed text-muted-foreground/40"
                    : tab === it.key
                      ? "bg-background shadow text-foreground"
                      : "text-muted-foreground hover:text-foreground"
                }`}
                title={it.on === false ? "对方未公开" : undefined}
              >
                <span className="flex items-center gap-1">
                  {it.on === false ? <EyeOff className="h-3.5 w-3.5" /> : it.icon}
                  {it.label}
                </span>
                <span className="text-xs font-normal text-muted-foreground">{it.on === false ? "-" : it.value}</span>
              </button>
            ))}
          </div>

          {/* Tab 内容（滚动） */}
          <div className="mt-3 flex-1 overflow-y-auto pr-0.5">
            {tab === "footprints" && (
              <div className="space-y-1.5">
                {data.footprints.length ? (
                  data.footprints.map((f) => (
                    <div key={f.landmark_id} className="flex items-center justify-between rounded-xl border border-border bg-muted/40 px-3.5 py-2.5">
                      <div className="flex min-w-0 items-center gap-2">
                        <MapPin className="h-4 w-4 shrink-0 text-amber-500" />
                        <span className="truncate text-sm">{f.name}</span>
                      </div>
                      <div className="ml-2 flex shrink-0 items-center gap-2">
                        <span className="text-xs text-muted-foreground">到访 {f.visits} 次</span>
                        <FlyBtn onClick={() => flyTo(f.lat, f.lon, f.landmark_id)} />
                      </div>
                    </div>
                  ))
                ) : (
                  <Empty text="暂无公开足迹" />
                )}
              </div>
            )}

            {tab === "journals" && (
              <div className="space-y-1.5">
                {data.journals.length ? (
                  data.journals.map((j) => (
                    <div key={j.id} className="flex items-center justify-between rounded-xl border border-border bg-muted/40 px-3.5 py-2.5">
                      <button
                        onClick={() => setViewJournal(j.id)}
                        className="min-w-0 flex-1 text-left"
                        title="查看手账"
                      >
                        <div className="truncate text-sm font-medium hover:underline">{j.title}</div>
                        <div className="mt-0.5 text-xs text-muted-foreground">
                          {j.landmark} · {j.visited_at || "未记日期"}
                        </div>
                      </button>
                      <div className="ml-2 flex shrink-0 items-center gap-1.5">
                        {j.lat !== undefined && j.lon !== undefined && (
                          <FlyBtn onClick={() => flyTo(j.lat, j.lon, j.landmark_id)} />
                        )}
                      </div>
                    </div>
                  ))
                ) : (
                  <Empty text="暂无公开手账" />
                )}
              </div>
            )}

            {tab === "comments" && (
              <div className="space-y-1.5">
                {data.comments.length ? (
                  data.comments.map((c) => (
                    <div key={c.id} className="rounded-xl border border-border bg-muted/40 px-3.5 py-2.5">
                      <div className="flex items-center justify-between text-xs text-muted-foreground">
                        <span className="truncate">在 {c.landmark}</span>
                        <div className="ml-2 flex shrink-0 items-center gap-1.5">
                          <span>{new Date(c.created_at).toLocaleString("zh-CN")}</span>
                          {c.lat !== undefined && c.lon !== undefined && (
                            <FlyBtn onClick={() => flyTo(c.lat!, c.lon!, c.landmark_id)} />
                          )}
                        </div>
                      </div>
                      <p className="mt-1 line-clamp-3 text-sm">{c.content}</p>
                    </div>
                  ))
                ) : (
                  <Empty text="暂无公开评论" />
                )}
              </div>
            )}

            {tab === "favorites" && (
              <div className="grid grid-cols-2 gap-1.5">
                {data.favorites.length ? (
                  data.favorites.map((f) => (
                    <div key={f.id} className="flex items-center justify-between rounded-xl border border-border bg-muted/40 px-3 py-2.5">
                      <span className="flex min-w-0 items-center gap-1.5 truncate text-sm">
                        <Star className="h-4 w-4 shrink-0 fill-amber-400 text-amber-400" />
                        {f.name}
                      </span>
                      <FlyBtn onClick={() => flyTo(f.lat, f.lon, f.id)} />
                    </div>
                  ))
                ) : (
                  <div className="col-span-2"><Empty text="暂无公开收藏" /></div>
                )}
              </div>
            )}

            {tab === "badges" && (
              <div className="grid grid-cols-2 gap-2">
                {data.badges?.length ? (
                  data.badges.map((b) => (
                    <div key={b.code} className="flex items-center gap-2.5 rounded-xl border border-amber-400/60 bg-amber-400/10 p-3">
                      <div className="text-2xl">{b.icon}</div>
                      <div className="min-w-0">
                        <div className="truncate text-sm font-medium">{b.name}</div>
                        <div className="truncate text-[11px] text-muted-foreground">{b.description}</div>
                      </div>
                    </div>
                  ))
                ) : (
                  <div className="col-span-2"><Empty text="暂无公开徽章" /></div>
                )}
              </div>
            )}
          </div>
        </>
      )}
    </FloatingWindow>

      {viewJournal !== null && <JournalViewWindow journalId={viewJournal} onClose={() => setViewJournal(null)} />}
    </>
  );
}

function FlyBtn({ onClick }: { onClick: () => void }) {
  return (
    <button
      onClick={onClick}
      className="flex items-center gap-1 rounded-lg border border-border bg-card px-2 py-1 text-[11px] transition hover:bg-accent"
      title="在地球上查看"
    >
      <Compass className="h-3 w-3" /> 飞过去
    </button>
  );
}

function Empty({ text }: { text: string }) {
  return <div className="flex flex-col items-center gap-1 py-10 text-center"><p className="text-xs text-muted-foreground">{text}</p></div>;
}
