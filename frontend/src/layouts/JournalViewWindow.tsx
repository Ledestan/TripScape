import { useEffect, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { toast } from "sonner";
import { Flag, Heart } from "lucide-react";

import { api, errMessage } from "@/api/client";
import { useAuthStore } from "@/stores/auth";
import { FloatingWindow } from "@/components/FloatingWindow";
import ReportDialog from "@/features/comments/ReportDialog";

/* ================================================================== */
/* 手账查看浮窗（个人主页/详情页/搜索结果点手账弹出；含点赞与举报）       */
/* ================================================================== */
export function JournalViewWindow({ journalId, onClose }: { journalId: number; onClose: () => void }) {
  const [reportOpen, setReportOpen] = useState(false);
  const me = useAuthStore.getState()?.user;
  const { data: j } = useQuery({
    queryKey: ["journal", journalId],
    queryFn: async () =>
      (
        await api.get(`/journals/${journalId}`)
      ).data.data as {
        user: { nickname: string; avatar: string };
        landmark: { name: string };
        title: string;
        content: string;
        images: string[];
        visited_at: string | null;
        created_at: string;
      },
  });

  return (
    <FloatingWindow open onClose={onClose} title={j ? `${j.title} · 手账` : "手账"} width={480} maxHeight="72vh">
      {!j ? (
        <div className="py-10 text-center text-sm text-muted-foreground">加载中…</div>
      ) : (
        <>
          <div className="flex flex-wrap items-center gap-2 text-xs text-muted-foreground">
            <span className="font-medium text-foreground">{j.user.nickname}</span>
            <span>@ {j.landmark.name}</span>
            <span>{j.visited_at || new Date(j.created_at).toLocaleDateString("zh-CN")}</span>
          </div>
          {j.images?.length > 0 && (
            <div className="mt-3 grid grid-cols-2 gap-2">
              {j.images.slice(0, 6).map((u, i) => (
                <img key={i} src={u} alt="" className="h-36 w-full rounded-xl object-cover" />
              ))}
            </div>
          )}
          <div className="mt-3 whitespace-pre-wrap text-sm leading-relaxed">{j.content || "（作者没有留下文字）"}</div>

          <div className="mt-3 flex items-center gap-2">
            <LikeButton targetType="journal" targetId={journalId} />
            {j.user.nickname !== me?.nickname && <ReportButton onClick={() => setReportOpen(true)} />}
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
}: {
  targetType: "journal" | "comment";
  targetId: number;
  count?: number;
}) {
  const [liked, setLiked] = useState(false);
  const [n, setN] = useState(count);

  useEffect(() => {
    let alive = true;
    const tk = JSON.parse(localStorage.getItem("tripscape-auth") || "{}").state;
    if (tk?.token) {
      api
        .get("/likes/status", { params: { target_type: targetType, ids: String(targetId) } })
        .then((r) => {
          if (alive) setLiked((r.data.liked_ids || []).includes(targetId));
        })
        .catch(() => {});
    }
    return () => {
      alive = false;
    };
  }, [targetType, targetId]);

  const toggle = async () => {
    const tk = JSON.parse(localStorage.getItem("tripscape-auth") || "{}").state;
    if (!tk?.token) {
      toast.error("登录后才能点赞");
      return;
    }
    try {
      const r = await api.post("/likes/", { target_type: targetType, target_id: targetId });
      setLiked(r.data.liked);
      setN(r.data.count);
    } catch (e) {
      toast.error(errMessage(e, "操作失败"));
    }
  };

  return (
    <button
      onClick={toggle}
      className={`flex items-center gap-1 rounded-lg border px-2.5 py-1 text-xs transition ${
        liked
          ? "border-rose-400/60 bg-rose-400/10 text-rose-500"
          : "border-border bg-card hover:border-rose-400/40 hover:text-rose-400"
      }`}
      title={liked ? "取消点赞" : "点赞"}
    >
      <Heart className={`h-3.5 w-3.5 ${liked ? "fill-rose-400 text-rose-400" : ""}`} />
      {n > 0 ? n : "赞"}
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
