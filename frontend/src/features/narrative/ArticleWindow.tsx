/**
 * 行旅识景 TripScape / 文章详情页
 * 创建日期: 2026-11-26

 * 地标文章的独立阅读页（从档案面板"查看全文"打开），完成:
 *     1. 全文阅读：整体介绍、时间轴、全部分节（不折叠）
 *     2. 点赞：target_type=article，target_id=地标 id
 *     3. 评论、回复、修改、删除、给评论点赞
 *
 * 依赖:
 *     依赖库: @tanstack/react-query, lucide-react, sonner
 *
 * 用法:
 *     <ArticleWindow landmarkId={id} onClose={() => setOpen(false)} />
 *
 * 注意:
 *     1. 评论复用 /api/comments/landmark/{id}，与地标详情同一份数据。
 *     2. 点赞复用 /api/likes/，target_type 用 article。
 */

import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Flag, Heart, MessageSquare, Send } from "lucide-react";
import { toast } from "sonner";

import { api, errMessage } from "@/api/client";
import { FloatingWindow } from "@/components/FloatingWindow";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import type { LandmarkStoryData } from "@/features/narrative/types";
import LandmarkStoryView from "@/features/narrative/LandmarkStoryView";
import { useAuthStore } from "@/stores/auth";

interface ArticleComment {
  id: number;
  user: { id: number; nickname: string; avatar: string };
  parent_id: number | null;
  content: string;
  created_at: string;
  replies?: ArticleComment[];
}

export default function ArticleWindow({
  landmarkId,
  title,
  onClose,
}: {
  landmarkId: number;
  title?: string;
  onClose: () => void;
}) {
  const token = useAuthStore((s) => s.token);
  const me = useAuthStore((s) => s.user);
  const qc = useQueryClient();
  const [text, setText] = useState("");
  const [replyTo, setReplyTo] = useState<ArticleComment | null>(null);
  const [editing, setEditing] = useState<number | null>(null);
  const [editText, setEditText] = useState("");

  const { data: story } = useQuery({
    queryKey: ["narrative", "story", landmarkId, "article"],
    queryFn: async () =>
      (await api.get(`/narrative/story/${landmarkId}`)).data.data as LandmarkStoryData,
  });

  const {
    data: comments,
    refetch,
  } = useQuery({
    queryKey: ["comments", "landmark", landmarkId],
    queryFn: async () =>
      (await api.get(`/comments/landmark/${landmarkId}`)).data.data as ArticleComment[],
  });

  const requireLogin = (): boolean => {
    if (token) return true;
    toast.error("登录后才能评论");
    window.dispatchEvent(new CustomEvent("ts:open-login"));
    return false;
  };

  const submit = useMutation({
    mutationFn: async () => {
      const payload = replyTo
        ? { landmark_id: landmarkId, content: text, parent_id: replyTo.id }
        : { landmark_id: landmarkId, content: text };
      return api.post("/comments/", payload);
    },
    onSuccess: () => {
      setText("");
      setReplyTo(null);
      refetch();
      qc.invalidateQueries({ queryKey: ["profile"] });
      toast.success("评论已发布");
    },
    onError: (error) => toast.error(errMessage(error, "评论失败")),
  });

  const updateComment = useMutation({
    mutationFn: async (id: number) =>
      api.put(`/comments/${id}`, { landmark_id: landmarkId, content: editText }),
    onSuccess: () => {
      setEditing(null);
      refetch();
      toast.success("评论已更新");
    },
    onError: (error) => toast.error(errMessage(error, "更新失败")),
  });

  const deleteComment = useMutation({
    mutationFn: async (id: number) => api.delete(`/comments/${id}`),
    onSuccess: () => {
      refetch();
      qc.invalidateQueries({ queryKey: ["profile"] });
      toast.success("评论已删除");
    },
    onError: (error) => toast.error(errMessage(error, "删除失败")),
  });

  const articleTitle = title || story?.title || "文章";
  const total = comments?.reduce((sum, item) => sum + 1 + (item.replies?.length || 0), 0) || 0;

  const renderComment = (comment: ArticleComment, isReply = false) => {
    const mine = me?.id === comment.user.id;
    return (
      <div
        key={comment.id}
        className={isReply ? "ml-6 mt-2" : "mt-3"}
        data-testid={isReply ? "article-reply" : "article-comment"}
      >
        <div className="flex items-start gap-2">
          <img src={comment.user.avatar} alt="" className="h-6 w-6 rounded-full object-cover" />
          <div className="min-w-0 flex-1">
            <div className="flex items-center gap-1.5 text-[11px] text-muted-foreground">
              <span className="font-medium text-foreground">{comment.user.nickname}</span>
              <span>{new Date(comment.created_at).toLocaleDateString("zh-CN")}</span>
            </div>

            {editing === comment.id ? (
              <div className="mt-1 space-y-1">
                <Textarea
                  value={editText}
                  onChange={(event) => setEditText(event.target.value)}
                  rows={2}
                  className="text-[12px]"
                />
                <div className="flex gap-1.5">
                  <Button size="sm" className="h-6 text-[11px]" onClick={() => updateComment.mutate(comment.id)}>
                    保存
                  </Button>
                  <Button
                    size="sm"
                    variant="ghost"
                    className="h-6 text-[11px]"
                    onClick={() => setEditing(null)}
                  >
                    取消
                  </Button>
                </div>
              </div>
            ) : (
              <p className="mt-0.5 whitespace-pre-wrap text-[12px] leading-relaxed text-foreground/85">
                {comment.content}
              </p>
            )}

            <div className="mt-1 flex items-center gap-2 text-[10.5px] text-muted-foreground">
              <button
                type="button"
                className="flex items-center gap-0.5 hover:text-rose-500"
                onClick={async () => {
                  if (!requireLogin()) return;
                  try {
                    await api.post("/likes/", { target_type: "comment", target_id: comment.id });
                    refetch();
                  } catch (error) {
                    toast.error(errMessage(error, "操作失败"));
                  }
                }}
              >
                <Heart className="h-3 w-3" />
                赞
              </button>
              {!isReply && (
                <button
                  type="button"
                  className="hover:text-primary"
                  onClick={() => {
                    if (!requireLogin()) return;
                    setReplyTo(comment);
                  }}
                >
                  回复
                </button>
              )}
              {mine && (
                <>
                  <button
                    type="button"
                    className="hover:text-primary"
                    onClick={() => {
                      setEditing(comment.id);
                      setEditText(comment.content);
                    }}
                  >
                    修改
                  </button>
                  <button
                    type="button"
                    className="hover:text-destructive"
                    onClick={() => deleteComment.mutate(comment.id)}
                  >
                    删除
                  </button>
                </>
              )}
            </div>
          </div>
        </div>

        {comment.replies?.map((reply) => renderComment(reply, true))}
      </div>
    );
  };

  return (
    <FloatingWindow
      open
      onClose={onClose}
      title={`${articleTitle} · 文章`}
      width={560}
      maxHeight="78vh"
      testId="article-window"
    >
      {!story ? (
        <p className="py-6 text-center text-[12px] text-muted-foreground">文章加载中…</p>
      ) : (
        <div className="space-y-4">
          <div className="flex items-center gap-2">
            <ArticleLike landmarkId={landmarkId} />
            <span className="flex items-center gap-1 text-[11px] text-muted-foreground">
              <MessageSquare className="h-3 w-3" />
              {total} 条评论
            </span>
          </div>

          <article className="max-h-[42vh] overflow-y-auto pr-1">
            <LandmarkStoryView story={story} expanded />
          </article>

          <div className="border-t border-border/60 pt-3">
            <div className="flex items-start gap-2">
              <Textarea
                value={text}
                onChange={(event) => setText(event.target.value)}
                rows={2}
                data-testid="article-comment-input"
                placeholder={replyTo ? `回复 @${replyTo.user.nickname}` : "说点什么…"}
                className="text-[12px]"
              />
              <Button
                size="sm"
                className="h-8 shrink-0 text-[11px]"
                disabled={!text.trim() || submit.isPending}
                onClick={() => {
                  if (!requireLogin()) return;
                  submit.mutate();
                }}
              >
                <Send className="mr-1 h-3 w-3" />
                发送
              </Button>
            </div>
            {replyTo && (
              <button
                type="button"
                className="mt-1 text-[10.5px] text-muted-foreground hover:text-primary"
                onClick={() => setReplyTo(null)}
              >
                取消回复 @{replyTo.user.nickname}
              </button>
            )}

            <div className="mt-2 max-h-[26vh] overflow-y-auto pr-1">
              {comments?.length ? (
                comments.map((comment) => renderComment(comment))
              ) : (
                <p className="py-4 text-center text-[11px] text-muted-foreground">
                  还没有评论，来写第一条。
                </p>
              )}
            </div>
          </div>
        </div>
      )}
    </FloatingWindow>
  );
}

