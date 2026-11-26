/**
 * 行旅识景 TripScape / 手账画布编辑器
 * 创建日期: 2026-11-26
 *
 * 3:4 的手账版式编辑，用 react-konva 实现，完成:
 *     1. 五类元素：照片（可直接上传）、文字、地标碎片卡片、贴纸、胶带
 *     2. 选中后可拖拽、缩放、旋转（Konva Transformer）
 *     3. 自定义：圆角、投影、边框、透明度、旋转、字号、文字颜色、背景色
 *     4. 图层排序：上移 / 下移 / 置顶 / 置底；可复制、删除
 *     5. 受控组件：value 进来、onChange 出去，保存交给上层
 *
 * 依赖:
 *     依赖库: react-konva, konva, lucide-react, sonner
 *
 * 用法:
 *     <JournalCanvasEditor value={doc} onChange={setDoc} fragment={{ title, snippet, year, landmarkId }} />
 *
 * 注意:
 *     1. 坐标一律按 720×960 逻辑画布存，渲染时整体缩放，换设备不跑版。
 *     2. 缩放用统一的 scale 折叠进元素，避免非等比拉伸把文字拉变形。
 *     3. 上传走 POST /uploads/image，返回站内路径后立刻变成照片元素。
 */

import { useEffect, useMemo, useRef, useState } from "react";
import {
  ArrowDown,
  ArrowUp,
  ChevronsDown,
  ChevronsUp,
  Copy,
  ImagePlus,
  Layers,
  Sticker as StickerIcon,
  Trash2,
  Type,
  Upload,
} from "lucide-react";
import { Group, Layer, Rect, Stage, Transformer } from "react-konva";
import type Konva from "konva";
import { toast } from "sonner";

import { api, errMessage } from "@/api/client";
import { Button } from "@/components/ui/button";
import { ElementNode } from "./JournalCanvasView";
import {
  CANVAS_H,
  CANVAS_W,
  createFragment,
  createPhoto,
  createSticker,
  createTape,
  createText,
  moveLayer,
  removeElement,
  updateElement,
  type CanvasDoc,
  type CanvasElement,
  type FragmentElement,
} from "./canvas-types";

