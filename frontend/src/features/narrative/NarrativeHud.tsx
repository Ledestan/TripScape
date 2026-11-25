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

import { useEffect } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";

import { api, errMessage } from "@/api/client";
import { useAuthStore } from "@/stores/auth";
import { useNarrativeStore } from "@/stores/narrative";

import JournalCardsPanel from "./JournalCardsPanel";
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

  /** 未登录时的统一出口：先提示再打开登录浮窗，不把 401 当业务错误抛给用户 */
  const requireLogin = (action: string): boolean => {
    if (token) return true;
    toast.error(`请先登录后再${action}`, {
      description: "点右上角「登录」即可，登录后本页状态不会丢",
    });
    window.dispatchEvent(new CustomEvent("ts:open-login"));
    return false;
  };

  /** 头像菜单的「旅行手记」通过事件唤起手记层，避免把层状态散到多个组件 */
  useEffect(() => {
    const onOpenJournal = () => showJournal();
    window.addEventListener("ts:open-journal", onOpenJournal);
    return () => window.removeEventListener("ts:open-journal", onOpenJournal);
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

  const { data: journal = [] } = useQuery({
    queryKey: ["narrative", "journal"],
    queryFn: async () => (await api.get("/narrative/journal")).data.data as JournalEntry[],
    enabled: !!token,
    retry: 0,
  });

  const addToJournal = useMutation({
    mutationFn: async (cardId: number) =>
      api.post("/narrative/journal/cards", { card_id: cardId }),
    onSuccess: () => {
      toast.success("已收进手记", { description: "这段叙事以只读快照保留，刷新不会丢失" });
      qc.invalidateQueries({ queryKey: ["narrative", "journal"] });
    },
    onError: (e) => toast.error(errMessage(e, "收进手记失败")),
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
            journalCount={journal.length}
            onBack={back}
            onOpenJournal={showJournal}
            adding={addToJournal.isPending}
            onAdd={() => {
              if (card && requireLogin("收进手记")) addToJournal.mutate(card.id);
            }}
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
          />
        </div>
      )}

      {layer === "journal" && (
        <div className="pointer-events-auto absolute right-3 top-1/2 z-30 w-[min(430px,calc(100vw-24px))] -translate-y-1/2">
          <JournalCardsPanel
            entries={journal}
            delivering={deliver.isPending}
            onClose={back}
            onDeliver={(cardId, lmId) => {
              if (requireLogin("投递碎片")) {
                deliver.mutate({ card_id: cardId, landmark_id: lmId });
              }
            }}
            onWake={(lmId, name) => enterLandmark(lmId, name)}
            onPickHere={() => {
              if (landmarkId !== null && requireLogin("拾取碎片")) pick.mutate(landmarkId);
            }}
            canPick={landmarkId !== null}
          />
        </div>
      )}
    </div>
  );
}
