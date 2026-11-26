/**
 * 行旅识景 TripScape / 旅行拼贴创作浮窗
 * 创建日期: 2026-11-26
 *
 * 叠加在地球页上的独立创作窗口，完成:
 *     1. 窗口壳：标题栏拖拽、最大化/还原、未保存关闭确认、Esc 逐层返回
 *     2. 三栏布局：左侧素材栏 / 中间 3:4 画布 / 右侧属性面板 + 图层面板
 *     3. 编辑：拖入、选中、移动、缩放、旋转、图层排序、撤销重做
 *     4. 状态：未保存圆点、保存中只读、已保存提示、错误内联条
 *     5. 保存/导出只通过回调交给宿主，窗口自己不请求接口、不落库
 *     6. 移动端：全屏底部抽屉，素材与属性改为底部面板
 *
 * 依赖:
 *     依赖库: react-konva, konva, lucide-react
 *
 * 用法:
 *     <CreationComposeWindow
 *       open={open}
 *       initialElements={elements}
 *       assetSlots={{ photos, stickers, tapes, backgrounds }}
 *       onSave={async (canvas) => { await api.post("/journals/", { canvas }); }}
 *       onExport={async () => new Blob()}
 *       onDirtyChange={(dirty) => setDirty(dirty)}
 *       onClose={() => setOpen(false)}
 *     />
 *
 * 注意:
 *     1. 画布比例固定 3:4，导出永远按 720×960 原尺寸，不受当前缩放影响。
 *     2. 窗口不承担审核语义：状态只有草稿/保存中/已保存/错误。
 */

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  ArrowDown,
  ArrowUp,
  ChevronDown,
  ChevronsDown,
  ChevronsUp,
  ImagePlus,
  Layers,
  Maximize2,
  Minimize2,
  Redo2,
  Trash2,
  Type,
  Undo2,
  Upload,
  X,
} from "lucide-react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { AssetMini, AssetThumb } from "./AssetPreview";
import { cn } from "@/utils/cn";
import { saveBlob } from "@/utils/save-file";
import ComposeStage, { type ComposeStageHandle } from "./ComposeStage";
import { useHistory } from "./useHistory";
import {
  ASSET_TABS,
  COMPOSE_TEMPLATES,
  COMPOSE_W,
  MAX_ELEMENTS,
  docSignature,
  emptyDoc,
  parseDoc,
  removeElement,
  updateElement,
  clampElement,
  createFromAsset,
  createTemplate,
  moveLayer,
  serializeDoc,
  TEXT_ASSET,
  type AssetItem,
  type AssetSlots,
  type ComposeDoc,
  type ComposeElement,
} from "./types";

export interface CreationComposeWindowProps {
  open: boolean;
  title?: string;
  initialBackground?: string;
  initialElements?: ComposeElement[];
  onClose: () => void;
  onSave?: (canvas: ComposeDoc) => Promise<void>;
  /** 发布（不传则只有保存草稿） */
  onPublish?: (canvas: ComposeDoc) => Promise<void>;
  onExport?: (canvas: ComposeDoc) => Promise<Blob>;
  onDirtyChange?: (dirty: boolean) => void;
  assetSlots?: AssetSlots;
  /** 标题栏下方由宿主注入的一栏（写手账时放标题/日期/公开开关/正文） */
  metaBar?: React.ReactNode;
  /** 上传照片：宿主负责调接口，返回可直接落进素材栏的素材 */
  onUploadPhoto?: (file: File) => Promise<AssetItem | null>;
}

type Status = "draft" | "saving" | "saved" | "error";

const STATUS_TEXT: Record<Status, string> = {
  draft: "草稿",
  saving: "保存中",
  saved: "已保存",
  error: "保存失败",
};

const STATUS_CLASS: Record<Status, string> = {
  draft: "text-muted-foreground",
  saving: "text-sky-500",
  saved: "text-emerald-500",
  error: "text-red-500",
};

