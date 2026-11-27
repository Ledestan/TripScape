/**
 * 行旅识景 TripScape / src/pages/LandmarkDetail
 *
 * 地标详情窗：介绍、时间轴、评论与手账页签。
 */

import { useEffect, useState } from "react";
import { MapPin, Eye, Star, Send, Flag, NotebookPen, MessageSquare } from "lucide-react";

import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { api, errMessage } from "@/api/client";
import { useAuthStore } from "@/stores/auth";
import { globeBus } from "@/features/globe/bus";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { FloatingWindow } from "@/components/FloatingWindow";
import ReportDialog from "@/features/comments/ReportDialog";
import { lazy, Suspense } from "react";
import CommentSection from "@/features/comments/CommentSection";

const CanvasThumb = lazy(() => import("@/features/narrative/JournalCanvasView"));

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

  initialTab = "comments",

}: {

  landmarkId: number;

  onClose: () => void;

  onWriteJournal: (landmarkId: number) => void;

  /** 从档案的「评论 / 手账」进入时指定页签 */
  initialTab?: "comments" | "journals";

}) {

  const [tab, setTab] = useState<"comments" | "journals">(initialTab);

  const { token } = useAuthStore();

  const [viewJournal, setViewJournal] = useState<number | null>(null);

  const [reportTarget, setReportTarget] = useState<{ type: "comment" | "journal"; id: number } | null>(null);

  const qc = useQueryClient();

  const { data: lm, refetch: refetchLandmark } = useQuery({

    queryKey: ["landmark", landmarkId],

    queryFn: async () => (await api.get(`/landmarks/${landmarkId}`)).data.data,

    enabled: !!landmarkId,

  });

  // 登录/退出后要重取：favorited / 点赞态是"按当前用户"算的，
  // 浮窗在匿名态先打开时，不重取就会一直显示成未收藏。
  useEffect(() => {
    if (landmarkId) refetchLandmark();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [token, landmarkId]);

  const { data: comments } = useQuery({

    queryKey: ["comments", landmarkId],

    queryFn: async () => (await api.get(`/comments/landmark/${landmarkId}`)).data.data as Comment[],

    enabled: !!landmarkId,

  });

  const { data: journals } = useQuery({

    queryKey: ["journals", "landmark", landmarkId],

    queryFn: async () => (await api.get(`/journals/landmark/${landmarkId}`)).data.data,

    enabled: !!landmarkId,

  });

  // 收藏状态：直接用详情接口返回的 favorited（之前靠个人主页前 50 条收藏推断，
  // 收藏多了会误显示成"未收藏"；这里也不再额外请求 /auth/profile）
  const [favorited, setFavorited] = useState(false);

  useEffect(() => {
    if (lm && typeof lm.favorited === "boolean") setFavorited(lm.favorited);
  }, [lm?.favorited, lm?.id]);

  const fav = useMutation({

    // 显式目标状态：双击/重试不会把收藏状态来回翻转

    mutationFn: async () =>

      api.post(`/landmarks/${landmarkId}/favorite`, null, {
        params: { favorited: !favorited },
      }),

    onSuccess: (r) => {

      setFavorited(!!r.data.favorited);

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

      testId="landmark-detail-window"

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

                data-testid={`detail-tab-${t}`}

                data-active={tab === t}

                onClick={() => setTab(t)}

                className={`rounded-lg py-1.5 text-sm font-medium transition ${

                  tab === t ? "bg-background shadow" : "text-muted-foreground hover:text-foreground"

                }`}

              >

                {t === "comments" ? `评论（${comments?.length ?? 0}）` : `手账（${journals?.length ?? 0}）`}

              </button>

            ))}

          </div>

          {/* 评论 Tab：一级 + 任意层级回复，统一用 CommentSection */}
          {tab === "comments" && (
            <div className="mt-3">
              <CommentSection landmarkId={landmarkId} />
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

                    {j.canvas?.elements?.length ? (
                      <div className="h-28 w-full overflow-hidden rounded-t-xl bg-muted"><Suspense fallback={null}><CanvasThumb canvas={j.canvas} /></Suspense></div>
                    ) : j.images?.[0] ? (
                      <img src={j.images[0]} alt="" className="h-28 w-full rounded-t-xl object-cover" />
                    ) : null}

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
