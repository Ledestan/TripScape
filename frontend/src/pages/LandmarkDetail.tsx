import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { MapPin, Eye, Star, Send, Flag, NotebookPen, MessageSquare, Compass } from "lucide-react";

import { api, errMessage } from "@/api/client";
import { useAuthStore } from "@/stores/auth";
import { globeBus } from "@/features/globe/Globe";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { Card, CardContent } from "@/components/ui/card";
import { FloatingWindow } from "@/components/FloatingWindow";
import ReportDialog from "@/features/comments/ReportDialog";
import { lazy, Suspense } from "react";

const JournalViewLazy = ({ journalId, onClose }: { journalId: number; onClose: () => void }) => (
  <Suspense fallback={null}>
    <JournalView journalId={journalId} onClose={onClose} />
  </Suspense>
);
const JournalView = lazy(() =>
  import("@/layouts/JournalViewWindow").then((m) => ({ default: m.JournalViewWindow }))
);
const LikeLazy = lazy(() =>
  import("@/layouts/JournalViewWindow").then((m) => ({ default: m.LikeButton }))
);
const LikeBtn = (p: { targetType: "journal" | "comment"; targetId: number }) => (
  <Suspense fallback={<span className="text-xs text-muted-foreground">…</span>}>
    <LikeLazy {...p} />
  </Suspense>
);

interface Comment {
  id: number;
  user: { id: number; nickname: string; avatar: string };
  content: string;
  created_at: string;
  replies: Comment[];
}

/**
 * 地标详情浮窗（在地球上打开，不切页）：
 * - 百科图 + 简介 + 评论/手账两个 Tab
 * - 写手账 = 隐藏本浮窗、打开手账浮窗；手账关闭后本浮窗回来
 */
