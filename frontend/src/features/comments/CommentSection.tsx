/**
 * 行旅识景 TripScape / 评论树
 * 创建日期: 2026-11-26
 *
 * 一份评论组件，地标与手账共用，完成:
 *     1. 一级评论 + 任意层级回复（后端返回树，这里递归渲染）
 *     2. 发表、回复（回复的回复也能回）、修改、删除自己的评论
 *     3. 给评论点赞，登录校验统一走 ts:open-login
 *
 * 依赖:
 *     依赖库: @tanstack/react-query, lucide-react, sonner
 *
 * 用法:
 *     <CommentSection landmarkId={landmarkId} />
 *     <CommentSection journalId={journalId} />
 *
 * 注意:
 *     1. 传 landmarkId 或 journalId，二选一；接口分别是 /comments/landmark/{id} 与 /comments/journal/{id}。
 *     2. 缩进最多 3 层，更深的回复继续显示在同一缩进，避免右侧被挤没。
 */

import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Heart, Send } from "lucide-react";
import { toast } from "sonner";

import { api, errMessage } from "@/api/client";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { useAuthStore } from "@/stores/auth";

export interface CommentNode {
  id: number;
  user: { id: number; nickname: string; avatar: string };
  parent_id: number | null;
  content: string;
  created_at: string;
  replies?: CommentNode[];
}

const MAX_DEPTH = 3;

export default function CommentSection({
  landmarkId,
  journalId,
}: {
  landmarkId?: number;
  journalId?: number;
}) {
  const token = useAuthStore((s) => s.token);
  const me = useAuthStore((s) => s.user);
  const qc = useQueryClient();
  const [text, setText] = useState("");
  const [replyTo, setReplyTo] = useState<CommentNode | null>(null);
  const [editing, setEditing] = useState<number | null>(null);
  const [editText, setEditText] = useState("");

  const path = landmarkId
    ? `/comments/landmark/${landmarkId}`
    : `/comments/journal/${journalId}`;

  const { data: comments, refetch } = useQuery({
    queryKey: ["comments", landmarkId ? "landmark" : "journal", landmarkId ?? journalId],
    queryFn: async () => (await api.get(path)).data.data as CommentNode[],
    enabled: !!landmarkId || !!journalId,
  });

  const requireLogin = (): boolean => {
    if (token) return true;
    toast.error("登录后才能评论");
    window.dispatchEvent(new CustomEvent("ts:open-login"));
    return false;
  };

  const submit = useMutation({
    mutationFn: async () => {
      const target = landmarkId ? { landmark_id: landmarkId } : { journal_id: journalId };
      return api.post("/comments/", {
        ...target,
        content: text,
        ...(replyTo ? { parent_id: replyTo.id } : {}),
      });
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
      api.put(`/comments/${id}`, { content: editText }),
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

  const count = (nodes?: CommentNode[]): number =>
    (nodes || []).reduce((sum, node) => sum + 1 + count(node.replies), 0);

  const renderNode = (node: CommentNode, depth = 0) => {
    const mine = me?.id === node.user.id;
    return (
      <div key={node.id} className={depth > 0 ? "mt-2" : "mt-3"} data-testid={depth > 0 ? "comment-reply" : "comment-item"}>
        <div className="flex items-start gap-2">
          <img src={node.user.avatar} alt="" className="h-6 w-6 rounded-full object-cover" />
          <div className="min-w-0 flex-1">
            <div className="flex items-center gap-1.5 text-[11px] text-muted-foreground">
              <span className="font-medium text-foreground">{node.user.nickname}</span>
              <span>{new Date(node.created_at).toLocaleDateString("zh-CN")}</span>
            </div>

            {editing === node.id ? (
              <div className="mt-1 space-y-1">
                <Textarea
                  value={editText}
                  onChange={(event) => setEditText(event.target.value)}
                  rows={2}
                  className="text-[12px]"
                />
                <div className="flex gap-1.5">
                  <Button size="sm" className="h-6 text-[11px]" onClick={() => updateComment.mutate(node.id)}>
                    保存
                  </Button>
                  <Button size="sm" variant="ghost" className="h-6 text-[11px]" onClick={() => setEditing(null)}>
                    取消
                  </Button>
                </div>
              </div>
            ) : (
              <p className="mt-0.5 whitespace-pre-wrap text-[12px] leading-relaxed text-foreground/85">
                {node.content}
              </p>
            )}

            <div className="mt-1 flex items-center gap-2 text-[10.5px] text-muted-foreground">
              <button
                type="button"
                className="flex items-center gap-0.5 hover:text-rose-500"
                onClick={async () => {
                  if (!requireLogin()) return;
                  try {
                    await api.post("/likes/", { target_type: "comment", target_id: node.id });
                    refetch();
                  } catch (error) {
                    toast.error(errMessage(error, "操作失败"));
                  }
                }}
              >
                <Heart className="h-3 w-3" />
                赞
              </button>
              <button
                type="button"
                className="hover:text-primary"
                onClick={() => {
                  if (!requireLogin()) return;
                  setReplyTo(node);
                }}
              >
                回复
              </button>
              {mine && (
                <>
                  <button
                    type="button"
                    className="hover:text-primary"
                    onClick={() => {
                      setEditing(node.id);
                      setEditText(node.content);
                    }}
                  >
                    修改
                  </button>
                  <button
                    type="button"
                    className="hover:text-destructive"
                    onClick={() => deleteComment.mutate(node.id)}
                  >
                    删除
                  </button>
                </>
              )}
            </div>
          </div>
        </div>

        {node.replies?.length ? (
          <div className={depth < MAX_DEPTH ? "ml-5 border-l border-border/50 pl-2" : "ml-2"}>
            {node.replies.map((reply) => renderNode(reply, depth + 1))}
          </div>
        ) : null}
      </div>
    );
  };

  return (
    <div className="space-y-2">
      <div className="flex items-center justify-between text-[11px] text-muted-foreground">
        <span>评论 {count(comments)}</span>
        {replyTo && (
          <button
            type="button"
            className="text-primary hover:underline"
            onClick={() => setReplyTo(null)}
          >
            取消回复 @{replyTo.user.nickname}
          </button>
        )}
      </div>

      <div className="flex items-start gap-2">
        <Textarea
          value={text}
          onChange={(event) => setText(event.target.value)}
          rows={2}
          data-testid="comment-input"
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

      <div className="max-h-[36vh] overflow-y-auto pr-1">
        {comments?.length ? (
          comments.map((node) => renderNode(node))
        ) : (
          <p className="py-4 text-center text-[11px] text-muted-foreground">
            还没有评论，来写第一条。
          </p>
        )}
      </div>
    </div>
  );
}
