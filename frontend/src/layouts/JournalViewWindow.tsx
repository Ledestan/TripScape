/**
 * 行旅识景 TripScape / src/layouts/JournalViewWindow
 *
 * 手账查看窗：画布/图片渲染、点赞、评论与作者修改入口。
 */

import { Suspense, lazy, useEffect, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { toast } from "sonner";
import { Flag, Heart, Pencil } from "lucide-react";
import { api, errMessage } from "@/api/client";
import { useAuthStore } from "@/stores/auth";
import { FloatingWindow } from "@/components/FloatingWindow";
import ReportDialog from "@/features/comments/ReportDialog";
import CommentSection from "@/features/comments/CommentSection";
import { SkeletonRows } from "@/components/ui/skeleton";

// 画布渲染带 konva，只在真的打开带画布的手账时才加载
const JournalCanvasView = lazy(() => import("@/features/narrative/JournalCanvasView"));

/* ================================================================== */
/* 手账查看浮窗（个人主页/详情页/搜索结果点手账弹出；含点赞与举报）       */
/* ================================================================== */
export function JournalViewWindow({ journalId, onClose }: { journalId: number; onClose: () => void }) {
  const [reportOpen, setReportOpen] = useState(false);
  // 必须订阅 store：getState() 只在渲染那一刻取值，登录/退出后按钮不会更新
  const me = useAuthStore((s) => s.user);
  const token = useAuthStore((s) => s.token);
  const { data: j, refetch: refetchJournal } = useQuery({
    queryKey: ["journal", journalId],
    queryFn: async () =>
      (
        await api.get(`/journals/${journalId}`)
      ).data.data as {
        user: { id: number; nickname: string; avatar: string };
        landmark: { name: string };
        title: string;
        content: string;
        images: string[];
        canvas?: unknown;
        visited_at: string | null;
        created_at: string;
        like_count?: number;
        liked?: boolean;
      },
  });

  // 登录/退出后重取：liked 是按当前用户算的，不重取会显示错误的已赞状态
  useEffect(() => {
    refetchJournal();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [token, journalId]);

  // 有画布就优先展示画布；老手账没有画布时退回图片九宫格
  const hasCanvas =
    !!j?.canvas &&
    Array.isArray((j.canvas as { elements?: unknown[] }).elements) &&
    ((j.canvas as { elements: unknown[] }).elements.length > 0);

  return (
    <FloatingWindow open onClose={onClose} title={j ? `${j.title} · 手账` : "手账"} width={480} maxHeight="80vh">
      {!j ? (
        <SkeletonRows rows={3} className="py-6" />
      ) : (
        <>
          <div className="flex flex-wrap items-center gap-2 text-xs text-muted-foreground">
            <span className="font-medium text-foreground">{j.user.nickname}</span>
            <span>@ {j.landmark.name}</span>
            <span>{j.visited_at || new Date(j.created_at).toLocaleDateString("zh-CN")}</span>
          </div>
          {hasCanvas && (
            <div className="mt-3">
              <Suspense fallback={null}>
                <JournalCanvasView canvas={j.canvas} />
              </Suspense>
            </div>
          )}
          {!hasCanvas && j.images?.length > 0 && (
            <div className="mt-3 grid grid-cols-2 gap-2">
              {j.images.slice(0, 6).map((u, i) => (
                <img key={i} src={u} alt="" className="h-36 w-full rounded-xl object-cover" />
              ))}
            </div>
          )}
          {j.content?.trim() ? (
            <div className="mt-3 whitespace-pre-wrap text-sm leading-relaxed">{j.content}</div>
          ) : null}

          <div className="mt-3 border-t border-border/60 pt-3">
            <CommentSection journalId={journalId} />
          </div>

          <div className="mt-3 flex items-center gap-2">
            <LikeButton
              targetType="journal"
              targetId={journalId}
              count={j.like_count ?? 0}
              initialLiked={!!j.liked}
            />
            {me?.id === j.user.id && (
              <button
                type="button"
                data-testid="journal-edit"
                className="flex items-center gap-1 rounded-lg border border-border px-2.5 py-1 text-xs transition hover:border-primary/50 hover:text-primary"
                onClick={() => {
                  window.dispatchEvent(
                    new CustomEvent("ts:edit-journal", { detail: { journalId } })
                  );
                  onClose();
                }}
              >
                <Pencil className="h-3 w-3" /> 修改
              </button>
            )}
            {j.user.id !== me?.id && <ReportButton onClick={() => setReportOpen(true)} />}
          </div>

          {reportOpen && <ReportDialog targetType="journal" targetId={journalId} onClose={() => setReportOpen(false)} />}
        </>
      )}
    </FloatingWindow>
  );
}

/* ---------------- 点赞按钮（手账/评论通用；未登录提示） ---------------- */
export function LikeButton({
  targetType,
  targetId,
  count = 0,
  initialLiked,
}: {
  targetType: "journal" | "comment" | "article";
  targetId: number;
  count?: number;
  /** 父级已经从详情接口拿到"我是否点过"时传入，省一次请求 */
  initialLiked?: boolean;
}) {
  const token = useAuthStore((s) => s.token);
  const [liked, setLiked] = useState(!!initialLiked);
  const [n, setN] = useState(count);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    if (initialLiked !== undefined) {
      setLiked(!!initialLiked);
      setN(count);
      return;
    }
    let alive = true;
    // 只拿到 id 的场景：批量统计接口同时给"赞数"和"我点过没有"
    api
      .get("/likes/stats", { params: { target_type: targetType, ids: String(targetId) } })
      .then((r) => {
        if (!alive) return;
        setN(Number(r.data.counts?.[String(targetId)] || 0));
        setLiked((r.data.liked_ids || []).includes(targetId));
      })
      .catch(() => {});
    return () => {
      alive = false;
    };
  }, [targetType, targetId, token, initialLiked, count]);

  const toggle = async () => {
    if (busy) return;
    if (!token) {
      toast.error("登录后才能点赞");
      return;
    }
    const target = !liked;
    setBusy(true);
    // 乐观更新：网络慢时也有即时反馈；失败回滚
    setLiked(target);
    setN((value) => Math.max(0, value + (target ? 1 : -1)));
    try {
      const r = await api.post("/likes/", {
        target_type: targetType,
        target_id: targetId,
        // 显式目标状态：双击/重试不会把赞来回抵消
        liked: target,
      });
      setLiked(!!r.data.liked);
      setN(Number(r.data.count ?? 0));
    } catch (e) {
      setLiked(!target);
      setN((value) => Math.max(0, value + (target ? -1 : 1)));
      toast.error(errMessage(e, "操作失败"));
    } finally {
      setBusy(false);
    }
  };

  return (
    <button
      onClick={toggle}
      disabled={busy}
      data-testid="like-button"
      aria-pressed={liked}
      className={`flex items-center gap-1 rounded-lg border px-2.5 py-1 text-xs transition disabled:opacity-60 ${
        liked
          ? "border-rose-400/60 bg-rose-400/10 text-rose-500"
          : "border-border bg-card hover:border-rose-400/40 hover:text-rose-400"
      }`}
      title={liked ? "取消点赞" : "点赞"}
    >
      <Heart className={`h-3.5 w-3.5 ${liked ? "fill-rose-400 text-rose-400" : ""}`} />
      {n > 0 ? n : liked ? "已赞" : "赞"}
    </button>
  );
}

/* ---------------- 举报按钮 ---------------- */
function ReportButton({ onClick }: { onClick: () => void }) {
  return (
    <button
      onClick={onClick}
      className="flex items-center gap-1 rounded-lg border border-border px-2.5 py-1 text-xs text-destructive transition hover:bg-destructive/10"
    >
      <Flag className="h-3 w-3" /> 举报该手账
    </button>
  );
}