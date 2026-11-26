/**
 * 行旅识景 TripScape / 手账画布编辑器
 * 创建日期: 2026-11-26
 *
 * 3:4 的手账版式编辑，用 react-konva 实现，完成:
 *     1. 三种元素：照片、文字、地标碎片卡片
 *     2. 选中后可拖拽、缩放、旋转（Konva Transformer）
 *     3. 图层排序：上移 / 下移 / 置顶 / 置底；可删除
 *     4. 受控组件：value 进来、onChange 出去，保存交给上层
 *
 * 依赖:
 *     依赖库: react-konva, konva, lucide-react
 *
 * 用法:
 *     <JournalCanvasEditor
 *       value={doc}
 *       onChange={setDoc}
 *       photos={images}
 *       fragment={{ title, snippet, year, landmarkId }}
 *     />
 *
 * 注意:
 *     1. 坐标一律按 720×960 逻辑画布存，渲染时整体缩放，换设备不跑版。
 *     2. 缩放用统一的 scale 折叠进元素，避免非等比拉伸把文字拉变形。
 */

import { useEffect, useMemo, useRef, useState } from "react";
import { ArrowDown, ArrowUp, ImagePlus, Layers, Trash2, Type } from "lucide-react";
import {
  Image as KonvaImage,
  Group,
  Layer,
  Rect,
  Stage,
  Text,
  Transformer,
} from "react-konva";
import type Konva from "konva";

import { Button } from "@/components/ui/button";
import {
  CANVAS_H,
  CANVAS_W,
  createFragment,
  createPhoto,
  createText,
  moveLayer,
  removeElement,
  updateElement,
  type CanvasDoc,
  type CanvasElement,
  type FragmentElement,
  type PhotoElement,
  type TextElement,
} from "./canvas-types";

/** 加载一张图片给 Konva 用（没有图片时返回 null，节点先不渲染） */
function useImage(src: string): HTMLImageElement | null {
  const [image, setImage] = useState<HTMLImageElement | null>(null);
  useEffect(() => {
    if (!src) {
      setImage(null);
      return;
    }
    const img = new window.Image();
    img.crossOrigin = "anonymous";
    img.src = src;
    const onLoad = () => setImage(img);
    img.addEventListener("load", onLoad);
    return () => img.removeEventListener("load", onLoad);
  }, [src]);
  return image;
}

/** 照片节点：按元素宽高裁切填满 */
function PhotoNode({ element }: { element: PhotoElement }) {
  const image = useImage(element.src);
  return (
    <Group clipX={0} clipY={0} clipWidth={element.width} clipHeight={element.height}>
      <Rect
        width={element.width}
        height={element.height}
        fill={element.color || "#1b1b1b"}
        cornerRadius={6}
      />
      {image && (
        <KonvaImage
          image={image}
          width={element.width}
          height={element.height}
          cornerRadius={6}
        />
      )}
    </Group>
  );
}

/** 文字节点：按框宽自动换行 */
function TextNode({ element }: { element: TextElement }) {
  return (
    <>
      <Rect width={element.width} height={element.height} fill="transparent" />
      <Text
        text={element.text}
        width={element.width}
        fontSize={element.fontSize}
        fontFamily={element.fontFamily || "serif"}
        fontStyle={element.fontStyle || "normal"}
        fill={element.color}
        align={element.align || "left"}
        lineHeight={1.5}
        wrap="word"
      />
    </>
  );
}

/** 碎片卡片节点：标题 + 摘录 + 年份，像是从档案里剪下来的一块 */
function FragmentNode({ element }: { element: FragmentElement }) {
  return (
    <>
      <Rect
        width={element.width}
        height={element.height}
        fill={element.color || "#12161d"}
        cornerRadius={10}
        stroke="rgba(216,178,106,0.55)"
        strokeWidth={1}
      />
      <Rect x={0} y={0} width={4} height={element.height} fill="#d8b26a" cornerRadius={2} />
      <Text
        x={16}
        y={14}
        width={element.width - 32}
        text={element.title}
        fontSize={18}
        fontStyle="bold"
        fontFamily="serif"
        fill="#f5f2ea"
        wrap="word"
      />
      {element.snippet ? (
        <Text
          x={16}
          y={44}
          width={element.width - 32}
          height={element.height - 72}
          text={element.snippet}
          fontSize={12}
          lineHeight={1.6}
          fill="rgba(245,242,234,0.72)"
          wrap="word"
          ellipsis
        />
      ) : null}
      {element.year ? (
        <Text
          x={16}
          y={element.height - 24}
          text={element.year}
          fontSize={11}
          fill="#d8b26a"
        />
      ) : null}
    </>
  );
}

