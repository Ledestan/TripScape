import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import {
  MapPin, NotebookPen, MessageSquare, Star, Pencil, Compass, Award, Eye, EyeOff, Trash2,
} from "lucide-react";

import { api, errMessage } from "@/api/client";
import { useAuthStore } from "@/stores/auth";
import { globeBus } from "@/features/globe/Globe";
import { FloatingWindow } from "@/components/FloatingWindow";
import JournalEditWindow from "@/pages/JournalEditWindow";
import { JournalViewWindow } from "@/layouts/JournalViewWindow";

/* ================================================================== */
/* 个人主页（五 Tab：足迹/手账/评论/收藏/徽章，固定高度内容滚动）         */
/* ================================================================== */

interface ProfileData {
  user?: {
    id: number;
    username: string;
    nickname: string;
    banned?: boolean;
    muted_until?: string | null;
    locked_until?: string | null;
  };
  counts: { footprints: number; journals: number; comments: number; favorites: number };
  footprints: { landmark_id: number; name: string; lat: number; lon: number; visits: number; hidden?: boolean; last_visited_at?: string }[];
  journals: { id: number; title: string; landmark: string; landmark_id?: number; lat?: number; lon?: number; visited_at: string | null; is_public: boolean }[];
  comments: { id: number; landmark: string; landmark_id?: number; lat?: number; lon?: number; content: string; created_at: string }[];
  favorites: { id: number; name: string; lat?: number; lon?: number }[];
}

