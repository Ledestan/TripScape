/**
 * 行旅识景 TripScape / src/features/creation/ComposeStage
 * 创建日期: 2026-11-26
 *
 * 拼贴画布的 Konva 渲染层，完成:
 *     1. 720×960 逻辑画布，等比适配容器，支持缩放与平移查看
 *     2. 四类元素渲染：照片 / 文字 / 贴纸 / 胶带
 *     3. 选中挂 Transformer：拖拽、角点缩放、旋转（15° 吸附）
 *     4. 拖拽时吸附画布中线并显示参考线
 *     5. 导出：按 3:4 原尺寸返回 PNG（不受当前缩放/平移影响）
 *
 * 依赖:
 *     依赖库: react-konva, konva
 *
 * 用法:
 *     const stageRef = useRef<ComposeStageHandle>(null);
 *     <ComposeStage ref={stageRef} doc={doc} selectedId={id} onSelect={...} onCommit={...} />
 *     const dataUrl = stageRef.current?.exportDataUrl();
 *
 * 注意:
 *     1. 拖拽/缩放的中间态不回写文档（避免每帧重渲染），松手时由 onCommit 提交一步。
 *     2. 导出前会临时复位缩放与平移，并隐藏参考线与选中框，导出后再恢复。
 */

import { forwardRef, useEffect, useImperativeHandle, useMemo, useRef, useState } from "react";
import {
  Circle,
  Group,
  Image as KonvaImage,
  Layer,
  Line,
  Rect,
  RegularPolygon,
  Stage,
  Star,
  Text,
  Transformer,
} from "react-konva";
import type Konva from "konva";

import {
  COMPOSE_H,
  COMPOSE_W,
  type ComposeDoc,
  type ComposeElement,
  type PhotoElement,
  type TextElement,
  type StickerElement,
  type TapeElement,
} from "./types";

export interface ComposeStageHandle {
  /** 按 720×960 原尺寸导出 PNG（data URL） */
  exportDataUrl: () => string | null;
}

interface ComposeStageProps {
  doc: ComposeDoc;
  selectedId: string | null;
  onSelect: (id: string | null) => void;
  /** 变换结束时提交一步（进历史） */
  onCommit: (patch: { id: string; x: number; y: number; width: number; height: number; rotation: number }) => void;
  /** 保存中只读 */
  readOnly?: boolean;
  /** 容器尺寸（外层测量后传入），画布按 3:4 等比适配 */
  width: number;
  height: number;
}

const SNAP = 8;

/** 加载图片（没有 src 时返回 null，渲染占位） */
function useImage(src: string): HTMLImageElement | null {
  const [image, setImage] = useState<HTMLImageElement | null>(null);
  useEffect(() => {
    if (!src) {
      setImage(null);
      return;
    }
    const img = new window.Image();
    img.crossOrigin = "anonymous";
    let alive = true;
    img.onload = () => {
      if (alive) setImage(img);
    };
    img.src = src;
    return () => {
      alive = false;
      img.onload = null;
    };
  }, [src]);
  return image;
}

function PhotoNode({ element }: { element: PhotoElement }) {
  const image = useImage(element.src);
  const shadow = element.shadow
    ? { shadowColor: "rgba(0,0,0,0.28)", shadowBlur: 14, shadowOffsetY: 6, shadowOpacity: 0.5 }
    : {};
  return (
    <Group clipX={0} clipY={0} clipWidth={element.width} clipHeight={element.height}>
      <Rect
        width={element.width}
        height={element.height}
        cornerRadius={element.cornerRadius}
        fill={image ? "#1b1b1b" : "#d9d0c2"}
        stroke={element.borderWidth ? element.borderColor : undefined}
        strokeWidth={element.borderWidth}
        {...shadow}
      />
      {image ? (
        <KonvaImage
          image={image}
          width={element.width}
          height={element.height}
          cornerRadius={element.cornerRadius}
        />
      ) : (
        <>
          <Line
            points={[0, 0, element.width, element.height]}
            stroke="rgba(90,80,66,0.35)"
            strokeWidth={1}
          />
          <Line
            points={[element.width, 0, 0, element.height]}
            stroke="rgba(90,80,66,0.35)"
            strokeWidth={1}
          />
          <Text
            text="照片"
            width={element.width}
            y={element.height / 2 - 8}
            align="center"
            fontSize={13}
            fill="rgba(70,62,50,0.6)"
          />
        </>
      )}
    </Group>
  );
}

