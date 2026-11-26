/**
 * 行旅识景 TripScape / src/pages/JournalEditWindow
 * 创建日期: 2026-10-09
 *
 * 该组件的界面与交互实现；结构与事件约定见下方代码。
 */

import { Suspense, lazy, useEffect, useMemo, useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { ImagePlus, X, Share2, Search } from "lucide-react";
import { api, errMessage } from "@/api/client";
import { useAuthStore } from "@/stores/auth";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Switch } from "@/components/ui/switch";
// 画布编辑器带 konva（约 450KB），只在真正打开写手账时加载，不拖慢地球首屏
const JournalCanvasEditor = lazy(() => import("@/features/narrative/JournalCanvasEditor"));
import {
  emptyCanvas,
  parseCanvas,
  serializeCanvas,
  type CanvasDoc,
} from "@/features/narrative/canvas-types";

import { FloatingWindow } from "@/components/FloatingWindow";

interface LandmarkOption {

  id: number;

  name: string;

  country?: string;

}

/**

 * 手账编辑浮窗（在地球上叠加打开）：

 * - 新建：presetLandmarkId 可预选地标

 * - 编辑：presetJournalId 加载已有内容

 * - 地标选择支持搜索过滤

 */

export default function JournalEditWindow({

  presetLandmarkId,

  presetJournalId,

  onClose,

}: {

  presetLandmarkId?: number;

  presetJournalId?: number;

  onClose: () => void;

}) {

  const token = useAuthStore((s) => s.token);

  const qc = useQueryClient();

  const [landmarkId, setLandmarkId] = useState<string>(presetLandmarkId ? String(presetLandmarkId) : "");

  const [title, setTitle] = useState("");

  const [content, setContent] = useState("");

  const [visitedAt, setVisitedAt] = useState("");

  const [isPublic, setIsPublic] = useState(true);

  const [images, setImages] = useState<string[]>([]);

  const [canvas, setCanvas] = useState<CanvasDoc>(emptyCanvas());

  const [saving, setSaving] = useState(false);

  const [savingShare, setSavingShare] = useState(false);

  // 地标搜索

  const [pickerOpen, setPickerOpen] = useState(false);

  const [search, setSearch] = useState("");

  const { data: landmarks } = useQuery({

    queryKey: ["landmarks", "all"],

    queryFn: async () =>

      (await api.get("/landmarks/", { params: { page_size: 100 } })).data.data as LandmarkOption[],

  });

  // 当前地标的叙事卡片：画布里的"碎片"元素就贴这张卡片
  const { data: fragmentCard } = useQuery({
    queryKey: ["narrative", "card", landmarkId, "canvas"],
    queryFn: async () =>
      (
        await api.get(`/narrative/card/${landmarkId}`)
      ).data.data as {
        title: string;
        timeFragments?: { text: string; year: number | null }[];
      },
    enabled: !!landmarkId && /^\d+$/.test(landmarkId),
    retry: 0,
  });

  const fragmentSource = fragmentCard
    ? {
        title: fragmentCard.title,
        snippet: fragmentCard.timeFragments?.[0]?.text || "",
        year: (() => {
          const year = fragmentCard.timeFragments?.[0]?.year;
          if (year === null || year === undefined) return "未记年";
          return year < 0 ? `公元前 ${-year} 年` : year < 1000 ? `公元 ${year} 年` : `${year} 年`;
        })(),
        landmarkId: Number(landmarkId),
      }
    : null;

  // 编辑模式：加载已有手账

  const { data: existing } = useQuery({

    queryKey: ["journal", presetJournalId],

    queryFn: async () =>

      (

        await api.get(`/journals/${presetJournalId}`)

      ).data.data as {

        landmark: { id: number; name: string };

        title: string;

        content: string;

        images: string[];

        visited_at: string | null;

        is_public: boolean;

        canvas?: unknown;

      },

    enabled: !!presetJournalId,

  });

  useEffect(() => {

    if (existing) {

      setLandmarkId(String(existing.landmark.id));

      setTitle(existing.title);

      setContent(existing.content);

      setImages(existing.images || []);

      setCanvas(parseCanvas(existing.canvas));

      setIsPublic(existing.is_public);

      setVisitedAt(existing.visited_at || "");

    }

  }, [existing]);

  const selectedLm = landmarks?.find((l) => String(l.id) === landmarkId);

  const filtered = useMemo(() => {

    if (!landmarks) return [];

    const q = search.trim();

    if (!q) return landmarks;

    return landmarks.filter(

      (l) => l.name.includes(q) || (l.country || "").includes(q) || String(l.id) === q

    );

  }, [landmarks, search]);

  const save = async () => {

    if (!token) {

      toast.error("请先登录");

      return;

    }

    if (!landmarkId || !title.trim()) {

      toast.error("请选择地标并填写标题");

      return;

    }

    setSaving(true);

    try {

      const payload = {

        landmark_id: Number(landmarkId),

        title: title.trim(),

        content: content.trim(),

        images: Array.from(
          new Set([
            ...images,
            ...canvas.elements
              .filter((element) => element.type === "photo")
              .map((element) => (element as { src?: string }).src || "")
              .filter(Boolean),
          ])
        ),

        visited_at: visitedAt || null,

        is_public: isPublic,

        canvas: canvas.elements.length ? serializeCanvas(canvas) : undefined,

      };

      if (presetJournalId) {

        const r = await api.put(`/journals/${presetJournalId}`, payload);

        toast.success(r.data?.message || "手账已更新", {

          description: r.data?.message?.includes("审核") ? "审核通过前，读者看到的仍是原版本" : undefined,

        });

      } else {

        await api.post("/journals/", payload);

        toast.success("手账已发布，足迹 +1");

      }

      // 手账/足迹/个人中心与地标热度全部刷新（此前完全没失效，导致

      // 发完手账后个人主页与地球计数仍是旧数据）

      qc.invalidateQueries({ queryKey: ["profile"] });

      qc.invalidateQueries({ queryKey: ["landmark"] });

      qc.invalidateQueries({ queryKey: ["spots"] });

      qc.invalidateQueries({ queryKey: ["footprints"] });

      onClose();

    } catch (e) {

      toast.error(errMessage(e, "保存失败"));

    } finally {

      setSaving(false);

    }

  };

  const share = async () => {

    if (!presetJournalId) return;

    setSavingShare(true);

    try {

      const r = await api.post(`/journals/${presetJournalId}/share`);

      const full = window.location.origin + r.data.share_url;

      await navigator.clipboard?.writeText(full);

      toast.success("分享链接已复制", { description: full });

    } catch (e) {

      toast.error(errMessage(e));

    } finally {

      setSavingShare(false);

    }

  };

  return (

    <FloatingWindow

      open

      onClose={onClose}

      title={presetJournalId ? "编辑手账" : "写旅行手账"}

      width={520}

      maxHeight="72vh"

    >

      <div className="space-y-4">

        {/* 地标选择（带搜索） */}

        <div className="space-y-1.5">

          <Label>地标 *</Label>

          {pickerOpen ? (

            <div className="rounded-xl border-2 border-border">

              <div className="flex items-center gap-2 border-b border-border px-3 py-2">

                <Search className="h-4 w-4 shrink-0 text-muted-foreground" />

                <input

                  autoFocus

                  value={search}

                  onChange={(e) => setSearch(e.target.value)}

                  className="w-full bg-transparent text-sm outline-none"

                />

                <button

                  onClick={() => {

                    setPickerOpen(false);

                    setSearch("");

                  }}

                  className="shrink-0 rounded-lg p-1 text-muted-foreground hover:bg-muted"

                >

                  <X className="h-4 w-4" />

                </button>

              </div>

              <div className="max-h-44 overflow-y-auto p-1.5">

                {filtered.length ? (

                  filtered.map((lm) => (

                    <button

                      key={lm.id}

                      onClick={() => {

                        setLandmarkId(String(lm.id));

                        setPickerOpen(false);

                        setSearch("");

                      }}

                      className={`flex w-full items-center justify-between rounded-lg px-3 py-2 text-left text-sm transition hover:bg-accent ${

                        String(lm.id) === landmarkId ? "bg-accent" : ""

                      }`}

                    >

                      <span>{lm.name}</span>

                      {lm.country && <span className="text-xs text-muted-foreground">{lm.country}</span>}

                    </button>

                  ))

                ) : (

                  <p className="py-6 text-center text-sm text-muted-foreground">无匹配地标</p>

                )}

              </div>

            </div>

          ) : (

            <button

              onClick={() => setPickerOpen(true)}

              className="flex w-full items-center justify-between rounded-lg border-2 border-border bg-background px-3 py-2.5 text-sm transition hover:bg-accent"

            >

              <span className={selectedLm ? "" : "text-muted-foreground"}>

                {selectedLm ? selectedLm.name : "选择地标"}

              </span>

              <Search className="h-4 w-4 text-muted-foreground" />

            </button>

          )}

        </div>

        <div className="space-y-1.5">

          <Label>标题 *</Label>

          <Input value={title} onChange={(e) => setTitle(e.target.value)} maxLength={128} />

        </div>

        <div className="space-y-1.5">

          <Label>手账画布（3:4）</Label>

          <p className="text-[11px] text-muted-foreground">

            拖拽移动，四角缩放，选中后可旋转；图层顺序即叠放顺序。

          </p>

          <Suspense

            fallback={

              <div className="flex h-56 items-center justify-center rounded-panel border border-border/70 text-[11px] text-muted-foreground">

                画布加载中…

              </div>

            }

          >

            <JournalCanvasEditor

              value={canvas}

              onChange={setCanvas}

                fragment={fragmentSource}

            />

          </Suspense>

        </div>

        <div className="space-y-1.5">

          <Label>旅行日期</Label>

          <Input type="date" value={visitedAt} onChange={(e) => setVisitedAt(e.target.value)} />

        </div>

        <div className="space-y-1.5">

          <Label>内容</Label>

          <Textarea

            value={content}

            onChange={(e) => setContent(e.target.value)}

            rows={6}

            className="resize-y"

          />

        </div>

        <div className="flex items-center justify-between rounded-lg border-2 border-border p-3">

          <div>

            <div className="text-sm font-medium">公开展示</div>

            <div className="text-xs text-muted-foreground">公开后展示在地标页，可生成分享链接</div>

          </div>

          <Switch checked={isPublic} onCheckedChange={setIsPublic} />

        </div>

        <div className="flex items-center justify-between">

          {presetJournalId ? (

            <Button variant="outline" size="sm" onClick={share} disabled={!isPublic || savingShare}>

              <Share2 className="mr-1.5 h-3.5 w-3.5" />

              {savingShare ? "生成中…" : "分享链接"}

            </Button>

          ) : (

            <span />

          )}

          <div className="flex gap-2">

            <Button variant="ghost" size="sm" onClick={onClose}>

              取消

            </Button>

            <Button size="sm" onClick={save} disabled={saving}>

              {saving ? "保存中…" : presetJournalId ? "更新" : "发布手账"}

            </Button>

          </div>

        </div>

      </div>

    </FloatingWindow>

  );

}