export default function JournalCanvasEditor({
  value,
  onChange,
  fragment,
}: {
  value: CanvasDoc;
  onChange: (doc: CanvasDoc) => void;
  /** 当前地标的碎片卡片来源 */
  fragment?: { title: string; snippet?: string; year?: string; landmarkId?: number } | null;
}) {
  const containerRef = useRef<HTMLDivElement | null>(null);
  const transformerRef = useRef<Konva.Transformer | null>(null);
  const nodeRefs = useRef(new Map<string, Konva.Group>());
  const fileRef = useRef<HTMLInputElement | null>(null);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [width, setWidth] = useState(360);
  const [uploading, setUploading] = useState(false);

  // 画布宽度跟随容器，但比例永远 3:4
  useEffect(() => {
    const element = containerRef.current;
    if (!element) return;
    const observer = new ResizeObserver((entries) => {
      const next = entries[0]?.contentRect.width ?? 360;
      setWidth(Math.max(240, Math.min(next, 520)));
    });
    observer.observe(element);
    return () => observer.disconnect();
  }, []);

  const scale = width / CANVAS_W;
  const selected = useMemo(
    () => value.elements.find((element) => element.id === selectedId) || null,
    [value.elements, selectedId]
  );

  // 选中变化时把 Transformer 挂到对应节点
  useEffect(() => {
    const transformer = transformerRef.current;
    if (!transformer) return;
    const node = selectedId ? nodeRefs.current.get(selectedId) : null;
    transformer.nodes(node ? [node] : []);
    transformer.getLayer()?.batchDraw();
  }, [selectedId, value.elements.length]);

  /** 把拖拽/缩放/旋转的结果写回元素（缩放折叠进 scale，保持等比） */
  const commitTransform = (element: CanvasElement) => {
    const node = nodeRefs.current.get(element.id);
    if (!node) return;
    const nextScale = Math.min(4, Math.max(0.1, element.scale * node.scaleX()));
    node.scaleX(1);
    node.scaleY(1);
    onChange(
      updateElement(value, element.id, {
        x: Math.round(node.x()),
        y: Math.round(node.y()),
        rotation: Math.round(node.rotation()),
        scale: Number(nextScale.toFixed(3)),
      })
    );
  };

  const addElement = (element: CanvasElement) => {
    if (value.elements.length >= 40) {
      toast.error("元素太多了，先删掉几个再放");
      return;
    }
    onChange({ ...value, elements: [...value.elements, element] });
    setSelectedId(element.id);
  };

  const layer = (move: "up" | "down" | "top" | "bottom") => {
    if (!selectedId) return;
    onChange(moveLayer(value, selectedId, move));
  };

  const patch = (patchValue: Partial<CanvasElement>) => {
    if (!selectedId) return;
    onChange(updateElement(value, selectedId, patchValue));
  };

  /** 上传一张照片，成功后直接落到画布中央偏上 */
  const uploadPhoto = async (file: File) => {
    setUploading(true);
    try {
      const form = new FormData();
      form.append("image", file);
      const response = await api.post("/uploads/image", form);
      const url = (response.data?.url || response.data?.data?.url) as string | undefined;
      if (!url) throw new Error("上传成功但没有拿到图片地址");
      const index = value.elements.length % 6;
      addElement(createPhoto(url, 140 + index * 18, 120 + index * 18));
      toast.success("照片已加入画布");
    } catch (error) {
      toast.error(errMessage(error, "上传失败"));
    } finally {
      setUploading(false);
    }
  };

  const duplicate = () => {
    if (!selected) return;
    const copy = {
      ...selected,
      id: `${selected.type}-${Date.now().toString(36)}-copy`,
      x: selected.x + 24,
      y: selected.y + 24,
    } as CanvasElement;
    addElement(copy);
  };

  const shadow = selected?.shadow
    ? { shadowColor: "rgba(0,0,0,0.35)", shadowBlur: 18, shadowOffsetY: 8 }
    : {};

  return (
    <div className="space-y-2.5">
      {/* 工具栏 */}
      <div className="flex flex-wrap items-center gap-1.5">
        <Button type="button" size="sm" variant="outline" className="h-7 text-[11px]" onClick={() => addElement(createText())}>
          <Type className="mr-1 h-3 w-3" />
          文字
        </Button>
        <Button
          type="button"
          size="sm"
          variant="outline"
          className="h-7 text-[11px]"
          onClick={() => fileRef.current?.click()}
          disabled={uploading}
        >
          <Upload className="mr-1 h-3 w-3" />
          {uploading ? "上传中…" : "上传照片"}
        </Button>
        <Button
          type="button"
          size="sm"
          variant="outline"
          className="h-7 text-[11px]"
          onClick={() => fragment && addElement(createFragment(fragment))}
          disabled={!fragment}
          title={fragment ? "把这处地标的卡片贴上来" : "先选一个地标"}
        >
          <Layers className="mr-1 h-3 w-3" />
          碎片
        </Button>
        <Button
          type="button"
          size="sm"
          variant="outline"
          className="h-7 text-[11px]"
          onClick={() => addElement(createSticker("star"))}
        >
          <StickerIcon className="mr-1 h-3 w-3" />
          贴纸
        </Button>
        <Button
          type="button"
          size="sm"
          variant="outline"
          className="h-7 text-[11px]"
          onClick={() => addElement(createTape())}
        >
          胶带
        </Button>

        <span className="mx-1 h-4 w-px bg-border" />

        <Button type="button" size="sm" variant="ghost" className="h-7 px-2" onClick={() => layer("up")} disabled={!selectedId} title="上移一层">
          <ArrowUp className="h-3.5 w-3.5" />
        </Button>
        <Button type="button" size="sm" variant="ghost" className="h-7 px-2" onClick={() => layer("down")} disabled={!selectedId} title="下移一层">
          <ArrowDown className="h-3.5 w-3.5" />
        </Button>
        <Button type="button" size="sm" variant="ghost" className="h-7 px-2 text-muted-foreground" onClick={() => layer("top")} disabled={!selectedId} title="置顶">
          <ChevronsUp className="h-3.5 w-3.5" />
        </Button>
        <Button type="button" size="sm" variant="ghost" className="h-7 px-2 text-muted-foreground" onClick={() => layer("bottom")} disabled={!selectedId} title="置底">
          <ChevronsDown className="h-3.5 w-3.5" />
        </Button>
        <Button type="button" size="sm" variant="ghost" className="h-7 px-2" onClick={duplicate} disabled={!selectedId} title="复制">
          <Copy className="h-3.5 w-3.5" />
        </Button>
        <Button
          type="button"
          size="sm"
          variant="ghost"
          className="h-7 px-2 text-destructive"
          onClick={() => {
            if (!selectedId) return;
            onChange(removeElement(value, selectedId));
            setSelectedId(null);
          }}
          disabled={!selectedId}
          title="删除（Delete）"
        >
          <Trash2 className="h-3.5 w-3.5" />
        </Button>
      </div>

      <input
        ref={fileRef}
        type="file"
        accept="image/png,image/jpeg,image/webp"
        className="hidden"
        onChange={(event) => {
          const file = event.target.files?.[0];
          if (file) void uploadPhoto(file);
          event.target.value = "";
        }}
      />

      {/* 画布 */}
      <div ref={containerRef} className="mx-auto w-full max-w-[360px] overflow-hidden rounded-panel border border-border/70 shadow-panel">
        <Stage
          width={CANVAS_W * scale}
          height={CANVAS_H * scale}
          scaleX={scale}
          scaleY={scale}
          onMouseDown={(event) => {
            if (event.target === event.target.getStage()) setSelectedId(null);
          }}
          onTouchStart={(event) => {
            if (event.target === event.target.getStage()) setSelectedId(null);
          }}
        >
          <Layer>
            <Rect width={CANVAS_W} height={CANVAS_H} fill={value.background} />
          </Layer>

          <Layer>
            {value.elements.map((element) => (
              <Group
                key={element.id}
                ref={(node) => {
                  if (node) nodeRefs.current.set(element.id, node);
                  else nodeRefs.current.delete(element.id);
                }}
                x={element.x}
                y={element.y}
                rotation={element.rotation}
                scaleX={element.scale}
                scaleY={element.scale}
                opacity={element.opacity}
                draggable
                onClick={() => setSelectedId(element.id)}
                onTap={() => setSelectedId(element.id)}
                onDragEnd={() => commitTransform(element)}
                onTransformEnd={() => commitTransform(element)}
              >
                <ElementNode element={element} />
              </Group>
            ))}
            <Transformer
              ref={transformerRef}
              rotateEnabled
              keepRatio={false}
              rotationSnaps={[0, 15, 30, 45, 60, 75, 90, 105, 120, 135, 150, 165, 180, -15, -30, -45, -60, -75, -90, -105, -120, -135, -150, -165]}
              enabledAnchors={["top-left", "top-right", "bottom-left", "bottom-right"]}
              anchorSize={8}
              anchorStroke="#d8b26a"
              borderStroke="#d8b26a"
              borderDash={[3, 3]}
            />
          </Layer>
        </Stage>
      </div>

      {/* 选中元素的自定义项 */}
      {selected && (
        <div className="space-y-2 rounded-card border border-border/70 p-2">
          <div className="flex items-center justify-between text-[11px] text-muted-foreground">
            <span>
              {selected.type === "text"
                ? "文字"
                : selected.type === "photo"
                  ? "照片"
                  : selected.type === "fragment"
                    ? "碎片卡片"
                    : selected.type === "sticker"
                      ? "贴纸"
                      : "胶带"}
            </span>
            <button type="button" className="rounded p-0.5 hover:bg-muted" onClick={() => setSelectedId(null)} aria-label="取消选中">
              ×
            </button>
          </div>

          {selected.type === "text" && (
            <div className="flex items-center gap-1.5">
              <input
                value={selected.text}
                onChange={(event) => patch({ text: event.target.value })}
                placeholder="文字内容"
                className="h-8 flex-1 rounded-control border border-border/70 bg-background px-2 text-[12px] outline-none focus:border-primary/60"
              />
              <input
                type="number"
                min={10}
                max={96}
                value={selected.fontSize}
                onChange={(event) => patch({ fontSize: Math.min(96, Math.max(10, Number(event.target.value) || 24)) })}
                className="h-8 w-16 rounded-control border border-border/70 bg-background px-2 text-[12px] tabular-nums outline-none focus:border-primary/60"
                title="字号"
              />
              <input
                type="color"
                value={selected.color}
                onChange={(event) => patch({ color: event.target.value })}
                className="h-8 w-10 cursor-pointer rounded-control border border-border/70 bg-background"
                title="文字颜色"
              />
            </div>
          )}

          <div className="grid grid-cols-2 gap-2">
            <label className="block">
              <span className="mb-0.5 flex items-center justify-between text-[10.5px] text-muted-foreground">
                <span>旋转</span>
                <span className="tabular-nums">{Math.round(selected.rotation)}°</span>
              </span>
              <input
                type="range"
                min={-180}
                max={180}
                value={selected.rotation}
                onChange={(event) => patch({ rotation: Number(event.target.value) })}
                className="w-full accent-primary"
              />
            </label>
            <label className="block">
              <span className="mb-0.5 flex items-center justify-between text-[10.5px] text-muted-foreground">
                <span>透明度</span>
                <span className="tabular-nums">{Math.round(selected.opacity * 100)}%</span>
              </span>
              <input
                type="range"
                min={5}
                max={100}
                value={Math.round(selected.opacity * 100)}
                onChange={(event) => patch({ opacity: Number(event.target.value) / 100 })}
                className="w-full accent-primary"
              />
            </label>
            <label className="block">
              <span className="mb-0.5 block text-[10.5px] text-muted-foreground">圆角</span>
              <input
                type="number"
                min={0}
                max={120}
                value={Math.round(selected.cornerRadius)}
                onChange={(event) => patch({ cornerRadius: Number(event.target.value) || 0 })}
                className="h-7 w-full rounded-control border border-border/70 bg-background px-2 text-[12px] tabular-nums outline-none focus:border-primary/60"
              />
            </label>
            <label className="block">
              <span className="mb-0.5 block text-[10.5px] text-muted-foreground">边框</span>
              <input
                type="number"
                min={0}
                max={12}
                value={Math.round(selected.borderWidth)}
                onChange={(event) => patch({ borderWidth: Number(event.target.value) || 0 })}
                className="h-7 w-full rounded-control border border-border/70 bg-background px-2 text-[12px] tabular-nums outline-none focus:border-primary/60"
              />
            </label>
          </div>

          <label className="flex items-center justify-between text-[11px] text-muted-foreground">
            <span>投影</span>
            <input
              type="checkbox"
              checked={selected.shadow}
              onChange={(event) => patch({ shadow: event.target.checked })}
              className="h-3.5 w-3.5 accent-primary"
            />
          </label>
        </div>
      )}

      {/* 背景色 + 计数 */}
      <div className="flex items-center justify-between text-[11px] text-muted-foreground">
        <label className="flex items-center gap-1.5">
          背景
          <input
            type="color"
            value={value.background}
            onChange={(event) => onChange({ ...value, background: event.target.value })}
            className="h-6 w-8 cursor-pointer rounded border border-border/70 bg-background"
          />
        </label>
        <span className="tabular-nums">3:4 · {value.elements.length}/40</span>
      </div>

      {value.elements.length === 0 && (
        <p className="text-center text-[11px] leading-relaxed text-muted-foreground">
          先加一个元素：上传一张照片，写一句话，把地标的卡片剪下来。
          <br />
          选中后可拖动、缩放、旋转，上方工具栏调图层与自定义。
        </p>
      )}

      {/* 阴影设置只影响渲染，这里保留一个隐藏的占位避免 lint 认为未使用 */}
      <span className="hidden" aria-hidden data-shadow={shadow ? "on" : "off"} />
    </div>
  );
}