function TextNode({ element }: { element: TextElement }) {
  return (
    <Group clipX={0} clipY={0} clipWidth={element.width} clipHeight={element.height}>
      <Rect width={element.width} height={element.height} fill="transparent" />
      <Text
        text={element.text}
        width={element.width}
        fontSize={element.fontSize}
        fontFamily={element.fontFamily}
        fontStyle={element.fontStyle}
        fill={element.color}
        align={element.align}
        lineHeight={1.45}
        wrap="word"
      />
    </Group>
  );
}

function StickerNode({ element }: { element: StickerElement }) {
  const size = Math.min(element.width, element.height);
  const half = size / 2;
  if (element.variant === "circle") {
    return <Circle x={half} y={half} radius={half} fill={element.color} opacity={0.92} />;
  }
  if (element.variant === "heart") {
    return (
      <Text x={0} y={0} width={element.width} height={element.height} text="❤" fontSize={size} fill={element.color} align="center" />
    );
  }
  if (element.variant === "pin") {
    return (
      <Text x={0} y={0} width={element.width} height={element.height} text="📍" fontSize={size * 0.82} align="center" />
    );
  }
  const points = element.variant === "burst" ? 12 : 5;
  return (
    <Star
      x={half}
      y={half}
      numPoints={points}
      innerRadius={points > 6 ? half * 0.72 : half * 0.46}
      outerRadius={half}
      fill={element.color}
      opacity={0.94}
    />
  );
}

function TapeNode({ element }: { element: TapeElement }) {
  const stripes = element.pattern === "plain" ? 0 : Math.max(2, Math.floor(element.width / 26));
  return (
    <>
      <Rect
        width={element.width}
        height={element.height}
        fill={element.color}
        cornerRadius={element.cornerRadius}
        shadowColor="rgba(0,0,0,0.18)"
        shadowBlur={6}
        shadowOffsetY={2}
      />
      {Array.from({ length: stripes }).map((_, index) => (
        <Line
          key={index}
          points={
            element.pattern === "stripe"
              ? [8 + index * 26, 0, 24 + index * 26, element.height]
              : [10 + index * 26, element.height / 2, 16 + index * 26, element.height / 2]
          }
          stroke="rgba(255,255,255,0.35)"
          strokeWidth={element.pattern === "stripe" ? 4 : 3}
          dash={element.pattern === "dot" ? [2, 6] : undefined}
        />
      ))}
    </>
  );
}