export default function ProfileWindow({ onClose }: { onClose: () => void }) {
  const qc = useQueryClient();
  const { user } = useAuthStore();
  const [tab, setTab] = useState<"footprints" | "journals" | "comments" | "favorites" | "badges">("footprints");
  const [viewJournal, setViewJournal] = useState<number | null>(null);
  const [editJournal, setEditJournal] = useState<{ id?: number; landmarkId?: number } | null>(null);

  /* 足迹隐藏/显示 */
  const toggleFootprint = async (lmId: number) => {
    try {
      await api.post(`/footprints/${lmId}/visibility`);
      qc.invalidateQueries({ queryKey: ["profile"] });
    } catch (e) {
      toast.error(errMessage(e, "操作失败"));
    }
  };

  /* 删除手账 */
  const delJournal = useMutation({
    mutationFn: async (id: number) => api.delete(`/journals/${id}`),
    onSuccess: () => {
      toast.success("手账已删除");
      qc.invalidateQueries({ queryKey: ["profile"] });
    },
    onError: (e) => toast.error(errMessage(e, "删除失败")),
  });

  const { data } = useQuery({
    queryKey: ["profile"],
    queryFn: async () => (await api.get("/auth/profile")).data as ProfileData,
    // 个人中心是低频页面：每次打开都重新取，避免评论/手账刚写完仍显示旧缓存
    staleTime: 0,
    refetchOnMount: "always",
  });

  /* 我的徽章（含进度） */
  const { data: badges } = useQuery({
    queryKey: ["badges", "mine"],
    queryFn: async () =>
      (await api.get("/badges/mine")).data.data as {
        code: string; name: string; icon: string; description: string;
        owned: boolean; progress: number; current: number; threshold: number;
      }[],
  });

  const flyTo = (lat: number, lon: number, id?: number) => globeBus.flyTo(lat, lon, id);

  return (
    <>
      <FloatingWindow
        open
        onClose={onClose}
        title={`${user?.nickname ?? ""} · 个人主页`}
        width={540}
        fixedHeight="min(72vh, 620px)"
      >
        {!data ? (
          <div className="py-10 text-center text-sm text-muted-foreground">加载中…</div>
        ) : (
          <>
            {/* 账号状态（被封/禁言/限登时可见） */}
            {(data.user?.banned || data.user?.muted_until || data.user?.locked_until) && (
              <div className="mb-3 rounded-xl border border-amber-400/40 bg-amber-400/10 p-2.5 text-xs">
                <div className="font-medium text-amber-600 dark:text-amber-400">账号状态</div>
                <ul className="mt-1 space-y-0.5 text-muted-foreground">
                  {data.user?.banned && <li>· 账号已被封禁，请联系管理员申诉</li>}
                  {data.user?.muted_until && <li>· 禁言至 {new Date(data.user.muted_until).toLocaleString("zh-CN")}</li>}
                  {data.user?.locked_until && <li>· 限制登录至 {new Date(data.user.locked_until).toLocaleString("zh-CN")}</li>}
                </ul>
              </div>
            )}

            {/* Tab 头（带计数；徽章显示已获得数） */}
            <div className="grid grid-cols-5 gap-1 rounded-xl bg-muted p-1">
              {([
                { key: "footprints", label: "足迹", value: data.counts.footprints, icon: <MapPin className="h-4 w-4" /> },
                { key: "journals", label: "手账", value: data.counts.journals, icon: <NotebookPen className="h-4 w-4" /> },
                { key: "comments", label: "评论", value: data.counts.comments, icon: <MessageSquare className="h-4 w-4" /> },
                { key: "favorites", label: "收藏", value: data.counts.favorites, icon: <Star className="h-4 w-4" /> },
                { key: "badges", label: "徽章", value: badges?.filter((b) => b.owned).length ?? 0, icon: <Award className="h-4 w-4" /> },
              ] as const).map((it) => (
                <button
                  key={it.key}
                  onClick={() => setTab(it.key)}
                  className={`flex flex-col items-center gap-0.5 rounded-lg py-1.5 text-sm font-medium transition ${
                    tab === it.key ? "bg-background shadow text-foreground" : "text-muted-foreground hover:text-foreground"
                  }`}
                >
                  <span className="flex items-center gap-1">{it.icon}{it.label}</span>
                  <span className="text-xs font-normal text-muted-foreground">{it.value}</span>
                </button>
              ))}
            </div>

            {/* Tab 内容：滚动 */}
            <div className="mt-3 flex-1 overflow-y-auto pr-0.5">
              {tab === "footprints" && (
                <Section title={`我的足迹（${data.footprints.length}）`}>
                  {data.footprints.length ? (
                    data.footprints.map((f) => (
                      <div
                        key={f.landmark_id}
                        className={`flex items-center justify-between rounded-xl border border-border bg-muted/40 px-3.5 py-2.5 ${f.hidden ? "opacity-50" : ""}`}
                      >
                        <div className="flex min-w-0 items-center gap-2">
                          <MapPin className="h-4 w-4 shrink-0 text-amber-500" />
                          <span className="truncate text-sm">{f.name}</span>
                        </div>
                        <div className="ml-2 flex shrink-0 items-center gap-1.5">
                          <span className="text-xs text-muted-foreground">到访 {f.visits} 次</span>
                          <FlyButton onClick={() => flyTo(f.lat, f.lon, f.landmark_id)} />
                          <button
                            onClick={() => toggleFootprint(f.landmark_id)}
                            className="rounded-lg border border-border bg-card p-1.5 transition hover:bg-accent"
                            title={f.hidden ? "显示足迹" : "隐藏足迹"}
                          >
                            {f.hidden ? <EyeOff className="h-3.5 w-3.5" /> : <Eye className="h-3.5 w-3.5" />}
                          </button>
                        </div>
                      </div>
                    ))
                  ) : (
                    <EmptyHint text="还没有足迹，写下第一篇手账就会生成足迹" />
                  )}
                </Section>
              )}

              {tab === "journals" && (
                <Section title={`我的手账（${data.journals.length}）`}>
                  {data.journals.length ? (
                    data.journals.map((j) => (
                      <div key={j.id} className="flex items-center justify-between rounded-xl border border-border bg-muted/40 px-3.5 py-2.5">
                        <button onClick={() => setViewJournal(j.id)} className="min-w-0 flex-1 text-left" title="查看手账">
                          <div className="truncate text-sm font-medium hover:underline">{j.title}</div>
                          <div className="mt-0.5 text-xs text-muted-foreground">
                            {j.landmark} · {j.visited_at || "未记日期"} · {j.is_public ? "公开" : "私密"}
                          </div>
                        </button>
                        <div className="ml-2 flex shrink-0 items-center gap-1.5">
                          {j.lat !== undefined && j.lon !== undefined && (
                            <FlyButton onClick={() => flyTo(j.lat!, j.lon!, j.landmark_id)} />
                          )}
                          <button
                            onClick={() => setEditJournal({ id: j.id })}
                            className="flex items-center gap-1 rounded-lg border border-border bg-card px-2.5 py-1.5 text-xs transition hover:bg-accent"
                          >
                            <Pencil className="h-3 w-3" /> 编辑
                          </button>
                          <button
                            onClick={() => {
                              if (confirm(`删除手账《${j.title}》？`)) delJournal.mutate(j.id);
                            }}
                            className="flex items-center gap-1 rounded-lg border border-border bg-card px-2.5 py-1.5 text-xs text-destructive transition hover:bg-destructive/10"
                          >
                            <Trash2 className="h-3 w-3" /> 删除
                          </button>
                        </div>
                      </div>
                    ))
                  ) : (
                    <EmptyHint text="还没有手账" />
                  )}
                </Section>
              )}

              {tab === "comments" && (
                <Section title={`我的评论（${data.comments.length}）`}>
                  {data.comments.length ? (
                    data.comments.map((c) => (
                      <div key={c.id} className="rounded-xl border border-border bg-muted/40 px-3.5 py-2.5">
                        <div className="flex items-center justify-between text-xs text-muted-foreground">
                          <span className="truncate">在 {c.landmark}</span>
                          <div className="ml-2 flex shrink-0 items-center gap-1.5">
                            <span>{new Date(c.created_at).toLocaleString("zh-CN")}</span>
                            {c.lat !== undefined && c.lon !== undefined && (
                              <FlyButton onClick={() => flyTo(c.lat!, c.lon!, c.landmark_id)} />
                            )}
                          </div>
                        </div>
                        <p className="mt-1 line-clamp-3 text-sm">{c.content}</p>
                      </div>
                    ))
                  ) : (
                    <EmptyHint text="还没有评论" />
                  )}
                </Section>
              )}

              {tab === "favorites" && (
                <Section title={`我的收藏（${data.favorites.length}）`}>
                  {data.favorites.length ? (
                    <div className="grid grid-cols-2 gap-1.5">
                      {data.favorites.map((f) => (
                        <div key={f.id} className="flex items-center justify-between rounded-xl border border-border bg-muted/40 px-3 py-2.5">
                          <span className="flex min-w-0 items-center gap-1.5 truncate text-sm">
                            <Star className="h-4 w-4 shrink-0 fill-amber-400 text-amber-400" />
                            {f.name}
                          </span>
                          {f.lat !== undefined && f.lon !== undefined && (
                            <FlyButton onClick={() => flyTo(f.lat!, f.lon!, f.id)} />
                          )}
                        </div>
                      ))}
                    </div>
                  ) : (
                    <EmptyHint text="还没有收藏" />
                  )}
                </Section>
              )}

              {tab === "badges" && (
                <Section title="我的徽章">
                  {badges?.length ? (
                    <div className="grid grid-cols-2 gap-2">
                      {badges.map((b) => (
                        <div
                          key={b.code}
                          className={`flex items-center gap-2.5 rounded-xl border p-3 ${
                            b.owned ? "border-amber-400/60 bg-amber-400/10" : "border-border bg-muted/40 opacity-60"
                          }`}
                        >
                          <div className={`text-2xl ${b.owned ? "" : "grayscale"}`}>{b.icon}</div>
                          <div className="min-w-0 flex-1">
                            <div className="flex items-center gap-1.5">
                              <span className="truncate text-sm font-medium">{b.name}</span>
                              {b.owned && (
                                <span className="shrink-0 rounded-full bg-amber-400/20 px-1.5 py-0.5 text-[10px] text-amber-500">已获得</span>
                              )}
                            </div>
                            <div className="truncate text-[11px] text-muted-foreground">{b.description}</div>
                            {!b.owned && (
                              <div className="mt-1">
                                <div className="h-1 w-full overflow-hidden rounded-full bg-muted">
                                  <div className="h-full rounded-full bg-primary" style={{ width: `${Math.round(b.progress * 100)}%` }} />
                                </div>
                                <div className="mt-0.5 text-right text-[10px] text-muted-foreground">{b.current}/{b.threshold}</div>
                              </div>
                            )}
                          </div>
                        </div>
                      ))}
                    </div>
                  ) : (
                    <EmptyHint text="徽章加载中" />
                  )}
                </Section>
              )}
            </div>
          </>
        )}
      </FloatingWindow>

      {/* 叠浮窗：查看手账 / 编辑手账（不关闭个人主页） */}
      {viewJournal !== null && <JournalViewWindow journalId={viewJournal} onClose={() => setViewJournal(null)} />}
      {editJournal && (
        <JournalEditWindow
          presetJournalId={editJournal.id}
          presetLandmarkId={editJournal.landmarkId}
          onClose={() => {
            setEditJournal(null);
            qc.invalidateQueries({ queryKey: ["profile"] });
          }}
        />
      )}
    </>
  );
}

/* ---------------- 小工具组件 ---------------- */

function FlyButton({ onClick }: { onClick: () => void }) {
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

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div>
      <div className="mb-2 text-sm font-semibold">{title}</div>
      <div className="space-y-1.5">{children}</div>
    </div>
  );
}

function EmptyHint({ text }: { text: string }) {
  return <div className="flex flex-col items-center gap-1 py-10 text-center"><p className="text-xs text-muted-foreground">{text}</p></div>;
}
