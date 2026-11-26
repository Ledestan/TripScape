/**
 * 行旅识景 TripScape / 写手账浮窗
 * 创建日期: 2026-11-26
 *
 * 用 CreationComposeWindow 作为唯一的手账创作界面，完成:
 *     1. 标题 / 日期 / 公开开关 / 正文（通过 metaBar 注入到创作浮窗顶部）
 *     2. 画布落库：composeToJournalCanvas 转成 /api/journals 的 canvas 结构
 *     3. 照片：素材栏直接上传（POST /uploads/image），并同步进 images
 *     4. 编辑已有手账：canvas 转回编辑器文档回填，标题等一并带回
 *
 * 依赖:
 *     依赖库: @tanstack/react-query, sonner
 *
 * 用法:
 *     <JournalComposeWindow open presetLandmarkId={id} onClose={() => setOpen(false)} />
 *
 * 注意:
 *     1. 保存成功后不自动关窗，让作者看到"已保存"再自己关，避免误以为没存上。
 *     2. initialElements 必须 memo：创作浮窗用它判断是否重置历史，每次新数组会把画布清空。
 */

import { useEffect, useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";

import { api, errMessage } from "@/api/client";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Switch } from "@/components/ui/switch";
import CreationComposeWindow from "@/features/creation/CreationComposeWindow";
import type { AssetItem } from "@/features/creation/types";
import type { ComposeDoc, ComposeElement } from "@/features/creation/types";
import { parseCanvas } from "@/features/narrative/canvas-types";
import { composeToJournalCanvas, journalCanvasToCompose } from "./canvas-map";

interface JournalDetail {
  id: number;
  title: string;
  content: string;
  images: string[];
  canvas?: unknown;
  visited_at: string | null;
  is_public: boolean;
  landmark: { id: number; name: string };
}

