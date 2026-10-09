import { useEffect, useRef, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Search as SearchIcon, X, User as UserIcon, MapPin, NotebookPen } from "lucide-react";

import { api } from "@/api/client";
import UserProfileWindow from "@/features/profile/UserProfileWindow";

interface SearchItem {
  kind: "landmark" | "user";
  id: number;
  title: string;
  subtitle: string;
  image_url: string;
}

interface SpotLite {
  id: number;
  name: string;
  lat: number;
  lon: number;
}

/**
 * 左上角搜索（只搜地标与用户）：
 * - 地标：飞行 + 打开详情浮窗
 * - 用户：打开用户公开主页浮窗
 * - 面板固定尺寸；窄屏收成图标
 */
export default function DynamicIslandSearch({
  spots,
  onHighlightChange,
  onPickLandmark,
  narrow,
}: {
  spots: SpotLite[];
  onHighlightChange?: (ids: Set<number> | undefined) => void;
  onPickLandmark?: (s: SpotLite) => void;
  narrow?: boolean;
}) {
  const [expanded, setExpanded] = useState(false);
  const [query, setQuery] = useState("");
  const [submitted, setSubmitted] = useState("");
  const [showPanel, setShowPanel] = useState(false);
  const [userOpen, setUserOpen] = useState<number | null>(null);
  const wrapRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    const onDown = (e: MouseEvent) => {
      if (wrapRef.current && !wrapRef.current.contains(e.target as Node)) {
        setExpanded(false);
        setShowPanel(false);
        onHighlightChange?.(undefined);
      }
    };
    document.addEventListener("mousedown", onDown);
    return () => document.removeEventListener("mousedown", onDown);
  }, [onHighlightChange]);

  useEffect(() => {
    if (expanded) inputRef.current?.focus();
  }, [expanded]);

  const { data, isFetching } = useQuery({
    queryKey: ["island-search", submitted],
    queryFn: async () =>
      (
        await api.get("/search/", { params: { q: submitted, kind: "landmark", page_size: 10 } })
      ).data.data as SearchItem[],
    enabled: submitted.length > 0 && showPanel,
  });

  const { data: journals } = useQuery({
    queryKey: ["island-search-journals", submitted],
    queryFn: async () =>
      (
        await api.get("/search/", { params: { q: submitted, kind: "journal", page_size: 5 } })
      ).data.data as SearchItem[],
    enabled: submitted.length > 0 && showPanel,
  });

  const { data: users } = useQuery({
    queryKey: ["island-search-users", submitted],
    queryFn: async () =>
      (
        await api.get("/search/", { params: { q: submitted, kind: "user", page_size: 6 } })
      ).data.data as SearchItem[],
    enabled: submitted.length > 0 && showPanel,
  });

  const landmarks = data ?? [];
  const allUsers = users ?? [];
  const journalHits = journals ?? [];

  useEffect(() => {
    if (!showPanel || !submitted) {
      onHighlightChange?.(undefined);
      return;
    }
    const q = submitted.trim();
    const hits = new Set(spots.filter((s) => s.name.includes(q)).map((s) => s.id));
    landmarks.forEach((d) => hits.add(d.id));
    onHighlightChange?.(hits.size > 0 ? hits : undefined);
  }, [showPanel, submitted, landmarks, spots, onHighlightChange]);

  const doSearch = () => {
    const q = query.trim();
    if (!q) return;
    setSubmitted(q);
    setShowPanel(true);
  };

  const pickLandmark = (item: SearchItem) => {
    const s = spots.find((x) => x.id === item.id);
    if (s) {
      onPickLandmark?.(s);
      setShowPanel(false);
    }
  };

  /* 结果面板（固定尺寸，只含地标+用户） */
  const SearchPanel = showPanel && submitted ? (
    <div
      className="absolute left-0 top-[calc(100%+var(--ui-gap))] w-[min(28vw,400px)] overflow-hidden rounded-[var(--ui-radius)] border border-border/60 bg-card text-card-foreground shadow-[0_8px_36px_-6px_rgb(0_0_0/0.3)] dark:shadow-[0_8px_40px_-4px_rgb(0_0_0/0.7)]"
      style={{ fontSize: "var(--ui-fs-sm)" }}
    >
      <div className="flex items-center justify-between border-b border-border px-4 py-2.5">
        <div className="text-sm font-semibold">
          {isFetching ? "搜索中…" : `“${submitted}”`}
        </div>
        <button
          onClick={() => {
            setShowPanel(false);
            onHighlightChange?.(undefined);
          }}
          className="rounded-lg p-1.5 text-muted-foreground transition hover:bg-muted hover:text-foreground"
        >
          <X className="h-4 w-4" />
        </button>
      </div>

      <div className="max-h-[36vh] overflow-y-auto p-2">
        {/* 地标 */}
        {landmarks.length > 0 && (
          <>
            <div className="px-1.5 pb-1 pt-0.5 text-[10px] font-medium uppercase text-muted-foreground">地标</div>
            {landmarks.map((item, i) => (
              <button
                key={`lm-${item.id}-${i}`}
                onClick={() => pickLandmark(item)}
                className="flex w-full items-center gap-2.5 rounded-xl px-2.5 py-2 text-left transition hover:bg-accent hover:text-accent-foreground"
              >
                {item.image_url ? (
                  <img src={item.image_url} alt="" className="h-8 w-8 shrink-0 rounded-lg object-cover" />
                ) : (
                  <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-muted">
                    <MapPin className="h-4 w-4 text-muted-foreground" />
                  </div>
                )}
                <div className="min-w-0 flex-1">
                  <div className="truncate">{item.title}</div>
                  <div className="truncate text-muted-foreground">{item.subtitle}</div>
                </div>
                <span className="shrink-0 rounded-full bg-muted px-2 py-0.5 text-[10px] text-muted-foreground">查看</span>
              </button>
            ))}
          </>
        )}

        {/* 手账 */}
        {journalHits.length > 0 && (
          <>
            <div className="px-1.5 pb-1 pt-2 text-[10px] font-medium uppercase text-muted-foreground">手账</div>
            {journalHits.map((item, i) => (
              <button
                key={`j-${item.id}-${i}`}
                onClick={() => {
                  window.dispatchEvent(new CustomEvent("ts:open-detail", { detail: item.id }));
                  setShowPanel(false);
                }}
                className="flex w-full items-center gap-2.5 rounded-xl px-2.5 py-2 text-left transition hover:bg-accent hover:text-accent-foreground"
              >
                <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-muted">
                  <NotebookPen className="h-4 w-4 text-muted-foreground" />
                </div>
                <div className="min-w-0 flex-1">
                  <div className="truncate">{item.title}</div>
                  <div className="truncate text-muted-foreground">{item.subtitle}</div>
                </div>
              </button>
            ))}
          </>
        )}

        {/* 用户 */}
        {allUsers.length > 0 && (
          <>
            <div className="px-1.5 pb-1 pt-2 text-[10px] font-medium uppercase text-muted-foreground">用户</div>
            {allUsers.map((item, i) => (
              <button
                key={`us-${item.id}-${i}`}
                onClick={() => {
                  setUserOpen(item.id);
                  setShowPanel(false);
                }}
                className="flex w-full items-center gap-2.5 rounded-xl px-2.5 py-2 text-left transition hover:bg-accent hover:text-accent-foreground"
              >
                {item.image_url ? (
                  <img src={item.image_url} alt="" className="h-8 w-8 shrink-0 rounded-full object-cover" />
                ) : (
                  <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-muted">
                    <UserIcon className="h-4 w-4 text-muted-foreground" />
                  </div>
                )}
                <div className="min-w-0 flex-1">
                  <div className="truncate">{item.title}</div>
                  <div className="truncate text-muted-foreground">@{item.subtitle}</div>
                </div>
                <span className="shrink-0 rounded-full bg-muted px-2 py-0.5 text-[10px] text-muted-foreground">主页</span>
              </button>
            ))}
          </>
        )}

        {!isFetching && landmarks.length === 0 && allUsers.length === 0 && (
          <p className="py-8 text-center text-muted-foreground">没有找到相关内容</p>
        )}
      </div>

      {/* 显示更多 -> 全局搜索浮窗 */}
      {(landmarks.length >= 5 || allUsers.length >= 5 || journalHits.length >= 5) && (
        <button
          onClick={() => {
            window.dispatchEvent(new CustomEvent("ts:open-search", { detail: submitted }));
            setShowPanel(false);
            setExpanded(false);
          }}
          className="block w-full border-t border-border py-2.5 text-center text-muted-foreground transition hover:bg-accent hover:text-accent-foreground"
        >
          显示更多
        </button>
      )}
    </div>
  ) : null;

  /* 窄屏收成图标（与右下控件同尺寸） */
  if (narrow && !expanded) {
    return (
      <div ref={wrapRef} className="relative">
        <button
          onClick={() => setExpanded(true)}
          className="flex items-center justify-center rounded-full border border-border/70 bg-card text-muted-foreground shadow-md transition hover:bg-accent hover:text-accent-foreground"
          style={{ width: "var(--icon-btn)", height: "var(--icon-btn)" }}
          title="搜索"
        >
          <SearchIcon className="h-5 w-5" />
        </button>
        {SearchPanel}
        {userOpen !== null && <UserProfileWindow userId={userOpen} onClose={() => setUserOpen(null)} />}
      </div>
    );
  }

  return (
    <div ref={wrapRef} className="relative">
      <div
        onClick={() => setExpanded(true)}
        className="flex cursor-pointer items-center gap-2 rounded-full border border-border/70 bg-card px-3.5 text-card-foreground shadow-md transition-all duration-500 ease-[cubic-bezier(0.34,1.56,0.64,1)] hover:border-border focus-within:border-primary"
        style={{
          width: expanded ? "min(30vw, 440px)" : "min(24vw, 380px)",
          height: "var(--icon-btn)",
        }}
      >
        <SearchIcon className="h-[18px] w-[18px] shrink-0 text-muted-foreground" />
        <input
          ref={inputRef}
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter") doSearch();
            if (e.key === "Escape") {
              setExpanded(false);
              setShowPanel(false);
              onHighlightChange?.(undefined);
            }
          }}
          onFocus={() => setExpanded(true)}
          placeholder={expanded ? "搜索地标、用户…" : "搜索"}
          className="min-w-0 flex-1 bg-transparent text-[var(--ui-fs)] text-foreground outline-none placeholder:text-muted-foreground"
        />
        {expanded && query && (
          <button
            onClick={(e) => {
              e.stopPropagation();
              setQuery("");
              setShowPanel(false);
              onHighlightChange?.(undefined);
            }}
            className="shrink-0 rounded-full p-0.5 text-muted-foreground hover:text-foreground"
          >
            <X className="h-3.5 w-3.5" />
          </button>
        )}
        {expanded && (
          <button
            onClick={(e) => {
              e.stopPropagation();
              doSearch();
            }}
            className="shrink-0 rounded-full bg-primary px-2.5 py-1 text-[var(--ui-fs-sm)] font-medium text-primary-foreground transition hover:bg-primary/90"
          >
            搜索
          </button>
        )}
      </div>
      {SearchPanel}
      {userOpen !== null && <UserProfileWindow userId={userOpen} onClose={() => setUserOpen(null)} />}
    </div>
  );
}

