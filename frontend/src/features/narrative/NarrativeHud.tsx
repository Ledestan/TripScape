/**
 * 行旅识景 TripScape / 叙事层总控
 * 创建日期: 2026-11-25
 *
 * 把三层叙事收成「一个档案浮窗」，完成:
 *     1. 地球层不常驻任何叙事 UI（入口就是点地标）
 *     2. 地标层：右侧居中的故事档案，可关闭、可切手记、可开评论/写手账
 *     3. 手账层：右侧居中的旅行手记，同样自带关闭，不依赖顶部返回
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
 */

import { useEffect, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { api, errMessage } from "@/api/client";
import { globeBus } from "@/features/globe/bus";
import { useAuthStore } from "@/stores/auth";
import { useNarrativeStore } from "@/stores/narrative";
import FavoritesPanel, { FavoriteItem } from "./FavoritesPanel";
import FootprintWindow from "./FootprintWindow";
import LandmarkNarrativePanel from "./LandmarkNarrativePanel";
import type {
  JournalEntry,
  LandmarkStoryData,
  NarrativeCardData,
  PickedFragment,
} from "./types";

export default function NarrativeHud() {
  const layer = useNarrativeStore((s) => s.layer);
  const landmarkId = useNarrativeStore((s) => s.landmarkId);
  const landmarkName = useNarrativeStore((s) => s.landmarkName);
  const enterLandmark = useNarrativeStore((s) => s.enterLandmark);
  const showJournal = useNarrativeStore((s) => s.showJournal);
  const back = useNarrativeStore((s) => s.back);
  const token = useAuthStore((s) => s.token);
  const qc = useQueryClient();

  // 档案/手记浮窗压在地球上时停掉自转：省 GPU，也不会隔着面板看见地球在转
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

  /** 头像菜单的「旅行手记」通过事件唤起手记层，避免把层状态散到多个组件 */
  useEffect(() => {
    const onOpenJournal = () => showJournal();
    const onOpenFootprints = () => setFootprintsOpen(true);
    window.addEventListener("ts:open-journal", onOpenJournal);
    window.addEventListener("ts:open-footprints", onOpenFootprints);
    return () => {
      window.removeEventListener("ts:open-journal", onOpenJournal);
      window.removeEventListener("ts:open-footprints", onOpenFootprints);
    };
  }, [showJournal]);

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

  /** 收藏列表来自个人主页聚合接口（只读，已按收藏时间倒序） */
  const { data: profile } = useQuery({
    queryKey: ["profile"],
    queryFn: async () => (await api.get("/auth/profile")).data as { favorites?: FavoriteItem[] },
    enabled: !!token,
    retry: 0,
  });
  const favorites = profile?.favorites || [];

  const [footprintsOpen, setFootprintsOpen] = useState(false);

  /** 收藏开关：与「收藏」按钮同源，收藏后可在手记里找到 */
  const toggleFavorite = useMutation({
    mutationFn: async (lmId: number) => api.post(`/landmarks/${lmId}/favorite`),
    onSuccess: (r) => {
      const favorited = (r.data as { favorited?: boolean } | undefined)?.favorited;
      toast.success(favorited === false ? "已取消收藏" : "已收藏", {
        description: favorited === false ? undefined : "可以在「手记」里找到它",
      });
      qc.invalidateQueries({ queryKey: ["profile"] });
    },
    onError: (e) => toast.error(errMessage(e, "收藏失败")),
  });

  const deliver = useMutation({
    mutationFn: async (payload: { card_id: number; landmark_id: number }) =>
      api.post("/narrative/fragments", payload),
    onSuccess: (r) => {
      const data = r.data?.data as { remaining?: number } | undefined;
      toast.success("这段叙事已匿名留在原地", {
        description:
          data?.remaining === undefined ? undefined : `该地标还剩 ${data.remaining} 个投递名额`,
      });
    },
    onError: (e) => toast.error(errMessage(e, "投递失败")),
  });

  const pick = useMutation({
    mutationFn: async (lmId: number) =>
      (await api.get("/narrative/fragments/pick", { params: { landmark_id: lmId } }))
        .data.data as PickedFragment,
    onSuccess: () => toast.success("有一条叙事漂流到这里"),
    onError: (e) => toast.error(errMessage(e, "这里暂时没有可拾取的碎片")),
  });

  /** 打开评论/收藏/写手账：复用原有浮窗，每个浮窗自带关闭按钮 */
  const openLegacyWindow = (event: string) => {
    if (!landmarkId) return;
    window.dispatchEvent(new CustomEvent(event, { detail: landmarkId }));
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
            journalCount={favorites.length}
            onBack={back}
            onOpenJournal={showJournal}
            picking={pick.isPending}
            onPick={() => {
              if (requireLogin("拾取碎片")) pick.mutate(landmarkId);
            }}
            delivering={deliver.isPending}
            onDeliver={(cardId) => {
              if (requireLogin("投递碎片")) {
                deliver.mutate({ card_id: cardId, landmark_id: landmarkId });
              }
            }}
            onOpenComments={() => openLegacyWindow("ts:open-landmark-window")}
            onOpenJournalEditor={() => {
              if (requireLogin("写手账")) openLegacyWindow("ts:open-journal-edit");
            }}
            favorited={favorites.some((f) => f.id === landmarkId)}
            favoriteBusy={toggleFavorite.isPending}
            onToggleFavorite={() => {
              if (landmarkId !== null && requireLogin("收藏")) toggleFavorite.mutate(landmarkId);
            }}
            onOpenFootprints={() => setFootprintsOpen(true)}
          />
        </div>
      )}

      <FootprintWindow
        open={footprintsOpen}
        onClose={() => setFootprintsOpen(false)}
        onLocate={(id, name) => {
          setFootprintsOpen(false);
          enterLandmark(id, name);
        }}
      />

      {layer === "journal" && (
        <div className="pointer-events-auto absolute right-3 top-1/2 z-30 w-[min(430px,calc(100vw-24px))] -translate-y-1/2">
          <FavoritesPanel
            items={favorites}
            removing={toggleFavorite.isPending}
            onClose={back}
            onOpen={(id, name) => enterLandmark(id, name)}
            onRemove={(id) => {
              if (requireLogin("取消收藏")) toggleFavorite.mutate(id);
            }}
          />
        </div>
      )}
    </div>
  );
}
