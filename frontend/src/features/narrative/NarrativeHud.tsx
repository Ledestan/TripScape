/**
 * 行旅识景 TripScape / 叙事层总控
 *
 * 地标层的档案浮窗，完成:
 *     1. 地球层不常驻任何叙事 UI（入口就是点地标）
 *     2. 地标层：右侧居中的故事档案，自带关闭
 *     3. 底部四个入口：评论 / 收藏 / 足迹 / 手账；评论与手账都进详情浮窗
 *
 * 依赖:
 *     依赖库: @tanstack/react-query, zustand, sonner, lucide-react
 *
 * 用法:
 *     <NarrativeHud />    # 由 pages/GlobeApp.tsx 单点挂载
 *
 * 注意:
 *     1. 层状态在 stores/narrative.ts；本组件只负责呈现与请求。
 *     2. 未登录执行写操作时先提示并打开登录浮窗，不发无意义的 401 请求。
 *     3. 评论/手账要"进入详情"而不是叠一个窗口：先按 tab 打开详情浮窗，
 *        再把档案层退回地球层，避免两层浮窗互相遮挡。
 */

import { useEffect, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { api, errMessage } from "@/api/client";
import { globeBus } from "@/features/globe/bus";
import { useAuthStore } from "@/stores/auth";
import { useNarrativeStore } from "@/stores/narrative";

import LandmarkNarrativePanel from "./LandmarkNarrativePanel";
import type { LandmarkStoryData, NarrativeCardData } from "./types";

export default function NarrativeHud() {
  const layer = useNarrativeStore((s) => s.layer);
  const landmarkId = useNarrativeStore((s) => s.landmarkId);
  const landmarkName = useNarrativeStore((s) => s.landmarkName);

  const back = useNarrativeStore((s) => s.back);
  const token = useAuthStore((s) => s.token);
  const qc = useQueryClient();


  // 档案浮窗压在地球上时停掉自转：省 GPU，也不会隔着面板看见地球在转
  useEffect(() => {
    globeBus.setOverlay(layer !== "globe");
    return () => globeBus.setOverlay(false);
  }, [layer]);

  /** 未登录时的统一出口：先提示再打开登录浮窗，不把 401 当业务错误抛给用户 */
  const requireLogin = (action: string): boolean => {
    if (token) return true;
    toast.error(`请先登录后再${action}`);
    window.dispatchEvent(new CustomEvent("ts:open-login"));
    return false;
  };

  const {
    data: card,
    isLoading: cardLoading,
    isError: cardFailed,
    error: cardError,
    refetch: refetchCard,
  } = useQuery({
    queryKey: ["narrative", "card", landmarkId],
    queryFn: async () =>
      (await api.get(`/narrative/card/${landmarkId}`)).data.data as NarrativeCardData,
    enabled: layer === "landmark" && landmarkId !== null,
    retry: 1,
  });

  const { data: story } = useQuery({
    queryKey: ["narrative", "story", landmarkId],
    queryFn: async () =>
      (await api.get(`/narrative/story/${landmarkId}`)).data.data as LandmarkStoryData,
    enabled: layer === "landmark" && landmarkId !== null,
    retry: 0,
  });

  /** 收藏状态直接取卡片响应里的 favorited（服务端按当前用户判断，
      不再依赖"个人主页前 50 条收藏"，收藏多了也不会误显示未收藏） */
  const favorited = Boolean((card as { favorited?: boolean } | undefined)?.favorited);

  // 登录/退出后重取卡片：否则匿名态先打开的档案，登录后仍显示"未收藏"
  useEffect(() => {
    if (landmarkId !== null) refetchCard();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [token, landmarkId]);

  const toggleFavorite = useMutation({
    // 显式目标状态：双击/重试不会把收藏状态来回翻转
    mutationFn: async (lmId: number) =>
      api.post(`/landmarks/${lmId}/favorite`, null, {
        params: { favorited: !favorited },
      }),
    onSuccess: (r) => {
      const now = (r.data as { favorited?: boolean } | undefined)?.favorited;
      toast.success(now === false ? "已取消收藏" : "已收藏");
      qc.invalidateQueries({ queryKey: ["profile"] });
      qc.invalidateQueries({ queryKey: ["narrative", "card", landmarkId] });
    },
    onError: (e) => toast.error(errMessage(e, "收藏失败")),
  });

  /** 进入详情浮窗：评论走评论页签，手账走手账页签；同时收起档案层 */
  const openDetail = (tab: "comments" | "journals") => {
    if (landmarkId === null) return;
    window.dispatchEvent(
      new CustomEvent("ts:open-landmark-window", { detail: { landmarkId, tab } })
    );
    back();
  };

  return (
    <div data-testid="narrative-hud" className="pointer-events-none absolute inset-0 z-20">
      {/* 层状态只做无障碍与测试锚点：地球层不渲染任何叙事 UI，入口就是点地标 */}
      <span data-testid="narrative-layer-indicator" className="sr-only">
        {layer}
      </span>

      {layer === "landmark" && landmarkId !== null && (
        <div
          data-testid="narrative-layer-landmark"
          className="pointer-events-auto absolute right-3 top-1/2 z-30 w-[min(430px,calc(100vw-24px))] -translate-y-1/2"
        >
          <LandmarkNarrativePanel
            card={card}
            loading={cardLoading}
            failed={cardFailed}
            errorText={cardError instanceof Error ? cardError.message : ""}
            onRetry={() => refetchCard()}
            landmarkName={landmarkName}
            story={story}
            onBack={back}
            onOpenComments={() => openDetail("comments")}
            onOpenArticle={() => {
              window.dispatchEvent(
                new CustomEvent("ts:open-article", { detail: { landmarkId, title: landmarkName } })
              );
            }}
            onOpenJournalEditor={() => {
              if (requireLogin("查看手账")) openDetail("journals");
            }}
            favorited={favorited}
            favoriteBusy={toggleFavorite.isPending}
            onToggleFavorite={() => {
              if (landmarkId !== null && requireLogin("收藏")) toggleFavorite.mutate(landmarkId);
            }}

          />
        </div>
      )}

      {/* 足迹已收进个人中心：档案里不再重复开窗 */}
    </div>
  );
}