export default forwardRef<ComposeStageHandle, ComposeStageProps>(function ComposeStage(
  { doc, selectedId, onSelect, onCommit, readOnly = false, width, height },
  ref
) {
  const stageRef = useRef<Konva.Stage | null>(null);
  const transformerRef = useRef<Konva.Transformer | null>(null);
  const nodes = useRef(new Map<string, Konva.Group>());
  const [zoom, setZoom] = useState(1);
  const [hand, setHand] = useState(false);
  // Shift 按住时等比缩放（用 ref 避免每帧重渲染）
  const shiftDown = useRef(false);
  useEffect(() => {
    const onDown = (event: KeyboardEvent) => {
      if (event.key === "Shift") shiftDown.current = true;
    };
    const onUp = (event: KeyboardEvent) => {
      if (event.key === "Shift") shiftDown.current = false;
    };
    const onBlur = () => {
      shiftDown.current = false;
    };
    window.addEventListener("keydown", onDown);
    window.addEventListener("keyup", onUp);
    window.addEventListener("blur", onBlur);
    return () => {
      window.removeEventListener("keydown", onDown);
      window.removeEventListener("keyup", onUp);
      window.removeEventListener("blur", onBlur);
    };
  }, []);
  const [guides, setGuides] = useState<{ x?: number; y?: number }>({});

  const fit = Math.max(0.15, Math.min((width - 8) / COMPOSE_W, (height - 8) / COMPOSE_H));
  const stageW = COMPOSE_W * fit;
  const stageH = COMPOSE_H * fit;

  const selected = useMemo(
    () => doc.elements.find((element) => element.id === selectedId) || null,
    [doc.elements, selectedId]
  );

  // Transformer 跟随选中变化（渲染后再挂，保证节点已生成）
  useEffect(() => {
    const transformer = transformerRef.current;
    if (!transformer) return;
    const node = selectedId ? nodes.current.get(selectedId) : null;
    transformer.nodes(node ? [node] : []);
    transformer.getLayer()?.batchDraw();
  }, [selectedId, doc.elements.length]);

  useImperativeHandle(ref, () => ({
    exportDataUrl: () => {
      const stage = stageRef.current;
      const transformer = transformerRef.current;
      if (!stage) return null;
      const previousScale = stage.scaleX();
      const previousPos = stage.position();
      const previousZoom = zoom;
      transformer?.nodes([]);
      setGuides({});
      stage.scale({ x: 1, y: 1 });
      stage.position({ x: 0, y: 0 });
      stage.batchDraw();
      const url = stage.toDataURL({ pixelRatio: 720 / stageW });
      stage.scale({ x: previousScale, y: previousScale });
      stage.position(previousPos);
      stage.batchDraw();
      const node = selectedId ? nodes.current.get(selectedId) : null;
      transformer?.nodes(node ? [node] : []);
      transformer?.getLayer()?.batchDraw();
      return url;
    },
  }));

  /** 拖拽时吸附中线并给出参考线 */
  const snap = (node: Konva.Group) => {
    let { x, y } = node.position();
    const cx = x + (node.width() * node.scaleX()) / 2;
    const cy = y + (node.height() * node.scaleY()) / 2;
    const nextGuides: { x?: number; y?: number } = {};
    if (Math.abs(cx - COMPOSE_W / 2) < SNAP) {
      x += COMPOSE_W / 2 - cx;
      nextGuides.x = COMPOSE_W / 2;
    }
    if (Math.abs(cy - COMPOSE_H / 2) < SNAP) {
      y += COMPOSE_H / 2 - cy;
      nextGuides.y = COMPOSE_H / 2;
    }
    node.position({ x, y });
    setGuides(nextGuides);
  };

  const commit = (element: ComposeElement) => {
    const node = nodes.current.get(element.id);
    if (!node) return;
    const scaleX = node.scaleX();
    const scaleY = node.scaleY();
    node.scaleX(1);
    node.scaleY(1);
    onCommit({
      id: element.id,
      x: Math.round(node.x()),
      y: Math.round(node.y()),
      width: Math.round(element.width * scaleX),
      height: Math.round(element.height * scaleY),
      rotation: Math.round(node.rotation()),
    });
    setGuides({});
  };

  return (
    <div className="relative">
      <Stage
        ref={stageRef}
        width={stageW}
        height={stageH}
        scaleX={fit * zoom}
        scaleY={fit * zoom}
        draggable={hand}
        onWheel={(event) => {
          event.evt.preventDefault();
          const next = zoom + (event.evt.deltaY > 0 ? -0.08 : 0.08);
          setZoom(Math.min(3, Math.max(0.5, Number(next.toFixed(2)))));
        }}
        onMouseDown={(event) => {
          if (event.target === event.target.getStage()) onSelect(null);
        }}
        onTouchStart={(event) => {
          if (event.target === event.target.getStage()) onSelect(null);
        }}
        style={{ cursor: hand ? "grab" : "default" }}
      >
        <Layer>
          <Rect width={COMPOSE_W} height={COMPOSE_H} fill={doc.background} />
          {/* 纸纹：极淡的散点，避免纯色太平 */}
          {Array.from({ length: 220 }).map((_, index) => {
            const x = (index * 97) % COMPOSE_W;
            const y = (index * 151) % COMPOSE_H;
            return <Circle key={index} x={x} y={y} radius={0.9} fill="rgba(80,64,44,0.05)" />;
          })}
        </Layer>

        <Layer>
          {doc.elements.map((element) => (
            <Group
              key={element.id}
              ref={(node) => {
                if (node) nodes.current.set(element.id, node);
                else nodes.current.delete(element.id);
              }}
              x={element.x}
              y={element.y}
              rotation={element.rotation}
              opacity={element.opacity}
              draggable={!readOnly}
              onClick={() => onSelect(element.id)}
              onTap={() => onSelect(element.id)}
              onDragMove={(event) => snap(event.target as Konva.Group)}
              onDragEnd={(event) => commit({ ...element, ...event.target.position() })}
              onTransformEnd={() => commit(element)}
            >
              {element.kind === "photo" && <PhotoNode element={element} />}
              {element.kind === "text" && <TextNode element={element} />}
              {element.kind === "sticker" && <StickerNode element={element} />}
              {element.kind === "tape" && <TapeNode element={element} />}
            </Group>
          ))}

          {guides.x !== undefined && (
            <Line points={[guides.x, 0, guides.x, COMPOSE_H]} stroke="#d8b26a" strokeWidth={1} dash={[6, 6]} />
          )}
          {guides.y !== undefined && (
            <Line points={[0, guides.y, COMPOSE_W, guides.y]} stroke="#d8b26a" strokeWidth={1} dash={[6, 6]} />
          )}

          {selected && !readOnly && (
            <Transformer
              ref={transformerRef}
              rotateEnabled
              keepRatio={false}
              boundBoxFunc={(oldBox, newBox) => {
                // 规格：默认自由缩放，按住 Shift 才等比
                if (!shiftDown.current) return newBox;
                const ratio = Math.max(0.05, oldBox.width / Math.max(1, oldBox.height));
                const width = Math.max(24, Math.abs(newBox.width));
                return { ...newBox, width, height: Math.max(24, width / ratio) };
              }}
              rotationSnaps={[0, 15, 30, 45, 60, 75, 90, 105, 120, 135, 150, 165, 180, -15, -30, -45, -60, -75, -90, -105, -120, -135, -150, -165]}
              anchorSize={9}
              anchorStroke="#b8863b"
              anchorCornerRadius={2}
              borderStroke="#b8863b"
              borderDash={[4, 4]}
              flipEnabled={false}
            />
          )}
        </Layer>
      </Stage>

      {/* 画布工具：缩放与手形平移 */}
      <div className="pointer-events-none absolute inset-x-0 -bottom-9 flex items-center justify-center">
        <div className="pointer-events-auto flex items-center gap-1 rounded-full border border-border/70 bg-card/95 px-2 py-1 text-[11px] shadow-sm">
          <button
            type="button"
            className="rounded px-1.5 py-0.5 hover:bg-muted"
            onClick={() => setZoom((z) => Math.max(0.5, Number((z - 0.1).toFixed(2))))}
            aria-label="缩小"
          >
            −
          </button>
          <span className="w-10 text-center tabular-nums">{Math.round(zoom * 100)}%</span>
          <button
            type="button"
            className="rounded px-1.5 py-0.5 hover:bg-muted"
            onClick={() => setZoom((z) => Math.min(3, Number((z + 0.1).toFixed(2))))}
            aria-label="放大"
          >
            +
          </button>
          <span className="mx-1 h-3 w-px bg-border" />
          <button
            type="button"
            className={`rounded px-1.5 py-0.5 ${hand ? "bg-primary/15 text-primary" : "hover:bg-muted"}`}
            onClick={() => setHand((value) => !value)}
            aria-pressed={hand}
            title="手形平移（也可按住空格）"
          >
            平移
          </button>
          <button
            type="button"
            className="rounded px-1.5 py-0.5 hover:bg-muted"
            onClick={() => setZoom(1)}
            title="按适应缩放"
          >
            复位
          </button>
        </div>
      </div>

      <div className="sr-only" aria-live="polite">
        {selected ? `已选中${selected.kind === "text" ? "文字" : "元素"}` : "未选中元素"}
      </div>
    </div>
  );
});