export default function CreationComposeWindow({
  open,
  title = "旅行拼贴",
  initialBackground,
  initialElements,
  onClose,
  onSave,
  onPublish,
  onExport,
  onDirtyChange,
  assetSlots,
  metaBar,
  onUploadPhoto,
}: CreationComposeWindowProps) {
  const stageRef = useRef<ComposeStageHandle>(null);
  const rootRef = useRef<HTMLDivElement>(null);
  const canvasWrapRef = useRef<HTMLDivElement>(null);

  const history = useHistory<ComposeDoc>(emptyDoc(), docSignature);
  const doc = history.value;

  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [status, setStatus] = useState<Status>("draft");
  const [errorText, setErrorText] = useState("");
  const [savedAt, setSavedAt] = useState(0);
  const [confirmClose, setConfirmClose] = useState(false);
  const [maximized, setMaximized] = useState(false);
  const [mobile, setMobile] = useState(false);
  const [mobilePane, setMobilePane] = useState<"assets" | "props" | null>(null);
  const [assetTab, setAssetTab] = useState<keyof AssetSlots>("photos");
  const [uploading, setUploading] = useState(false);
  const [extraPhotos, setExtraPhotos] = useState<AssetItem[]>([]);
  const uploadRef = useRef<HTMLInputElement>(null);
  const [canvasSize, setCanvasSize] = useState({ width: 360, height: 480 });
  const [pos, setPos] = useState({ x: 0, y: 0 });
  const dragRef = useRef<{ x: number; y: number; ox: number; oy: number } | null>(null);
  const [dirty, setDirty] = useState(false);
  const savedSignature = useRef(docSignature(emptyDoc()));

  const selected = useMemo(
    () => doc.elements.find((element) => element.id === selectedId) || null,
    [doc.elements, selectedId]
  );

  // 打开时按宿主传入的内容重置历史（画布内容变化 / 重新打开都回到干净状态）
  useEffect(() => {
    if (!open) return;
    const next = parseDoc(
      { elements: initialElements || [] },
      initialBackground || emptyDoc().background
    );
    history.reset(next);
    savedSignature.current = docSignature(next);
    setStatus("draft");
    setErrorText("");
    setSelectedId(null);
    setDirty(false);
    setConfirmClose(false);
    setMobilePane(null);
    setAssetTab("photos");
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open, initialElements, initialBackground]);

  // 移动端判定
  useEffect(() => {
    if (!open) return;
    const query = window.matchMedia("(max-width: 767px)");
    const sync = () => setMobile(query.matches);
    sync();
    query.addEventListener("change", sync);
    return () => query.removeEventListener("change", sync);
  }, [open]);

  // 画布宽度跟随容器
  useEffect(() => {
    if (!open) return;
    const element = canvasWrapRef.current;
    if (!element) return;
    const observer = new ResizeObserver((entries) => {
      const rect = entries[0]?.contentRect;
      setCanvasSize({
        width: Math.max(200, Math.min(rect?.width ?? 360, 620)),
        height: Math.max(240, (rect?.height ?? 480) - 24),
      });
    });
    observer.observe(element);
    return () => observer.disconnect();
  }, [open, maximized, mobile]);

  // 脏状态回传宿主
  useEffect(() => {
    if (!open) return;
    setDirty(docSignature(doc) !== savedSignature.current);
  }, [doc, open]);

  useEffect(() => {
    onDirtyChange?.(dirty);
  }, [dirty, onDirtyChange]);

  // 已保存提示 2 秒后回到草稿态
  useEffect(() => {
    if (status !== "saved") return;
    const timer = window.setTimeout(() => setStatus("draft"), 2000);
    return () => window.clearTimeout(timer);
  }, [status, savedAt]);

  const requestClose = useCallback(() => {
    if (dirty) {
      setConfirmClose(true);
      return;
    }
    onClose();
  }, [dirty, onClose]);

  const commit = useCallback(
    (patch: { id: string; x: number; y: number; width: number; height: number; rotation: number }) => {
      const element = doc.elements.find((item) => item.id === patch.id);
      if (!element) return;
      history.apply(
        updateElement(doc, patch.id, {
          x: patch.x,
          y: patch.y,
          width: patch.width,
          height: patch.height,
          rotation: patch.rotation,
        })
      );
    },
    [doc, history]
  );

  const addElement = useCallback(
    (asset: AssetItem) => {
      if (doc.elements.length >= MAX_ELEMENTS) {
        toast.error("元素太多了，先合并或删除一部分");
        return;
      }
      const element = createFromAsset(asset, doc.elements.length);
      history.apply({
        ...doc,
        elements: [...doc.elements, { ...clampElement(element), z: doc.elements.length }],
      });
      setSelectedId(element.id);
      setMobilePane(null);
    },
    [doc, history]
  );

  const removeSelected = useCallback(() => {
    if (!selectedId) return;
    history.apply(removeElement(doc, selectedId));
    setSelectedId(null);
  }, [doc, history, selectedId]);

  const patchSelected = useCallback(
    (patch: Partial<ComposeElement>) => {
      if (!selectedId) return;
      history.apply(updateElement(doc, selectedId, patch));
    },
    [doc, history, selectedId]
  );

  const persist = useCallback(
    async (mode: "draft" | "publish") => {
      if (status === "saving") return;
      setStatus("saving");
      setErrorText("");
      const canvas = serializeDoc(doc);
      try {
        const handler = mode === "publish" ? onPublish : onSave;
        if (handler) {
          await handler(canvas);
        } else {
          // 宿主没接保存：只在本地记为已保存，避免按钮点了没反应
          await new Promise((resolve) => window.setTimeout(resolve, 200));
        }
        savedSignature.current = docSignature(canvas);
        // 保存成功后必须立刻清脏：否则退出仍提示"未保存"
        setDirty(false);
        setSavedAt(Date.now());
        setStatus("saved");
      } catch (error) {
        setStatus("error");
        setErrorText(error instanceof Error ? error.message : "保存失败，请重试");
      }
    },
    [doc, onPublish, onSave, status]
  );

  const save = useCallback(() => persist("draft"), [persist]);
  const publish = useCallback(() => persist("publish"), [persist]);

  const exportImage = useCallback(async () => {
    if (status === "saving") return;
    setStatus("saving");
    setErrorText("");
    try {
      const canvas = serializeDoc(doc);
      let blob: Blob;
      if (onExport) {
        blob = await onExport(canvas);
      } else {
        const dataUrl = stageRef.current?.exportDataUrl();
        if (!dataUrl) throw new Error("画布还没有准备好");
        blob = await (await fetch(dataUrl)).blob();
      }
      // 交给浏览器选择保存位置；用户取消时不算失败
      const filename = `tripscape-collage-${Date.now()}.png`;
      const result = await saveBlob(blob, filename);
      if (result === "cancelled") {
        setStatus("draft");
        return;
      }
      toast.success("图片已保存");
      setStatus("draft");
    } catch (error) {
      setStatus("error");
      setErrorText(error instanceof Error ? error.message : "导出失败，请重试");
    }
  }, [doc, onExport, status]);

  const clearCanvas = useCallback(() => {
    history.reset({ ...emptyDoc(doc.background), elements: [] });
    setSelectedId(null);
  }, [doc.background, history]);

  const nudge = useCallback(
    (dx: number, dy: number) => {
      if (!selected) return;
      history.apply(
        updateElement(doc, selected.id, {
          x: selected.x + dx,
          y: selected.y + dy,
        })
      );
    },
    [doc, history, selected]
  );

  // 键盘：撤销/重做、删除、微移、Esc 逐层返回、焦点循环
  useEffect(() => {
    if (!open) return;
    const onKeyDown = (event: KeyboardEvent) => {
      const target = event.target as HTMLElement | null;
      const editing = target && /^(INPUT|TEXTAREA|SELECT)$/.test(target.tagName);

      if (event.key === "Escape") {
        event.preventDefault();
        if (confirmClose) {
          setConfirmClose(false);
          return;
        }
        if (selectedId) {
          setSelectedId(null);
          return;
        }
        if (mobilePane) {
          setMobilePane(null);
          return;
        }
        requestClose();
        return;
      }

      if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === "z") {
        event.preventDefault();
        if (event.shiftKey) history.redo();
        else history.undo();
        return;
      }

      if (editing) return;

      if (event.key === "Delete" || event.key === "Backspace") {
        event.preventDefault();
        removeSelected();
        return;
      }

      const step = event.shiftKey ? 10 : 1;
      if (event.key === "ArrowLeft") nudge(-step, 0);
      if (event.key === "ArrowRight") nudge(step, 0);
      if (event.key === "ArrowUp") nudge(0, -step);
      if (event.key === "ArrowDown") nudge(0, step);
      if (["ArrowLeft", "ArrowRight", "ArrowUp", "ArrowDown"].includes(event.key)) {
        event.preventDefault();
      }

      if (event.key === "Tab") {
        const root = rootRef.current;
        if (!root) return;
        const focusable = Array.from(
          root.querySelectorAll<HTMLElement>(
            'button:not([disabled]), input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])'
          )
        ).filter((element) => element.offsetParent !== null);
        if (focusable.length === 0) return;
        const first = focusable[0];
        const last = focusable[focusable.length - 1];
        if (!event.shiftKey && document.activeElement === last) {
          event.preventDefault();
          first.focus();
        }
        if (event.shiftKey && document.activeElement === first) {
          event.preventDefault();
          last.focus();
        }
      }
    };
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [confirmClose, history, mobilePane, nudge, open, removeSelected, requestClose, selectedId]);

  // 标题栏拖拽（桌面端）
  useEffect(() => {
    if (!open) return;
    const onMove = (event: PointerEvent) => {
      const drag = dragRef.current;
      if (!drag) return;
      setPos({ x: drag.ox + event.clientX - drag.x, y: drag.oy + event.clientY - drag.y });
    };
    const onUp = () => {
      dragRef.current = null;
      document.body.style.userSelect = "";
    };
    window.addEventListener("pointermove", onMove);
    window.addEventListener("pointerup", onUp);
    return () => {
      window.removeEventListener("pointermove", onMove);
      window.removeEventListener("pointerup", onUp);
    };
  }, [open]);

  if (!open) return null;

  const assets =
    assetTab === "photos"
      ? [...extraPhotos, ...(assetSlots?.photos || [])]
      : assetSlots?.[assetTab] || [];
  const layers = [...doc.elements].reverse();

  /** 属性面板：位置 / 尺寸 / 旋转 / 透明度 / 圆角 / 阴影 / 边框 */
  const inspector = selected ? (
    <div className="space-y-3">
      <div className="flex items-center justify-between">
        <span className="text-xs font-medium text-foreground">元素属性</span>
        <button
          type="button"
          className="rounded p-1 text-muted-foreground hover:bg-muted hover:text-foreground"
          onClick={removeSelected}
          aria-label="删除元素"
        >
          <Trash2 className="h-3.5 w-3.5" />
        </button>
      </div>

      <div className="grid grid-cols-2 gap-2">
        {(
          [
            ["x", "位置 X"],
            ["y", "位置 Y"],
            ["width", "宽"],
            ["height", "高"],
          ] as const
        ).map(([key, label]) => (
          <label key={key} className="block">
            <span className="mb-1 block text-[11px] text-muted-foreground">{label}</span>
            <input
              type="number"
              value={Math.round(selected[key] as number)}
              onChange={(event) =>
                patchSelected({ [key]: Number(event.target.value) || 0 } as Partial<ComposeElement>)
              }
              className="h-7 w-full rounded-control border border-border/70 bg-background px-2 text-[12px] tabular-nums outline-none focus:border-primary/60"
            />
          </label>
        ))}
      </div>

      <label className="block">
        <span className="mb-1 flex items-center justify-between text-[11px] text-muted-foreground">
          <span>旋转</span>
          <span className="tabular-nums">{Math.round(selected.rotation)}°</span>
        </span>
        <input
          type="range"
          min={-180}
          max={180}
          value={selected.rotation}
          onChange={(event) => patchSelected({ rotation: Number(event.target.value) })}
          className="w-full accent-primary"
        />
      </label>

      <label className="block">
        <span className="mb-1 flex items-center justify-between text-[11px] text-muted-foreground">
          <span>透明度</span>
          <span className="tabular-nums">{Math.round(selected.opacity * 100)}%</span>
        </span>
        <input
          type="range"
          min={5}
          max={100}
          value={Math.round(selected.opacity * 100)}
          onChange={(event) => patchSelected({ opacity: Number(event.target.value) / 100 })}
          className="w-full accent-primary"
        />
      </label>

      <div className="grid grid-cols-3 gap-2">
        <label className="block">
          <span className="mb-1 block text-[11px] text-muted-foreground">圆角</span>
          <input
            type="number"
            min={0}
            max={120}
            value={Math.round(selected.cornerRadius)}
            onChange={(event) => patchSelected({ cornerRadius: Number(event.target.value) || 0 })}
            className="h-7 w-full rounded-control border border-border/70 bg-background px-2 text-[12px] tabular-nums outline-none focus:border-primary/60"
          />
        </label>
        <label className="block">
          <span className="mb-1 block text-[11px] text-muted-foreground">边框</span>
          <input
            type="number"
            min={0}
            max={12}
            value={Math.round(selected.borderWidth)}
            onChange={(event) => patchSelected({ borderWidth: Number(event.target.value) || 0 })}
            className="h-7 w-full rounded-control border border-border/70 bg-background px-2 text-[12px] tabular-nums outline-none focus:border-primary/60"
          />
        </label>
        <label className="block">
          <span className="mb-1 block text-[11px] text-muted-foreground">边框色</span>
          <input
            type="color"
            value={selected.borderColor}
            onChange={(event) => patchSelected({ borderColor: event.target.value })}
            className="h-7 w-full cursor-pointer rounded-control border border-border/70 bg-background"
          />
        </label>
      </div>

      <label className="flex items-center justify-between rounded-control border border-border/70 px-2 py-1.5 text-[11px]">
        <span className="text-muted-foreground">投影</span>
        <input
          type="checkbox"
          checked={selected.shadow}
          onChange={(event) => patchSelected({ shadow: event.target.checked })}
          className="h-3.5 w-3.5 accent-primary"
        />
      </label>

      {selected.kind === "text" && (
        <>
          <label className="block">
            <span className="mb-1 block text-[11px] text-muted-foreground">文字</span>
            <textarea
              value={selected.text}
              rows={3}
              onChange={(event) => patchSelected({ text: event.target.value })}
              className="w-full resize-y rounded-control border border-border/70 bg-background px-2 py-1.5 text-[12px] outline-none focus:border-primary/60"
            />
          </label>
          <div className="grid grid-cols-2 gap-2">
            <label className="block">
              <span className="mb-1 block text-[11px] text-muted-foreground">字体</span>
              <select
                value={selected.fontFamily}
                onChange={(event) => patchSelected({ fontFamily: event.target.value })}
                className="h-7 w-full rounded-control border border-border/70 bg-background px-1.5 text-[12px] outline-none focus:border-primary/60"
              >
                <option value="serif">衬线</option>
                <option value="system-ui">无衬线</option>
                <option value="cursive">手写</option>
                <option value="monospace">等宽</option>
              </select>
            </label>
            <label className="block">
              <span className="mb-1 block text-[11px] text-muted-foreground">对齐</span>
              <select
                value={selected.align}
                onChange={(event) =>
                  patchSelected({ align: event.target.value as "left" | "center" })
                }
                className="h-7 w-full rounded-control border border-border/70 bg-background px-1.5 text-[12px] outline-none focus:border-primary/60"
              >
                <option value="left">左对齐</option>
                <option value="center">居中</option>
              </select>
            </label>
          </div>
        </>
      )}

      {selected.kind === "sticker" && (
        <div className="grid grid-cols-2 gap-2">
          <label className="block">
            <span className="mb-1 block text-[11px] text-muted-foreground">贴纸样式</span>
            <select
              value={selected.variant}
              onChange={(event) =>
                patchSelected({ variant: event.target.value as typeof selected.variant })
              }
              className="h-7 w-full rounded-control border border-border/70 bg-background px-1.5 text-[12px] outline-none focus:border-primary/60"
            >
              <option value="star">星标</option>
              <option value="heart">心形</option>
              <option value="circle">圆点</option>
              <option value="pin">定位</option>
              <option value="burst">爆炸</option>
            </select>
          </label>
          <label className="block">
            <span className="mb-1 block text-[11px] text-muted-foreground">颜色</span>
            <input
              type="color"
              value={selected.color}
              onChange={(event) => patchSelected({ color: event.target.value })}
              className="h-7 w-full cursor-pointer rounded-control border border-border/70 bg-background"
            />
          </label>
        </div>
      )}

      {selected.kind === "tape" && (
        <div className="grid grid-cols-2 gap-2">
          <label className="block">
            <span className="mb-1 block text-[11px] text-muted-foreground">胶带纹理</span>
            <select
              value={selected.pattern}
              onChange={(event) =>
                patchSelected({ pattern: event.target.value as typeof selected.pattern })
              }
              className="h-7 w-full rounded-control border border-border/70 bg-background px-1.5 text-[12px] outline-none focus:border-primary/60"
            >
              <option value="plain">纯色</option>
              <option value="stripe">条纹</option>
              <option value="dot">点纹</option>
            </select>
          </label>
          <label className="block">
            <span className="mb-1 block text-[11px] text-muted-foreground">颜色</span>
            <input
              type="color"
              value={selected.color}
              onChange={(event) => patchSelected({ color: event.target.value })}
              className="h-7 w-full cursor-pointer rounded-control border border-border/70 bg-background"
            />
          </label>
        </div>
      )}

      <div className="space-y-1">
        <span className="text-[11px] text-muted-foreground">图层</span>
        <div className="flex items-center gap-1">
          <Button type="button" size="sm" variant="outline" className="h-7 flex-1 text-[11px]" onClick={() => history.apply(moveLayer(doc, selected.id, "top"))}>
            <ChevronsUp className="mr-1 h-3 w-3" />
            置顶
          </Button>
          <Button type="button" size="sm" variant="outline" className="h-7 flex-1 text-[11px]" onClick={() => history.apply(moveLayer(doc, selected.id, "up"))}>
            <ArrowUp className="mr-1 h-3 w-3" />
            上移
          </Button>
          <Button type="button" size="sm" variant="outline" className="h-7 flex-1 text-[11px]" onClick={() => history.apply(moveLayer(doc, selected.id, "down"))}>
            <ArrowDown className="mr-1 h-3 w-3" />
            下移
          </Button>
          <Button type="button" size="sm" variant="outline" className="h-7 flex-1 text-[11px]" onClick={() => history.apply(moveLayer(doc, selected.id, "bottom"))}>
            <ChevronsDown className="mr-1 h-3 w-3" />
            置底
          </Button>
        </div>
      </div>
    </div>
  ) : (
    <p className="text-[11px] leading-relaxed text-muted-foreground">
      选中一个元素后，这里可以调位置、大小、旋转、透明度、圆角、投影与图层。
    </p>
  );

  const layerList = (
    <div className="space-y-1">
      <span className="text-[11px] text-muted-foreground">图层（自上而下）</span>
      <div className="max-h-40 space-y-0.5 overflow-y-auto pr-1">
        {layers.map((element) => (
          <button
            key={element.id}
            type="button"
            onClick={() => setSelectedId(element.id)}
            className={cn(
              "flex w-full items-center justify-between rounded px-1.5 py-1 text-left text-[11px]",
              element.id === selectedId ? "bg-primary/15 text-primary" : "hover:bg-muted"
            )}
          >
            <span className="flex min-w-0 items-center gap-1.5">
              <AssetMini element={element} />
              <span className="truncate">
                {element.kind === "text"
                  ? element.text.slice(0, 12) || "文字"
                  : element.kind === "photo"
                    ? "照片"
                    : element.kind === "sticker"
                      ? "贴纸"
                      : "胶带"}
              </span>
            </span>
            <span className="ml-2 shrink-0 tabular-nums text-muted-foreground">{element.z + 1}</span>
          </button>
        ))}
        {layers.length === 0 && <p className="text-[11px] text-muted-foreground">还没有元素</p>}
      </div>
    </div>
  );

  const assetsPanel = (
    <div className="flex h-full min-h-0 flex-col">
      <div className="mb-2 grid grid-cols-2 gap-1.5">
        <Button
          type="button"
          size="sm"
          variant="outline"
          className="h-7 text-[11px]"
          onClick={() => addElement(TEXT_ASSET)}
        >
          <Type className="mr-1 h-3 w-3" />
          加文字
        </Button>
        <Button
          type="button"
          size="sm"
          variant="outline"
          className="h-7 text-[11px]"
          onClick={() => uploadRef.current?.click()}
          disabled={!onUploadPhoto || uploading}
          title={onUploadPhoto ? "上传一张照片放进素材栏" : "宿主没有开启上传"}
        >
          <Upload className="mr-1 h-3 w-3" />
          {uploading ? "上传中…" : "上传照片"}
        </Button>
      </div>

      <input
        ref={uploadRef}
        type="file"
        accept="image/png,image/jpeg,image/webp"
        className="hidden"
        onChange={async (event) => {
          const file = event.target.files?.[0];
          event.target.value = "";
          if (!file || !onUploadPhoto) return;
          setUploading(true);
          try {
            const asset = await onUploadPhoto(file);
            if (asset) {
              setExtraPhotos((photos) => [asset, ...photos]);
              setAssetTab("photos");
            }
          } catch (error) {
            toast.error(error instanceof Error ? error.message : "上传失败");
          } finally {
            setUploading(false);
          }
        }}
      />

      <div className="flex flex-wrap gap-1 border-b border-border/60 pb-2">
        {ASSET_TABS.map((tab) => (
          <button
            key={tab.key}
            type="button"
            onClick={() => setAssetTab(tab.key)}
            className={cn(
              "rounded-full px-2 py-0.5 text-[11px] transition-colors",
              assetTab === tab.key ? "bg-primary/15 text-primary" : "text-muted-foreground hover:bg-muted"
            )}
          >
            {tab.label}
          </button>
        ))}
      </div>

      <p
        className="mt-2 text-[10.5px] leading-relaxed text-muted-foreground"
        title="贴纸、胶带、纸纹都由窗口内置绘制，没有引用第三方素材"
      >
        贴纸与胶带为内置绘制，未引用第三方素材；照片由宿主注入。
      </p>

      <div className="min-h-0 flex-1 overflow-y-auto pt-2">
        {assets.length === 0 ? (
          <p className="py-6 text-center text-[11px] leading-relaxed text-muted-foreground">
            这一类还没有素材
            <br />
            宿主没有注入时这里保持空态
          </p>
        ) : (
          <div className="grid grid-cols-2 gap-2">
            {assets.map((asset) => (
              <button
                key={asset.id}
                type="button"
                draggable
                onDragStart={(event) => {
                  event.dataTransfer.setData("text/tripscape-asset", asset.id);
                  event.dataTransfer.effectAllowed = "copy";
                }}
                onClick={() => {
                  if (asset.kind === "background") {
                    history.apply({ ...doc, background: asset.color || doc.background });
                    return;
                  }
                  addElement(asset);
                }}
                className="group overflow-hidden rounded-card border border-border/70 bg-background text-left transition hover:border-primary/50"
              >
                <div className="flex h-16 items-center justify-center overflow-hidden bg-muted">
                  <AssetThumb asset={asset} />
                </div>
                <div className="truncate px-1.5 py-1 text-[11px] text-muted-foreground group-hover:text-foreground">
                  {asset.label}
                </div>
              </button>
            ))}
          </div>
        )}
      </div>
    </div>
  );

  return (
    <div
      className="fixed inset-0 z-[45] flex items-center justify-center bg-black/35 p-4 motion-reduce:transition-none"
      onMouseDown={(event) => {
        if (event.target === event.currentTarget) requestClose();
      }}
    >
      <div
        ref={rootRef}
        role="dialog"
        aria-modal="true"
        aria-label={`${title}创作浮窗`}
        className={cn(
          "flex flex-col overflow-hidden border border-border/70 bg-card text-card-foreground shadow-panel",
          "animate-in fade-in zoom-in-95 duration-150 motion-reduce:animate-none",
          mobile ? "fixed inset-0 rounded-none" : "rounded-panel"
        )}
        style={
          mobile
            ? undefined
            : {
                width: "min(1080px, 92vw)",
                height: "min(720px, 88vh)",
                minWidth: 720,
                minHeight: 520,
                transform: `translate(${pos.x}px, ${pos.y}px)`,
                ...(maximized ? { width: "calc(100vw - 32px)", height: "calc(100vh - 32px)" } : {}),
              }
        }
      >
        {/* 标题栏 */}
        <header
          className="flex h-11 shrink-0 cursor-move items-center justify-between border-b border-border/70 px-3"
          onPointerDown={(event) => {
            if (mobile) return;
            if ((event.target as HTMLElement).closest("button")) return;
            dragRef.current = { x: event.clientX, y: event.clientY, ox: pos.x, oy: pos.y };
            document.body.style.userSelect = "none";
          }}
        >
          <div className="flex min-w-0 items-center gap-2">
            <span className="truncate text-[13px] font-medium">{title}</span>
            {dirty && (
              <span
                data-testid="compose-dirty-dot"
                className="h-1.5 w-1.5 rounded-full bg-amber-500"
                aria-label="有未保存修改"
              />
            )}
            <span className={cn("text-[11px]", STATUS_CLASS[status])}>{STATUS_TEXT[status]}</span>
            <span className="text-[11px] text-muted-foreground">
              {doc.elements.length}/{MAX_ELEMENTS} · 3:4
            </span>
          </div>

          <div className="flex items-center gap-0.5">
            <button
              type="button"
              className="rounded p-1.5 text-muted-foreground hover:bg-muted hover:text-foreground disabled:opacity-40"
              onClick={() => history.undo()}
              disabled={!history.canUndo}
              title="撤销（Ctrl/Cmd+Z）"
              aria-label="撤销"
            >
              <Undo2 className="h-3.5 w-3.5" />
            </button>
            <button
              type="button"
              className="rounded p-1.5 text-muted-foreground hover:bg-muted hover:text-foreground disabled:opacity-40"
              onClick={() => history.redo()}
              disabled={!history.canRedo}
              title="重做（Ctrl/Cmd+Shift+Z）"
              aria-label="重做"
            >
              <Redo2 className="h-3.5 w-3.5" />
            </button>
            {!mobile && (
              <button
                type="button"
                className="rounded p-1.5 text-muted-foreground hover:bg-muted hover:text-foreground"
                onClick={() => setMaximized((value) => !value)}
                title={maximized ? "还原" : "最大化"}
                aria-label={maximized ? "还原窗口" : "最大化窗口"}
              >
                {maximized ? <Minimize2 className="h-3.5 w-3.5" /> : <Maximize2 className="h-3.5 w-3.5" />}
              </button>
            )}
            <button
              type="button"
              className="rounded p-1.5 text-muted-foreground hover:bg-muted hover:text-foreground"
              onClick={requestClose}
              aria-label="关闭创作浮窗"
            >
              <X className="h-3.5 w-3.5" />
            </button>
          </div>
        </header>

        {/* 宿主注入的一栏：写手账时放标题 / 日期 / 公开开关 / 正文 */}
        {metaBar && <div className="shrink-0 border-b border-border/70 px-3 py-2">{metaBar}</div>}

        {/* 错误条 */}
        {status === "error" && (
          <div className="flex items-center justify-between gap-2 border-b border-red-500/30 bg-red-500/10 px-3 py-1.5 text-[11px] text-red-500">
            <span className="truncate">{errorText || "操作失败"}</span>
            <div className="flex shrink-0 gap-1">
              <button type="button" className="rounded px-1.5 py-0.5 hover:bg-red-500/15" onClick={save}>
                重试
              </button>
              <button type="button" className="rounded px-1.5 py-0.5 hover:bg-red-500/15" onClick={() => setStatus("draft")}>
                关闭
              </button>
            </div>
          </div>
        )}

        {/* 主体三栏 */}
        <div className="flex min-h-0 flex-1">
          {!mobile && (
            <aside className="flex w-[212px] shrink-0 flex-col border-r border-border/70 p-2.5">{assetsPanel}</aside>
          )}

          <div className="flex min-w-0 flex-1 flex-col">
            <div
              ref={canvasWrapRef}
              className="flex min-h-0 flex-1 items-center justify-center overflow-auto p-3"
              onDragOver={(event) => event.preventDefault()}
              onDrop={(event) => {
                event.preventDefault();
                const id = event.dataTransfer.getData("text/tripscape-asset");
                const asset = (assetSlots?.[assetTab] || []).find((item) => item.id === id);
                if (asset) addElement(asset);
              }}
            >
              {doc.elements.length === 0 ? (
                <div className="flex w-full max-w-[420px] flex-col items-center gap-3 text-center">
                  <p className="text-[12px] leading-relaxed text-muted-foreground">
                    从左侧拖入照片，或先加一段文字
                    <br />
                    也可以先套一个模板
                  </p>
                  <div className="grid w-full gap-1.5">
                    {COMPOSE_TEMPLATES.map((template) => (
                      <button
                        key={template.id}
                        type="button"
                        onClick={() => {
                          history.reset(createTemplate(template.id));
                          setSelectedId(null);
                        }}
                        className="flex items-center justify-between rounded-card border border-border/70 px-3 py-2 text-left transition hover:border-primary/50"
                      >
                        <span>
                          <span className="block text-[12px] text-foreground">{template.name}</span>
                          <span className="block text-[11px] text-muted-foreground">{template.description}</span>
                        </span>
                        <span className="text-[11px] text-primary">套用</span>
                      </button>
                    ))}
                  </div>
                </div>
              ) : (
                <ComposeStage
                  ref={stageRef}
                  doc={doc}
                  selectedId={selectedId}
                  onSelect={setSelectedId}
                  onCommit={commit}
                  readOnly={status === "saving"}
                  width={canvasSize.width}
                  height={canvasSize.height}
                />
              )}
            </div>
          </div>

          {!mobile && (
            <aside className="flex w-[248px] shrink-0 flex-col gap-3 overflow-y-auto border-l border-border/70 p-2.5">
              {inspector}
              <div className="border-t border-border/60 pt-3">{layerList}</div>
            </aside>
          )}
        </div>

        {/* 移动端底部面板 */}
        {mobile && (
          <div className="shrink-0 border-t border-border/70">
            <div className="flex items-center justify-around py-1.5">
              {(
                [
                  ["assets", "素材"],
                  ["props", "属性"],
                ] as const
              ).map(([key, label]) => (
                <button
                  key={key}
                  type="button"
                  onClick={() => setMobilePane((value) => (value === key ? null : key))}
                  className={cn(
                    "rounded px-3 py-1 text-[12px]",
                    mobilePane === key ? "bg-primary/15 text-primary" : "text-muted-foreground"
                  )}
                >
                  {label}
                  <ChevronDown className={cn("ml-1 inline h-3 w-3 transition-transform", mobilePane === key && "rotate-180")} />
                </button>
              ))}
            </div>
            {mobilePane && (
              <div className="max-h-[38vh] overflow-y-auto border-t border-border/60 p-2.5">
                {mobilePane === "assets" ? assetsPanel : <div className="space-y-3">{inspector}{layerList}</div>}
              </div>
            )}
          </div>
        )}

        {/* 底部动作栏 */}
        <footer className="flex h-11 shrink-0 items-center justify-between border-t border-border/70 px-3">
          <div className="flex items-center gap-1.5">
            {onPublish ? (
              <>
                <Button size="sm" className="h-7 text-[11px]" onClick={publish} disabled={status === "saving"}>
                  {status === "saving" ? "发布中…" : "发布"}
                </Button>
                <Button
                  size="sm"
                  variant="outline"
                  className="h-7 text-[11px]"
                  onClick={save}
                  disabled={status === "saving"}
                  data-testid="compose-save-draft"
                >
                  存草稿
                </Button>
              </>
            ) : (
              <Button size="sm" className="h-7 text-[11px]" onClick={save} disabled={status === "saving"}>
                {status === "saving" ? "保存中…" : "保存草稿"}
              </Button>
            )}
            <Button size="sm" variant="outline" className="h-7 text-[11px]" onClick={exportImage} disabled={status === "saving"}>
              导出图片
            </Button>
            <Button size="sm" variant="ghost" className="h-7 text-[11px] text-muted-foreground" onClick={clearCanvas}>
              清空画布
            </Button>
          </div>
          <div className="flex items-center gap-1.5">
            <Button size="sm" variant="ghost" className="h-7 text-[11px]" onClick={requestClose}>
              关闭
            </Button>
          </div>
        </footer>

        {/* 未保存关闭确认 */}
        {confirmClose && (
          <div className="absolute inset-0 z-10 flex items-center justify-center bg-black/40 p-4">
            <div className="w-full max-w-sm rounded-panel border border-border/70 bg-card p-4 shadow-panel">
              <p className="text-[13px] font-medium">还有未保存的修改</p>
              <p className="mt-1 text-[11px] leading-relaxed text-muted-foreground">
                保存后会交给宿主处理；放弃则这次拼贴不会留下记录。
              </p>
              <div className="mt-3 flex justify-end gap-1.5">
                <Button size="sm" variant="ghost" className="h-7 text-[11px]" onClick={() => setConfirmClose(false)}>
                  继续编辑
                </Button>
                <Button
                  size="sm"
                  variant="outline"
                  className="h-7 text-[11px]"
                  onClick={() => {
                    setConfirmClose(false);
                    onClose();
                  }}
                >
                  放弃修改
                </Button>
                <Button
                  size="sm"
                  className="h-7 text-[11px]"
                  onClick={async () => {
                    await save();
                    setConfirmClose(false);
                    onClose();
                  }}
                  disabled={status === "saving"}
                >
                  保存草稿
                </Button>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
