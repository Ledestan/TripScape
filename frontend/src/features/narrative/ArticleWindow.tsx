/**
 * 行旅识景 TripScape / 文章详情页
 *
 * 地标文章的独立阅读页（从档案面板"查看全文"打开），完成:
 *     1. 全文阅读：整体介绍、时间轴、全部分节（不折叠）
 *     2. 点赞：target_type=article，target_id=地标 id
 *     3. 评论：复用 CommentSection（一级 + 任意层级回复、改、删、点赞）
 *
 * 依赖:
 *     依赖库: @tanstack/react-query, lucide-react, sonner
 *
 * 用法:
 *     <ArticleWindow landmarkId={id} onClose={() => setOpen(false)} />
 *
 * 注意:
 *     评论与地标详情页是同一份数据（/comments/landmark/{id}），
 *     在文章页回复后，详情页的评论树也会一起更新。
 */

import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Heart } from "lucide-react";
import { toast } from "sonner";

import { api, errMessage } from "@/api/client";
import { FloatingWindow } from "@/components/FloatingWindow";
import CommentSection from "@/features/comments/CommentSection";
import LandmarkStoryView from "@/features/narrative/LandmarkStoryView";
import type { LandmarkStoryData } from "@/features/narrative/types";
import { useAuthStore } from "@/stores/auth";

export default function ArticleWindow({
  landmarkId,
  title,
  onClose,
}: {
  landmarkId: number;
  title?: string;
  onClose: () => void;
}) {
  const { data: story } = useQuery({
    queryKey: ["narrative", "story", landmarkId, "article"],
    queryFn: async () =>
      (await api.get(`/narrative/story/${landmarkId}`)).data.data as LandmarkStoryData,
  });

  const articleTitle = title || story?.title || "文章";

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
            <span className="text-[11px] text-muted-foreground">读完可以点个赞</span>
          </div>

          <article className="max-h-[40vh] overflow-y-auto pr-1">
            <LandmarkStoryView story={story} expanded />
          </article>

          <div className="border-t border-border/60 pt-3">
            <CommentSection landmarkId={landmarkId} />
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