/** 文章点赞：target_type=article，target_id=地标 id */
function ArticleLike({ landmarkId }: { landmarkId: number }) {
  const token = useAuthStore((s) => s.token);
  const [liked, setLiked] = useState(false);
  const [count, setCount] = useState(0);

  useQuery({
    queryKey: ["likes", "article", landmarkId],
    queryFn: async () => {
      if (!token) return null;
      const response = await api.get("/likes/status", {
        params: { target_type: "article", ids: String(landmarkId) },
      });
      const ids = (response.data.liked_ids || []) as number[];
      setLiked(ids.includes(landmarkId));
      return ids;
    },
    enabled: !!token,
  });

  return (
    <button
      type="button"
      data-testid="article-like"
      aria-pressed={liked}
      onClick={async () => {
        if (!token) {
          toast.error("登录后才能点赞");
          window.dispatchEvent(new CustomEvent("ts:open-login"));
          return;
        }
        try {
          const response = await api.post("/likes/", {
            target_type: "article",
            target_id: landmarkId,
          });
          setLiked(response.data.liked);
          setCount(response.data.count);
        } catch (error) {
          toast.error(errMessage(error, "操作失败"));
        }
      }}
      className={`flex items-center gap-1 rounded-lg border px-2.5 py-1 text-[11px] transition ${
        liked
          ? "border-rose-400/60 bg-rose-400/10 text-rose-500"
          : "border-border bg-card hover:border-rose-400/40 hover:text-rose-400"
      }`}
    >
      <Heart className={`h-3.5 w-3.5 ${liked ? "fill-rose-400 text-rose-400" : ""}`} />
      {count > 0 ? count : liked ? "已赞" : "赞"}
    </button>
  );
}