export default function JournalCanvasEditor({
  value,
  onChange,
  photos = [],
  fragment,
}: {
  value: CanvasDoc;
  onChange: (doc: CanvasDoc) => void;
  /** 可插入的照片（手账已上传的图） */
  photos?: string[];
  /** 当前地标的碎片卡片来源 */
  fragment?: { title: string; snippet?: string; year?: string; landmarkId?: number } | null;
}) {
  const containerRef = useRef<HTMLDivElement | null>(null);
  const stageRef = useRef<Konva.Stage | null>(null);
  const transformerRef = useRef<Konva.Transformer | null>(null);
  const nodeRefs = useRef(new Map<string, Konva.Group>());
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [width, setWidth] = useState(360);

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
    if (value.elements.length >= 40) return;
    onChange({ ...value, elements: [...value.elements, element] });
    setSelectedId(element.id);
  };

  const layer = (move: "up" | "down" | "top" | "bottom") => {
    if (!selectedId) return;
    onChange(moveLayer(value, selectedId, move));
  };

  return (
    <div className="space-y-2.5">
      {/* 工具栏 */}
      <div className="flex flex-wrap items-center gap-1.5">
        <Button
          type="button"
          size="sm"
          variant="outline"
          className="h-7 text-[11px]"
          onClick={() => addElement(createText())}
        >
          <Type className="mr-1 h-3 w-3" />
          文字
        </Button>
        <Button
          type="button"
          size="sm"
          variant="outline"
          className="h-7 text-[11px]"
          onClick={() => {
            const src = photos[0] || "";
            if (!src) return;
            addElement(createPhoto(src));
          }}
          disabled={photos.length === 0}
          title={photos.length ? "插入最近上传的照片" : "先在下方上传一张照片"}
        >
          <ImagePlus className="mr-1 h-3 w-3" />
          照片
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

        <span className="mx-1 h-4 w-px bg-border" />

        <Button
          type="button"
          size="sm"
          variant="ghost"
          className="h-7 px-2"
          onClick={() => layer("up")}
          disabled={!selectedId}
          title="上移一层"
        >
          <ArrowUp className="h-3.5 w-3.5" />
        </Button>
        <Button
          type="button"
          size="sm"
          variant="ghost"
          className="h-7 px-2"
          onClick={() => layer("down")}
          disabled={!selectedId}
          title="下移一层"
        >
          <ArrowDown className="h-3.5 w-3.5" />
        </Button>
        <Button
          type="button"
          size="sm"
          variant="ghost"
          className="h-7 px-2 text-muted-foreground"
          onClick={() => layer("top")}
          disabled={!selectedId}
          title="置顶"
        >
          顶
        </Button>
        <Button
          type="button"
          size="sm"
          variant="ghost"
          className="h-7 px-2 text-muted-foreground"
          onClick={() => layer("bottom")}
          disabled={!selectedId}
          title="置底"
        >
          底
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

      {/* 画布 */}
      <div
        ref={containerRef}
        className="mx-auto w-full max-w-[360px] overflow-hidden rounded-panel border border-border/70 shadow-panel"
      >
        <Stage
          ref={stageRef}
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
                {element.type === "photo" && <PhotoNode element={element} />}
                {element.type === "text" && <TextNode element={element} />}
                {element.type === "fragment" && <FragmentNode element={element} />}
              </Group>
            ))}
            <Transformer
              ref={transformerRef}
              rotateEnabled
              keepRatio
              enabledAnchors={["top-left", "top-right", "bottom-left", "bottom-right"]}
              anchorSize={8}
              anchorStroke="#d8b26a"
              borderStroke="#d8b26a"
              borderDash={[3, 3]}
            />
          </Layer>
        </Stage>
      </div>

      {/* 选中元素的属性 */}
      {selected?.type === "text" && (
        <div className="flex items-center gap-1.5">
          <input
            value={selected.text}
            onChange={(event) =>
              onChange(updateElement(value, selected.id, { text: event.target.value }))
            }
            placeholder="文字内容"
            className="h-8 flex-1 rounded-control border border-border/70 bg-background px-2 text-[12px] outline-none focus:border-primary/60"
          />
          <input
            type="number"
            min={10}
            max={96}
            value={selected.fontSize}
            onChange={(event) =>
              onChange(
                updateElement(value, selected.id, {
                  fontSize: Math.min(96, Math.max(10, Number(event.target.value) || 24)),
                })
              )
            }
            className="h-8 w-16 rounded-control border border-border/70 bg-background px-2 text-[12px] tabular-nums outline-none focus:border-primary/60"
            title="字号"
          />
          <input
            type="color"
            value={selected.color}
            onChange={(event) =>
              onChange(updateElement(value, selected.id, { color: event.target.value }))
            }
            className="h-8 w-10 cursor-pointer rounded-control border border-border/70 bg-background"
            title="文字颜色"
          />
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
        <span className="tabular-nums">
          3:4 · {value.elements.length}/40
        </span>
      </div>

      {value.elements.length === 0 && (
        <p className="text-center text-[11px] leading-relaxed text-muted-foreground">
          先加一个元素：文字写一句话，照片贴一张图，碎片把地标的卡片剪下来。
          <br />
          选中后可拖动、缩放、旋转，右上角工具栏调图层。
        </p>
      )}
    </div>
  );
}
