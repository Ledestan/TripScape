/**
 * 行旅识景 TripScape / 叙事层总控
 * 创建日期: 2026-11-25
 *
 * 把「空间叙事」从一条独立底栏改成融进界面的三处落点，完成:
 *     1. 地球层：左上角「故事胶片」，不遮挡地球与消息栏
 *     2. 地标层：右侧叙事档案面板，世界仍可见可点
 *     3. 手账层：右侧旅行手记抽屉，由头像菜单或面板按钮唤起
 *
 * 依赖:
 *     依赖库: @tanstack/react-query, zustand, sonner, lucide-react
 *
 * 用法:
 *     <NarrativeHud />    # 由 pages/GlobeApp.tsx 单点挂载
 *
 * 注意:
 *     1. 层状态储存在 stores/narrative.ts，本组件只负责呈现，不复制状态。
 *     2. 面板上的文案只描述后端字段（纪年/章节/置信度），不新增历史解释。
 */

import { useEffect, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { ArrowLeft, BookOpen, Compass, Layers } from "lucide-react";

import { api, errMessage } from "@/api/client";
import { useAuthStore } from "@/stores/auth";
import { useNarrativeStore } from "@/stores/narrative";
import { Button } from "@/components/ui/button";
import { cn } from "@/utils/cn";

import JournalCardsPanel from "./JournalCardsPanel";
import LandmarkNarrativePanel from "./LandmarkNarrativePanel";
import StoryStrip from "./StoryStrip";
import type {
  JournalEntry,
  NarrativeCardData,
  NarrativeSpot,
  PickedFragment,
} from "./types";

/** 三个层的中文名（用于面包屑，复用 store 的三值枚举） */
const LAYER_LABEL = {
  globe: "地球层",
  landmark: "地标层",
  journal: "手账层",
} as const;

export default function NarrativeHud() {
  const layer = useNarrativeStore((s) => s.layer);
  const landmarkId = useNarrativeStore((s) => s.landmarkId);
  const landmarkName = useNarrativeStore((s) => s.landmarkName);
  const enterLandmark = useNarrativeStore((s) => s.enterLandmark);
  const showJournal = useNarrativeStore((s) => s.showJournal);
  const back = useNarrativeStore((s) => s.back);
  const token = useAuthStore((s) => s.token);
  const qc = useQueryClient();
  const [picked, setPicked] = useState<PickedFragment | null>(null);

  const { data: spots } = useQuery({
    queryKey: ["landmarks", "spots"],
    queryFn: async () => (await api.get("/landmarks/spots")).data.data as NarrativeSpot[],
    staleTime: 60_000,
  });

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

  const { data: journal = [] } = useQuery({
    queryKey: ["narrative", "journal"],
    queryFn: async () => (await api.get("/narrative/journal")).data.data as JournalEntry[],
    enabled: !!token,
    retry: 0,
  });

  // 头像菜单里的「旅行手记」通过事件唤起手账层，避免层状态散落在多个组件
  useEffect(() => {
    const onOpenJournal = () => showJournal();
    window.addEventListener("ts:open-journal", onOpenJournal);
    return () => window.removeEventListener("ts:open-journal", onOpenJournal);
  }, [showJournal]);

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
      qc.invalidateQueries({ queryKey: ["narrative", "fragments"] });
    },
    onError: (e) => toast.error(errMessage(e, "投递失败")),
  });

  const pick = useMutation({
    mutationFn: async (lmId: number) =>
      (await api.get("/narrative/fragments/pick", { params: { landmark_id: lmId } }))
        .data.data as PickedFragment,
    onSuccess: (frag) => {
      setPicked(frag);
      toast.success("有一条叙事漂流到这里");
    },
    onError: (e) => toast.error(errMessage(e, "这里暂时没有可拾取的碎片")),
  });

  return (
    <div data-testid="narrative-hud" className="pointer-events-none absolute inset-0 z-30">
      {/* 层状态（无障碍与 e2e 的锚点，不参与视觉） */}
      <span data-testid="narrative-layer-indicator" className="sr-only">
        {layer}
      </span>

      {/* ① 地球层：左上角故事胶片，压在 logo 与搜索之下，不与它们抢位 */}
      {layer === "globe" && (
        <div
          data-testid="narrative-layer-globe"
          className="pointer-events-auto absolute z-20 flex flex-col gap-2"
          style={{
            left: "var(--ui-pad)",
            top: "calc(var(--ui-pad) + 150px)",
            width: "min(520px, 46vw)",
          }}
        >
          <StoryStrip
            spots={spots || []}
            onEnter={(spot) => enterLandmark(spot.id, spot.name)}
            journalCount={journal.length}
            onOpenJournal={showJournal}
          />
        </div>
      )}

      {/* 层内浮层共用一条顶部导航（面包屑 + 返回 + 手记）；地球层只留层名与手记入口 */}
      <div className="pointer-events-auto absolute inset-x-0 top-0 z-40 flex justify-center">
          <div
            className="mt-3 flex items-center gap-1 rounded-full border border-border/70 bg-card/90 px-2 py-1 shadow-[0_8px_28px_-12px_rgb(0_0_0/0.5)] backdrop-blur-md"
            style={{ marginTop: "calc(var(--ui-pad) - 6px)" }}
          >
            <span className="flex items-center gap-1.5 pl-1 pr-2 text-[11px] font-semibold tracking-wide text-foreground">
              <Layers className="h-3.5 w-3.5 text-primary" />
              {LAYER_LABEL[layer]}
            </span>
            <span className="h-4 w-px bg-border/70" />
            {layer !== "globe" && (
              <button
                data-testid="narrative-back"
                onClick={back}
                className="flex items-center gap-1 rounded-full px-2 py-1 text-[11px] text-muted-foreground transition hover:bg-accent hover:text-foreground"
              >
                <ArrowLeft className="h-3.5 w-3.5" />
                返回
              </button>
            )}
            <button
              data-testid="narrative-open-journal"
              onClick={showJournal}
              className={cn(
                "flex items-center gap-1 rounded-full px-2 py-1 text-[11px] transition",
                layer === "journal"
                  ? "bg-primary text-primary-foreground"
                  : "text-muted-foreground hover:bg-accent hover:text-foreground"
              )}
            >
              <BookOpen className="h-3.5 w-3.5" />
              旅行手记
              <span
                data-testid="narrative-journal-count"
                className="rounded-full bg-primary/15 px-1.5 text-[10px] font-bold text-primary"
              >
                {journal.length}
              </span>
            </button>
          </div>
        </div>

      {/* ② 地标层：右侧叙事档案 */}
      {layer === "landmark" && landmarkId !== null && (
        <div className="pointer-events-auto absolute bottom-[116px] right-[var(--ui-pad)] top-[calc(var(--ui-pad)+44px)] z-30 w-[min(420px,92vw)]">
          <LandmarkNarrativePanel
            card={card}
            loading={cardLoading}
            failed={cardFailed}
            errorText={cardError instanceof Error ? cardError.message : ""}
            onRetry={() => refetchCard()}
            landmarkName={landmarkName}
            adding={addToJournal.isPending}
            onAdd={() => card && addToJournal.mutate(card.id)}
            picking={pick.isPending}
            onPick={() => pick.mutate(landmarkId)}
            picked={picked}
            delivering={deliver.isPending}
            onDeliver={(cardId) => deliver.mutate({ card_id: cardId, landmark_id: landmarkId })}
          />
        </div>
      )}

      {/* ③ 手账层：右侧旅行手记抽屉 */}
      {layer === "journal" && (
        <div className="pointer-events-auto absolute bottom-[116px] right-[var(--ui-pad)] top-[calc(var(--ui-pad)+44px)] z-30 w-[min(420px,92vw)]">
          <JournalCardsPanel
            entries={journal}
            delivering={deliver.isPending}
            onDeliver={(cardId, lmId) => deliver.mutate({ card_id: cardId, landmark_id: lmId })}
            onWake={(lmId, name) => enterLandmark(lmId, name)}
            onPickHere={() => landmarkId !== null && pick.mutate(landmarkId)}
            canPick={landmarkId !== null}
          />
        </div>
      )}

      {/* 地球层左下角：一句提示，替代原来的整条底栏 */}
      {layer === "globe" && (
        <div
          className="pointer-events-none absolute left-0 z-10 flex items-center gap-1.5 text-[11px] text-muted-foreground"
          style={{ bottom: "calc(var(--ui-pad) + 108px)", paddingLeft: "var(--ui-pad)" }}
        >
          <Compass className="h-3.5 w-3.5" />
          点一个地标，读它被讲述的那一段
        </div>
      )}

      {/* 地标层的快捷入口：手记里还没收下这段叙事时的引导（不遮挡面板） */}
      {layer === "landmark" && (
        <Button
          size="sm"
          variant="ghost"
          className="pointer-events-auto absolute z-30 text-[11px] text-muted-foreground hover:text-foreground"
          style={{ right: "calc(var(--ui-pad) + 4px)", bottom: "calc(var(--ui-pad) + 76px)" }}
          onClick={showJournal}
        >
          <BookOpen className="mr-1 h-3.5 w-3.5" />
          看看手记
        </Button>
      )}
    </div>
  );
}