export default function JournalComposeWindow({
  open,
  presetLandmarkId,
  presetJournalId,
  onClose,
}: {
  open: boolean;
  presetLandmarkId?: number;
  presetJournalId?: number;
  onClose: () => void;
}) {
  const qc = useQueryClient();
  const [landmarkId, setLandmarkId] = useState<number | null>(presetLandmarkId ?? null);
  const [title, setTitle] = useState("");
  const [content, setContent] = useState("");
  const [visitedAt, setVisitedAt] = useState("");
  const [isPublic, setIsPublic] = useState(true);

  // 编辑模式：取回已有手账
  const { data: existing } = useQuery({
    queryKey: ["journal", presetJournalId],
    queryFn: async () =>
      (await api.get(`/journals/${presetJournalId}`)).data.data as JournalDetail,
    enabled: !!presetJournalId,
  });

  // 地标名（回显用）
  const { data: landmarks } = useQuery({
    queryKey: ["landmarks", "all"],
    queryFn: async () =>
      (await api.get("/landmarks/", { params: { page_size: 100 } })).data.data as {
        id: number;
        name: string;
      }[],
    staleTime: 60_000,
  });
  const landmarkName =
    existing?.landmark?.name ||
    landmarks?.find((item) => item.id === landmarkId)?.name ||
    "";

  // 已有手账回填（标题、日期、公开、正文、地标）
  useEffect(() => {
    if (!existing) return;
    setLandmarkId(existing.landmark.id);
    setTitle(existing.title);
    setContent(existing.content || "");
    setVisitedAt(existing.visited_at || "");
    setIsPublic(existing.is_public);
  }, [existing]);

  const initialElements = useMemo<ComposeElement[]>(
    () => (existing ? journalCanvasToCompose(existing.canvas).elements : []),
    [existing]
  );
  const initialBackground = useMemo(
    () => (existing ? parseCanvas(existing.canvas).background : undefined),
    [existing]
  );

  // 素材：已有图片当照片素材；贴纸、胶带、底纹内置
  const assetSlots = useMemo(
    () => ({
      photos: (existing?.images || []).map<AssetItem>((src, index) => ({
        id: `photo-${index}`,
        label: `照片 ${index + 1}`,
        kind: "photo",
        src,
      })),
      stickers: [
        { id: "st-star", label: "星标", kind: "sticker" as const, variant: "star" as const, color: "#d9a441" },
        { id: "st-heart", label: "心形", kind: "sticker" as const, variant: "heart" as const, color: "#c05a4a" },
        { id: "st-pin", label: "定位", kind: "sticker" as const, variant: "pin" as const, color: "#3d7a68" },
      ],
      tapes: [
        { id: "tp-kraft", label: "牛皮纸", kind: "tape" as const, color: "#d6ba84", pattern: "plain" as const },
        { id: "tp-stripe", label: "条纹", kind: "tape" as const, color: "#8fa6ad", pattern: "stripe" as const },
      ],
      backgrounds: [
        { id: "bg-cream", label: "米白纸", kind: "background" as const, color: "#f3ece1" },
        { id: "bg-kraft", label: "牛皮纸", kind: "background" as const, color: "#e6d7c3" },
        { id: "bg-night", label: "深空", kind: "background" as const, color: "#141a24" },
      ],
    }),
    [existing?.images]
  );

  /** 上传照片：接口返回站内地址，包成素材给创作浮窗 */
  const uploadPhoto = async (file: File): Promise<AssetItem | null> => {
    const form = new FormData();
    form.append("image", file);
    const response = await api.post("/uploads/image", form);
    const url = (response.data?.url || response.data?.data?.url) as string | undefined;
    if (!url) throw new Error("上传成功但没有拿到图片地址");
    return {
      id: `photo-${Date.now()}`,
      label: file.name.slice(0, 20) || "照片",
      kind: "photo",
      src: url,
    };
  };

  const save = useMutation({
    mutationFn: async (doc: ComposeDoc) => {
      if (!landmarkId) throw new Error("请先选择地标");
      if (!title.trim()) throw new Error("给这页手账起个标题");
      const canvas = composeToJournalCanvas(doc);
      const images = canvas.elements
        .filter((element) => element.type === "photo")
        .map((element) => (element as { src?: string }).src || "")
        .filter(Boolean);

      const payload = {
        landmark_id: landmarkId,
        title: title.trim(),
        content: content.trim(),
        images: Array.from(new Set([...(existing?.images || []), ...images])),
        visited_at: visitedAt || null,
        is_public: isPublic,
        canvas,
      };

      if (presetJournalId) {
        const response = await api.put(`/journals/${presetJournalId}`, payload);
        return response.data as { message?: string };
      }
      await api.post("/journals/", payload);
      return { message: "手账已发布，足迹 +1" };
    },
    onSuccess: (result) => {
      toast.success(result?.message || "手账已保存", {
        description: result?.message?.includes("审核") ? "审核通过前，读者看到的仍是原版本" : undefined,
      });
      qc.invalidateQueries({ queryKey: ["journals"] });
      qc.invalidateQueries({ queryKey: ["journal"] });
      qc.invalidateQueries({ queryKey: ["profile"] });
      qc.invalidateQueries({ queryKey: ["landmarks"] });
      qc.invalidateQueries({ queryKey: ["footprints"] });
    },
    onError: (error) => toast.error(errMessage(error, "保存失败")),
  });

  return (
    <CreationComposeWindow
      open={open}
      title={presetJournalId ? "编辑手账" : "写手账"}
      initialElements={initialElements}
      initialBackground={initialBackground}
      assetSlots={assetSlots}
      onUploadPhoto={uploadPhoto}
      onSave={async (doc) => {
        await save.mutateAsync(doc);
      }}
      onDirtyChange={() => undefined}
      onClose={onClose}
      metaBar={
        <div className="flex flex-wrap items-end gap-2">
          <div className="min-w-[180px] flex-1">
            <label className="mb-1 block text-[10.5px] text-muted-foreground">标题 *</label>
            <Input
              value={title}
              onChange={(event) => setTitle(event.target.value)}
              maxLength={128}
              data-testid="journal-compose-title"
              placeholder="例如：在阿斯旺的黄昏"
              className="h-8 text-[12px]"
            />
          </div>
          <div className="w-[120px]">
            <label className="mb-1 block text-[10.5px] text-muted-foreground">旅行日期</label>
            <Input
              type="date"
              value={visitedAt}
              onChange={(event) => setVisitedAt(event.target.value)}
              className="h-8 text-[12px]"
            />
          </div>
          <div className="min-w-[160px] flex-1">
            <label className="mb-1 block text-[10.5px] text-muted-foreground">
              正文（可选，读者先看画布）
            </label>
            <Input
              value={content}
              onChange={(event) => setContent(event.target.value)}
              placeholder="补一句当时的感受"
              className="h-8 text-[12px]"
            />
          </div>
          <label className="flex h-8 items-center gap-1.5 text-[11px] text-muted-foreground">
            <Switch checked={isPublic} onCheckedChange={setIsPublic} />
            公开
          </label>
          <span className="flex h-8 items-center text-[11px] text-muted-foreground">
            {landmarkName || "未选地标"}
          </span>
        </div>
      }
    />
  );
}


function formatYear(year: number | null): string {
  if (year === null) return "未记年";
  if (year < 0) return `公元前 ${-year} 年`;
  if (year < 1000) return `公元 ${year} 年`;
  return `${year} 年`;
}
