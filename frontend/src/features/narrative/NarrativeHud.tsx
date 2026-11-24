import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { ArrowLeft, BookOpen, Layers } from "lucide-react";

import { api, errMessage } from "@/api/client";
import { useAuthStore } from "@/stores/auth";
import { useFeatureFlag } from "@/hooks/useFeatureFlag";
import { useNarrativeStore } from "@/stores/narrative";
import { Button } from "@/components/ui/button";
import { cn } from "@/utils/cn";

import JournalCardsPanel from "./JournalCardsPanel";
import LandmarkNarrativePanel from "./LandmarkNarrativePanel";
import type {
  JournalEntry,
  NarrativeCardData,
  NarrativeSpot,
  PickedFragment,
} from "./types";

const LAYERS = [
  { key: "globe", label: "地球层" },
  { key: "landmark", label: "地标层" },
  { key: "journal", label: "手账层" },
] as const;

/**
 * TripScape 2.0 叙事层（SPEC §2 S1 三层空间切换）。
 *
 * 门控：tripScape2 关闭时本组件返回 null——默认行为与升级前一致。
 * 三层用底部叙事轨道呈现：地球层（未被讲述）→ 地标层（正在被讲述）
 * → 手账层（已沉淀），层间可感知、可返回。
 */
export default function NarrativeHud() {
  const enabled = useFeatureFlag("tripScape2");
  if (!enabled) return null;
  return <NarrativeRail />;
}

function NarrativeRail() {
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
    queryFn: async () =>
      (await api.get("/landmarks/spots")).data.data as NarrativeSpot[],
    staleTime: 60_000,
  });

  const { data: card, isLoading: cardLoading } = useQuery({
    queryKey: ["narrative", "card", landmarkId],
    queryFn: async () =>
      (await api.get(`/narrative/card/${landmarkId}`)).data.data as NarrativeCardData,
    enabled: landmarkId !== null,
  });

  const { data: journal = [] } = useQuery({
    queryKey: ["narrative", "journal"],
    queryFn: async () =>
      (await api.get("/narrative/journal")).data.data as JournalEntry[],
    enabled: !!token,
    retry: 0,
  });

  const addToJournal = useMutation({
    mutationFn: async (cardId: number) =>
      api.post("/narrative/journal/cards", { card_id: cardId }),
    onSuccess: () => {
      toast.success("已加入手账", { description: "卡片以只读快照保留，刷新不会丢失" });
      qc.invalidateQueries({ queryKey: ["narrative", "journal"] });
    },
    onError: (e) => toast.error(errMessage(e, "加入手账失败")),
  });

  const deliver = useMutation({
    mutationFn: async (payload: { card_id: number; landmark_id: number }) =>
      api.post("/narrative/fragments", payload),
    onSuccess: (r) => {
      const data = r.data?.data as { remaining?: number } | undefined;
      toast.success("碎片已匿名投递", {
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
      toast.success("拾到一条叙事碎片");
    },
    onError: (e) => toast.error(errMessage(e, "拾取失败")),
  });

  return (
    <div
      data-testid="narrative-hud"
      className="pointer-events-none absolute inset-x-0 z-30 flex justify-center"
      style={{ bottom: "calc(var(--ui-pad) + 34px)" }}
    >
      <div className="pointer-events-auto w-[min(940px,94vw)] rounded-2xl border border-border/70 bg-card/95 shadow-[0_10px_36px_-12px_rgb(0_0_0/0.45)] backdrop-blur">
        {/* 层指示 + 返回 + 手账入口 */}
        <div className="flex items-center gap-2 border-b border-border/60 px-3 py-2">
          <span className="flex items-center gap-1.5 text-[var(--ui-fs-sm)] font-semibold text-foreground">
            <Layers className="h-4 w-4 text-primary" />
            空间叙事
          </span>
          <div className="flex items-center gap-1">
            {LAYERS.map((l) => (
              <span
                key={l.key}
                className={cn(
                  "rounded-full px-2 py-0.5 text-[11px] transition",
                  layer === l.key
                    ? "bg-primary text-primary-foreground"
                    : "bg-muted text-muted-foreground"
                )}
              >
                {l.label}
              </span>
            ))}
          </div>
          <span data-testid="narrative-layer-indicator" className="sr-only">
            {layer}
          </span>
          <div className="ml-auto flex items-center gap-1.5">
            {landmarkName && layer !== "globe" && (
              <span className="hidden text-[11px] text-muted-foreground sm:inline">
                {landmarkName}
              </span>
            )}
            {layer !== "globe" && (
              <Button
                size="sm"
                variant="ghost"
                data-testid="narrative-back"
                onClick={back}
              >
                <ArrowLeft className="mr-1 h-3.5 w-3.5" />
                返回
              </Button>
            )}
            <Button
              size="sm"
              variant={layer === "journal" ? "default" : "outline"}
              data-testid="narrative-open-journal"
              onClick={showJournal}
            >
              <BookOpen className="mr-1 h-3.5 w-3.5" />
              手账
              <span
                data-testid="narrative-journal-count"
                className="ml-1 rounded-full bg-primary/15 px-1.5 text-[10px] font-bold text-primary"
              >
                {journal.length}
              </span>
            </Button>
          </div>
        </div>

        {/* 地球层：尚未被讲述的空间 */}
        {layer === "globe" && (
          <div data-testid="narrative-layer-globe" className="px-3 py-2">
            <p className="mb-1.5 text-[11px] text-muted-foreground">
              尚未被讲述的空间 · 点一个地标，进入它的叙事层
            </p>
            <div className="flex gap-2 overflow-x-auto pb-1">
              {(spots || []).map((s) => (
                <button
                  key={s.id}
                  data-testid="narrative-landmark-entry"
                  data-landmark-name={s.name}
                  onClick={() => enterLandmark(s.id, s.name)}
                  className="flex shrink-0 items-center gap-2 rounded-xl border border-border/60 bg-background px-2 py-1.5 text-left transition hover:border-primary/60"
                >
                  {s.image_url && (
                    <img
                      src={s.image_url}
                      alt=""
                      className="h-8 w-8 rounded-lg object-cover"
                      onError={(e) => ((e.target as HTMLImageElement).style.display = "none")}
                    />
                  )}
                  <span className="leading-tight">
                    <span className="block text-xs font-medium">{s.name}</span>
                    <span className="block text-[10px] text-muted-foreground">
                      {s.country || s.region || "—"}
                    </span>
                  </span>
                </button>
              ))}
            </div>
          </div>
        )}

        {/* 地标层：正在被讲述的地点 */}
        {layer === "landmark" && (
          <LandmarkNarrativePanel
            card={card}
            loading={cardLoading}
            adding={addToJournal.isPending}
            onAdd={() => card && addToJournal.mutate(card.id)}
            picking={pick.isPending}
            onPick={() => landmarkId !== null && pick.mutate(landmarkId)}
            picked={picked}
            delivering={deliver.isPending}
            onDeliver={(cardId) =>
              landmarkId !== null &&
              deliver.mutate({ card_id: cardId, landmark_id: landmarkId })
            }
          />
        )}

        {/* 手账层：已沉淀的个人叙事 */}
        {layer === "journal" && (
          <JournalCardsPanel
            entries={journal}
            delivering={deliver.isPending}
            onDeliver={(cardId, lmId) =>
              deliver.mutate({ card_id: cardId, landmark_id: lmId })
            }
            onWake={(lmId, name) => enterLandmark(lmId, name)}
          />
        )}
      </div>
    </div>
  );
}