export default function LandmarkDetailWindow({
  landmarkId,
  onClose,
  onWriteJournal,
}: {
  landmarkId: number;
  onClose: () => void;
  onWriteJournal: (landmarkId: number) => void;
}) {
  const [tab, setTab] = useState<"comments" | "journals">("comments");
  const [viewJournal, setViewJournal] = useState<number | null>(null);
  const [reportTarget, setReportTarget] = useState<{ type: "comment" | "journal"; id: number } | null>(null);
  const [editingComment, setEditingComment] = useState<number | null>(null);
  const [editText, setEditText] = useState("");
  const { token, user } = useAuthStore();
  const [text, setText] = useState("");
  const [replyTo, setReplyTo] = useState<Comment | null>(null);
  const qc = useQueryClient();

  const { data: lm } = useQuery({
    queryKey: ["landmark", landmarkId],
    queryFn: async () => (await api.get(`/landmarks/${landmarkId}`)).data.data,
    enabled: !!landmarkId,
  });

  const { data: comments, refetch } = useQuery({
    queryKey: ["comments", landmarkId],
    queryFn: async () => (await api.get(`/comments/landmark/${landmarkId}`)).data.data as Comment[],
    enabled: !!landmarkId,
  });

  const { data: journals } = useQuery({
    queryKey: ["journals", "landmark", landmarkId],
    queryFn: async () => (await api.get(`/journals/landmark/${landmarkId}`)).data.data,
    enabled: !!landmarkId,
  });

  const submit = useMutation({
    mutationFn: async () => {
      const payload = replyTo
        ? { landmark_id: landmarkId, content: text, parent_id: replyTo.id }
        : { landmark_id: landmarkId, content: text };
      return api.post("/comments/", payload);
    },
    onSuccess: () => {
      toast.success("评论已发布");
      setText("");
      setReplyTo(null);
      refetch();
      qc.invalidateQueries({ queryKey: ["landmark", landmarkId] });
    },
    onError: (e) => toast.error(errMessage(e, "评论失败")),
  });

  const report = useMutation({
    mutationFn: async (p: { id: number; reason: string; detail: string }) =>
      api.post("/comments/report", { target_type: "comment", target_id: p.id, reason: p.reason, detail: p.detail }),
    onSuccess: () => toast.success("举报已提交"),
  });

  const updateComment = useMutation({
    mutationFn: async (id: number) =>
      api.put(`/comments/${id}`, { landmark_id: landmarkId, content: editText }),
    onSuccess: () => {
      toast.success("评论已更新");
      setEditingComment(null);
      refetch();
    },
    onError: (e) => toast.error(errMessage(e, "更新失败")),
  });

  const delComment = useMutation({
    mutationFn: async (id: number) => api.delete(`/comments/${id}`),
    onSuccess: () => {
      toast.success("评论已删除");
      refetch();
      qc.invalidateQueries({ queryKey: ["landmark", landmarkId] });
    },
  });

  // 收藏状态（从个人主页数据判定是否已收藏）
  const { data: profile } = useQuery({
    queryKey: ["profile"],
    queryFn: async () => (await api.get("/auth/profile")).data as { favorites: { id: number }[] },
    enabled: !!token,
  });
  const favorited = profile?.favorites?.some((f) => f.id === landmarkId) ?? false;

  const fav = useMutation({
    mutationFn: async () => api.post(`/landmarks/${landmarkId}/favorite`),
    onSuccess: (r) => {
      toast.success(r.data.favorited ? "已收藏" : "已取消收藏");
      qc.invalidateQueries({ queryKey: ["profile"] });
    },
    onError: (e) => toast.error(errMessage(e)),
  });

  return (
    <>
    <FloatingWindow
      open
      onClose={onClose}
      title={lm ? `${lm.name} · 地标详情` : "地标详情"}
      width={460}
      fixedHeight="min(70vh, 640px)"
    >
      {lm && (
        <>
          {/* 头图（标题在图下方实底区，不压图） */}
          {lm.image_url && (
            <img
              src={lm.image_url}
              alt={lm.name}
              className="h-40 w-full rounded-xl object-cover"
              onError={(e) => ((e.target as HTMLImageElement).style.display = "none")}
            />
          )}

          {/* 标题/区域/统计（实底区，不叠图） */}
          <div className="mt-3">
            <h3 className="flex items-center gap-1.5 text-base font-bold">
              <MapPin className="h-4 w-4 text-primary" />
              {lm.name}
            </h3>
            <div className="mt-1 flex flex-wrap items-center gap-2 text-xs text-muted-foreground">
              {lm.country && <span>{lm.country}</span>}
              {lm.region && <span className="rounded-full bg-muted px-2 py-0.5">{lm.region}</span>}
              <span className="flex items-center gap-1">
                <Eye className="h-3 w-3" /> {lm.view_count}
              </span>
              <span className="flex items-center gap-1">
                <MessageSquare className="h-3 w-3" /> {lm.comment_count ?? comments?.length ?? 0}
              </span>
              <span className="flex items-center gap-1">
                <NotebookPen className="h-3 w-3" /> {lm.journal_count ?? 0}
              </span>
            </div>
          </div>

          {/* 简介 */}
          <p className="mt-2.5 text-sm leading-relaxed text-foreground/90">{lm.intro || "暂无介绍"}</p>

          {/* 操作 */}
          <div className="mt-3 flex flex-wrap items-center gap-2">
            <Button
              size="sm"
              onClick={() => globeBus.flyTo(lm.lat, lm.lon, lm.id)}
              className="bg-sky-500/90 text-foreground hover:bg-sky-400"
            >
              <Compass className="mr-1 h-3.5 w-3.5" /> 飞过去
            </Button>
            <Button size="sm" onClick={() => onWriteJournal(landmarkId)}>
              <NotebookPen className="mr-1 h-3.5 w-3.5" /> 写手账
            </Button>
            {token && (
              <Button
                size="sm"
                variant="outline"
                onClick={() => fav.mutate()}
                disabled={fav.isPending}
                className={favorited ? "border-amber-400 text-amber-500" : ""}
              >
                <Star
                  className={`mr-1 h-3.5 w-3.5 ${favorited ? "fill-amber-400 text-amber-400" : ""}`}
                />
                {favorited ? "已收藏" : "收藏"}
              </Button>
            )}
          </div>

          {/* Tab：评论 / 手账 */}
          <div className="mt-4 grid grid-cols-2 gap-1 rounded-xl bg-muted p-1">
            {(["comments", "journals"] as const).map((t) => (
              <button
                key={t}
                onClick={() => setTab(t)}
                className={`rounded-lg py-1.5 text-sm font-medium transition ${
                  tab === t ? "bg-background shadow" : "text-muted-foreground hover:text-foreground"
                }`}
              >
                {t === "comments" ? `评论（${comments?.length ?? 0}）` : `手账（${journals?.length ?? 0}）`}
              </button>
            ))}
          </div>

          {/* 评论 Tab */}
          {tab === "comments" && (
            <div className="mt-3">
              {token ? (
                <div className="mb-3">
                  {replyTo && (
                    <div className="mb-1.5 flex items-center gap-2 text-xs text-muted-foreground">
                      回复 @{replyTo.user.nickname}：
                      <button className="text-primary hover:underline" onClick={() => setReplyTo(null)}>
                        取消
                      </button>
                    </div>
                  )}
                  <Textarea
                    value={text}
                    onChange={(e) => setText(e.target.value)}
                    placeholder="发表评论…"
                    rows={2}
                  />
                  <div className="mt-1.5 flex justify-end">
                    <Button size="sm" disabled={!text.trim() || submit.isPending} onClick={() => submit.mutate()}>
                      <Send className="mr-1 h-3.5 w-3.5" />
                      {submit.isPending ? "发布中…" : "发布"}
                    </Button>
                  </div>
                </div>
              ) : (
                <p className="mb-3 rounded-xl border border-dashed p-2.5 text-center text-xs text-muted-foreground">
                  登录后可以发表评论
                </p>
              )}

              <div className="max-h-[26vh] space-y-2 overflow-y-auto pr-0.5">
                {comments?.length ? (
                  comments.map((c) => (
                    <div key={c.id}>
                      <Card>
                        <CardContent className="flex items-start gap-2.5 p-3">
                          {c.user.avatar ? (
                            <img src={c.user.avatar} alt="" className="h-7 w-7 rounded-full object-cover" />
                          ) : (
                            <div className="flex h-7 w-7 items-center justify-center rounded-full bg-accent text-xs">
                              {c.user.nickname[0]}
                            </div>
                          )}
                          <div className="min-w-0 flex-1">
                            <div className="flex items-center gap-2 text-xs text-muted-foreground">
                              <span className="font-medium text-foreground">{c.user.nickname}</span>
                              <span>{new Date(c.created_at).toLocaleString("zh-CN")}</span>
                            </div>
                            {editingComment === c.id ? (
                              <div className="mt-1">
                                <textarea
                                  value={editText}
                                  onChange={(e) => setEditText(e.target.value)}
                                  rows={2}
                                  className="w-full rounded-lg border border-border bg-background px-2.5 py-1.5 text-sm outline-none focus:border-primary"
                                />
                                <div className="mt-1 flex justify-end gap-1.5">
                                  <button
                                    className="rounded-lg px-2 py-1 text-xs hover:bg-muted"
                                    onClick={() => setEditingComment(null)}
                                  >
                                    取消
                                  </button>
                                  <button
                                    className="rounded-lg bg-primary px-2.5 py-1 text-xs text-primary-foreground"
                                    onClick={() => updateComment.mutate(c.id)}
                                  >
                                    保存
                                  </button>
                                </div>
                              </div>
                            ) : (
                              <p className="mt-0.5 break-words text-sm">{c.content}</p>
                            )}
                            <div className="mt-1 flex items-center gap-3 text-xs text-muted-foreground">
                              <button className="hover:text-primary" onClick={() => setReplyTo(c)}>
                                回复
                              </button>
                              <LikeBtn targetType="comment" targetId={c.id} />
                              {user?.id === c.user.id ? (
                                <>
                                  <button
                                    className="hover:text-primary"
                                    onClick={() => {
                                      setEditingComment(c.id);
                                      setEditText(c.content);
                                    }}
                                  >
                                    编辑
                                  </button>
                                  <button
                                    className="hover:text-destructive"
                                    onClick={() => {
                                      if (confirm("删除这条评论？")) delComment.mutate(c.id);
                                    }}
                                  >
                                    删除
                                  </button>
                                </>
                              ) : (
                                <button
                                  className="flex items-center gap-0.5 hover:text-destructive"
                                  onClick={() => setReportTarget({ type: "comment", id: c.id })}
                                >
                                  <Flag className="h-3 w-3" /> 举报
                                </button>
                              )}
                            </div>
                          </div>
                        </CardContent>
                      </Card>
                      {c.replies?.length > 0 && (
                        <div className="ml-6 mt-1.5 space-y-1.5 border-l-2 border-border pl-3">
                          {c.replies.map((r) => (
                            <Card key={r.id}>
                              <CardContent className="p-2.5">
                                <div className="flex items-center gap-2 text-xs text-muted-foreground">
                                  <span className="font-medium text-foreground">{r.user.nickname}</span>
                                  <span>{new Date(r.created_at).toLocaleString("zh-CN")}</span>
                                </div>
                                <p className="mt-0.5 break-words text-sm">{r.content}</p>
                              </CardContent>
                            </Card>
                          ))}
                        </div>
                      )}
                    </div>
                  ))
                ) : (
                  <p className="py-6 text-center text-sm text-muted-foreground">还没有评论，来抢沙发！</p>
                )}
              </div>
            </div>
          )}

          {/* 手账 Tab */}
          {tab === "journals" && (
            <div className="mt-3 grid max-h-[30vh] gap-2 overflow-y-auto pr-0.5 sm:grid-cols-2">
              {journals?.length ? (
                journals.map((j: any) => (
                  <Card
                    key={j.id}
                    className="cursor-pointer overflow-hidden transition hover:border-primary/50"
                    onClick={() => setViewJournal(j.id)}
                  >
                    {j.images?.[0] && (
                      <img src={j.images[0]} alt="" className="h-28 w-full rounded-t-xl object-cover" />
                    )}
                    <CardContent className="p-3">
                      <div className="text-sm font-medium">{j.title}</div>
                      <div className="mt-0.5 text-xs text-muted-foreground">
                        {j.user?.nickname} · {new Date(j.created_at).toLocaleDateString("zh-CN")}
                      </div>
                    </CardContent>
                  </Card>
                ))
              ) : (
                <p className="py-6 text-center text-sm text-muted-foreground sm:col-span-2">
                  还没有公开手账，写下第一篇吧！
                </p>
              )}
            </div>
          )}
        </>
      )}
    </FloatingWindow>

      {viewJournal !== null && <JournalViewLazy journalId={viewJournal} onClose={() => setViewJournal(null)} />}
      {reportTarget && (
        <ReportDialog
          targetType={reportTarget.type}
          targetId={reportTarget.id}
          onClose={() => setReportTarget(null)}
        />
      )}
    </>
  );
}
