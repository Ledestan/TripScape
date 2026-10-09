import { lazy, Suspense, useEffect, useState } from "react";
import { useParams } from "react-router-dom";import { useQuery } from "@tanstack/react-query";
import { Globe2 } from "lucide-react";

import Globe, { Spot, globeBus } from "@/features/globe/Globe";
const SearchWindow = lazy(() => import("@/features/search/SearchWindow"));
import DynamicIslandSearch from "@/features/search/DynamicIslandSearch";
import FloatingDock from "@/layouts/FloatingDock";
import MessageBar from "@/features/qa/MessageBar";
import GlobeControls from "@/features/globe/GlobeControls";
import ElasticLandmarkCard from "@/features/globe/ElasticLandmarkCard";
import LandmarkDetailWindow from "@/pages/LandmarkDetail";
import JournalEditWindow from "@/pages/JournalEditWindow";
import { JournalViewWindow } from "@/layouts/JournalViewWindow";
import { api } from "@/api/client";
import { useViewport } from "@/hooks/useViewport";

/**
 * 主页：全屏地球 + 四角浮层。
 * - 详情浮窗在地球上打开（点光点/路由直达）
 * - 详情内点"写手账" -> 隐藏详情、开手账浮窗；手账关闭后详情回来
 */
export default function GlobeApp() {
  const { compact, narrow } = useViewport();
  const routeParams = useParams();

  const [selectedSpot, setSelectedSpot] = useState<Spot | null>(null);
  const [highlightIds, setHighlightIds] = useState<Set<number> | undefined>(undefined);
  const [detailId, setDetailId] = useState<number | null>(
    routeParams.id ? Number(routeParams.id) : null
  );
  const [journalLandmarkId, setJournalLandmarkId] = useState<number | null>(null);
  const [journalOpen, setJournalOpen] = useState(false);
  const [cardDocked, setCardDocked] = useState(false);

  const { data: spots } = useQuery({
    queryKey: ["landmarks", "spots"],
    queryFn: async () => (await api.get("/landmarks/spots")).data.data as Spot[],
    staleTime: 60_000,
  });

  const flyToSpot = (s: Spot | { id: number; lat: number; lon: number }) => {
    globeBus.flyTo(s.lat, s.lon, s.id);
  };

  // 拖动地球 -> 资料卡片收成小条
  useEffect(() => {
    const onMove = () => {
      if (window.__tsDragging) setCardDocked(true);
    };
    window.addEventListener("pointermove", onMove);
    return () => window.removeEventListener("pointermove", onMove);
  }, []);

  // 菜单"写手账"事件 -> 在地球上打开手账浮窗（可带 landmark_id 预选）
  useEffect(() => {
    const onOpenJournal = (e: Event) => {
      const lmId = (e as CustomEvent<number>).detail;
      if (lmId) setJournalLandmarkId(lmId);
      setJournalOpen(true);
    };
    window.addEventListener("ts:open-journal", onOpenJournal);
    return () => window.removeEventListener("ts:open-journal", onOpenJournal);
  }, []);

  // 消息卡"详情"事件 -> 打开地标详情浮窗
  useEffect(() => {
    const onOpenDetail = (e: Event) => {
      const id = (e as CustomEvent<number>).detail;
      if (id) setDetailId(id);
    };
    window.addEventListener("ts:open-detail", onOpenDetail);
    return () => window.removeEventListener("ts:open-detail", onOpenDetail);
  }, []);

  // 搜索结果"查看手账"事件
  const [viewJournalId, setViewJournalId] = useState<number | null>(null);
  useEffect(() => {
    const onView = (e: Event) => setViewJournalId((e as CustomEvent<number>).detail ?? null);
    window.addEventListener("ts:open-journal-view", onView);
    return () => window.removeEventListener("ts:open-journal-view", onView);
  }, []);

  // 搜索"显示更多"事件 -> 全局搜索浮窗（携带搜索词）
  const [searchOpen, setSearchOpen] = useState(false);
  const [searchQuery, setSearchQuery] = useState("");
  useEffect(() => {
    const onOpenSearch = (e: Event) => {
      setSearchQuery((e as CustomEvent<string>).detail || "");
      setSearchOpen(true);
    };
    window.addEventListener("ts:open-search", onOpenSearch);
    return () => window.removeEventListener("ts:open-search", onOpenSearch);
  }, []);

  return (
    <div className="relative h-screen w-full overflow-hidden">
      <Globe
        onSpotClick={(s) => {
          setSelectedSpot(s);
          setCardDocked(false);
        }}
        highlightIds={highlightIds}
      />

      {/* 上下渐隐 vignette：增强空间纵深（不拦截交互） */}
      <div className="globe-vignette pointer-events-none absolute inset-0 z-[5]" />

      {/* 左上：Logo + 搜索 */}
      <div
        className="absolute left-0 top-0 z-30 flex flex-col gap-[var(--ui-gap)]"
        style={{ padding: "var(--ui-pad)", maxWidth: "calc(50vw)" }}
      >
        <div className="flex items-center gap-[var(--ui-gap)]">
          <div className="flex h-10 shrink-0 items-center gap-2 rounded-full border border-border/60 bg-card pl-3 pr-3.5 shadow-[0_2px_12px_-2px_rgb(0_0_0/0.25)] dark:shadow-[0_2px_14px_-2px_rgb(0_0_0/0.6)]">
            <Globe2 className="h-[18px] w-[18px] text-primary" />
            {!narrow && (
              <span className="text-[var(--ui-fs)] font-bold tracking-wide text-foreground">行旅识景</span>
            )}
          </div>
        </div>
        <DynamicIslandSearch
          spots={spots || []}
          onHighlightChange={setHighlightIds}
          onPickLandmark={(s) => {
            // 搜索选中：飞行 + 打开详情浮窗
            flyToSpot(s);
            setDetailId(s.id);
          }}
          narrow={narrow}
        />
      </div>

      {/* 右上：日夜 + 登录/头像（点击弹菜单） */}
      <FloatingDock />

      {/* 左下：消息栏 */}
      <div className="absolute bottom-0 left-0 z-20" style={{ padding: "var(--ui-pad)" }}>
        <MessageBar
          spots={spots || []}
          onFly={(lmId) => {
            const s = (spots || []).find((x) => x.id === lmId);
            if (s) flyToSpot(s);
          }}
          compact={compact}
          narrow={narrow}
        />
      </div>

      {/* 右下：地球控件 */}
      <div className="absolute bottom-0 right-0 z-20" style={{ padding: "var(--ui-pad)" }}>
        <GlobeControls compact={compact} narrow={narrow} />
      </div>

      {/* 弹性资料卡片（点光点弹出；拖动时收成小条） */}
      {selectedSpot && detailId === null && !journalOpen && (
        <ElasticLandmarkCard
          spot={selectedSpot}
          onClose={() => setSelectedSpot(null)}
          narrow={narrow}
          forceDocked={cardDocked}
          onOpenDetail={() => setDetailId(selectedSpot.id)}
        />
      )}

      {/* 详情浮窗（写手账时叠加在上，不隐藏详情） */}
      {detailId !== null && (
        <LandmarkDetailWindow
          landmarkId={detailId}
          onClose={() => {
            setDetailId(null);
            setSelectedSpot(null);
          }}
          onWriteJournal={(lmId) => {
            setJournalLandmarkId(lmId);
            setJournalOpen(true);
          }}
        />
      )}

      {/* 手账浮窗（可叠加在详情/个人主页之上） */}
      {(journalLandmarkId !== null || journalOpen) && (
        <JournalEditWindow
          presetLandmarkId={journalLandmarkId ?? undefined}
          onClose={() => {
            setJournalLandmarkId(null);
            setJournalOpen(false);
          }}
        />
      )}

      {/* 全局搜索浮窗（"显示更多"打开，带上搜索词） */}
      {searchOpen && (
        <Suspense fallback={null}>
          <SearchWindow initialQuery={searchQuery} onClose={() => setSearchOpen(false)} />
        </Suspense>
      )}

      {/* 搜索结果手账查看浮窗 */}
      {viewJournalId !== null && (
        <JournalViewWindow journalId={viewJournalId} onClose={() => setViewJournalId(null)} />
      )}

      {/* 底部提示 */}
      {!narrow && (
        <div
          className="pointer-events-none absolute left-1/2 z-10 -translate-x-1/2 rounded-full border border-border/70 bg-card px-4 py-1 text-[var(--ui-fs-sm)] text-muted-foreground"
          style={{ bottom: "calc(var(--ui-pad) + 6px)" }}
        >
          拖动旋转 · 滚轮缩放 · 点击看百科
        </div>
      )}
    </div>
  );
}
