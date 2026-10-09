import { useEffect, useMemo, useRef, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { toast } from "sonner";
import {
  ImagePlus, Send, X, Search as SearchIcon, MapPin, NotebookPen, Compass, History, MessageSquare, Bell, Check,
} from "lucide-react";

import { api, errMessage } from "@/api/client";
import { FloatingWindow } from "@/components/FloatingWindow";
import { useChatStore, ChatMessage } from "@/stores/chat";
import { useAuthStore } from "@/stores/auth";
import { globeBus } from "@/features/globe/Globe";

/* ------------------------------------------------------------------ */
/* 识别结果卡（识别图 + 百科图 + 介绍 + 操作按钮 + 候选）                */
/* ------------------------------------------------------------------ */
export function RecognitionResultCard({
  msg,
  onFly,
}: {
  msg: ChatMessage;
  onFly?: (lmId: number) => void;
}) {
  const m = msg as ChatMessage & {
    landmark_id?: number;
    candidates?: { landmark_id: number; name: string; confidence: number; image_url: string }[];
    low_confidence?: boolean;
  };

  return (
    <div className="w-full self-start rounded-2xl border border-border/50 bg-muted/50 p-2.5 text-foreground shadow-sm">
      {/* 识别结果行：地标名（含置信度数字） */}
      <div className="flex items-center justify-between">
        <span className="text-[var(--ui-fs)] font-medium">{m.content}</span>
        {m.confidence !== undefined && (
          <span className="rounded-full bg-muted px-2 py-0.5 text-[10px]">
            置信度 {Math.round(m.confidence * 100)}%
          </span>
        )}
      </div>

      {m.confidence !== undefined && (
        <div className="mt-2 h-1.5 w-full overflow-hidden rounded-full bg-muted">
          <div
            className="h-full rounded-full bg-gradient-to-r from-amber-400 to-sky-400"
            style={{ width: `${Math.min(100, Math.round(m.confidence * 100))}%` }}
          />
        </div>
      )}

      {/* 纯图片识别：小百科（intro）；图+文：问答引擎的回答 */}
      {m.intro && (
        <p className="mt-2 text-[var(--ui-fs-sm)] leading-relaxed text-foreground/60">{m.intro}</p>
      )}
      {m.qa_answer && (
        <div className="mt-2 rounded-xl bg-background/60 p-2.5">
          <div className="mb-1 flex items-center gap-1 text-[10px] font-medium text-foreground/50">
            <MessageSquare className="h-3 w-3" /> 回答
          </div>
          <p className="text-[var(--ui-fs-sm)] leading-relaxed">{m.qa_answer}</p>
        </div>
      )}

      {/* 关联地标行：小按钮弹详情浮窗（详情内有飞过去/写手账） */}
      {m.landmark_ids && m.landmark_ids.length > 0 && (
        <div className="mt-2.5 flex flex-wrap items-center gap-1.5 border-t border-border/40 pt-2">
          <span className="text-[10px] text-foreground/50">关联地标</span>
          {m.landmark_ids.map((id, i) => (
            <button
              key={id}
              onClick={() => window.dispatchEvent(new CustomEvent("ts:open-detail", { detail: id }))}
              className="flex items-center gap-1 rounded-lg bg-muted px-2 py-0.5 text-[var(--ui-fs-sm)] transition hover:bg-accent"
              title={m.landmark_names?.[i] || "地标详情"}
            >
              <MapPin className="h-3 w-3" />
              {m.landmark_names?.[i] || "详情"}
            </button>
          ))}
        </div>
      )}

      {m.low_confidence && m.candidates && m.candidates.length > 0 && (
        <div className="mt-2.5 rounded-xl border border-amber-400/25 bg-amber-400/5 p-2">
          <div className="text-[11px] font-medium text-amber-200/90">置信度较低，可能是这些地标：</div>
          <div className="mt-1.5 space-y-1">
            {m.candidates.map((c) => (
              <button
                key={c.landmark_id}
                onClick={() => window.dispatchEvent(new CustomEvent("ts:open-detail", { detail: c.landmark_id }))}
                className="flex w-full items-center gap-2 rounded-lg px-2 py-1 text-left transition hover:bg-muted"
              >
                {c.image_url ? (
                  <img src={c.image_url} alt="" className="h-7 w-7 rounded-md object-cover" />
                ) : (
                  <div className="flex h-7 w-7 items-center justify-center rounded-md bg-muted">
                    <MapPin className="h-3 w-3" />
                  </div>
                )}
                <span className="flex-1 text-[var(--ui-fs-sm)]">{c.name}</span>
                <span className="text-[10px] text-foreground/50">{Math.round(c.confidence * 100)}%</span>
              </button>
            ))}
          </div>
          <Link
            to="/search"
            className="mt-1.5 flex items-center justify-center gap-1 rounded-lg bg-muted py-1 text-[11px] transition hover:bg-accent"
          >
            <SearchIcon className="h-3 w-3" /> 手动搜索确认
          </Link>
        </div>
      )}
    </div>
  );
}

/** 识别中骨架屏 */
export function RecognizingSkeleton() {
  return (
    <div className="w-full self-start rounded-2xl border border-border/50 bg-muted/50 p-2.5">
      <div className="flex items-center gap-2">
        <span className="h-2 w-2 animate-ping rounded-full bg-sky-400" />
        <span className="text-[var(--ui-fs-sm)] text-foreground/60">正在识别图片，请稍候…</span>
      </div>
      <div className="mt-2.5 grid grid-cols-2 gap-2">
        <div className="h-[9vw] max-h-24 animate-pulse rounded-lg bg-muted" />
        <div className="h-[9vw] max-h-24 animate-pulse rounded-lg bg-muted" style={{ animationDelay: "0.15s" }} />
      </div>
      <div className="mt-2 h-1.5 w-full animate-pulse rounded-full bg-muted" />
      <div className="mt-1.5 h-1.5 w-2/3 animate-pulse rounded-full bg-muted" />
    </div>
  );
}

/* ------------------------------------------------------------------ */
/* 消息栏：默认通知条 / 展开会话浮窗                                    */
/* ------------------------------------------------------------------ */
export default function MessageBar({
  spots,
  onFly,
  compact,
  narrow,
}: {
  spots?: { id: number; name: string; lat: number; lon: number }[];
  onFly?: (lmId: number) => void;
  compact?: boolean;
  narrow?: boolean;
}) {
  const { messages, addMessage, updateMessage, sessionId } = useChatStore();
  const token = useAuthStore((s) => s.token);
  const [open, setOpen] = useState(false);
  const [historyOpen, setHistoryOpen] = useState(false);
  const [viewMsg, setViewMsg] = useState<ChatMessage | null>(null);
  const [tab, setTab] = useState<"qa" | "notifications">("qa");
  const [input, setInput] = useState("");
  const [file, setFile] = useState<File | null>(null);
  const [sending, setSending] = useState(false);
  const fileRef = useRef<HTMLInputElement>(null);
  const flowRef = useRef<HTMLDivElement>(null);
  const [previewUrl, setPreviewUrl] = useState<string | null>(null);

  // 未读通知（收起态预览 & 通知角标）
  const { data: unreadData, refetch: refetchUnread } = useQuery({
    queryKey: ["notifications", "unread"],
    queryFn: async () => (await api.get("/notifications/unread")).data as { count: number },
    enabled: !!token,
    refetchInterval: 30_000,
  });
  const unreadCount = unreadData?.count ?? 0;

  // 最新未读（按时间正序第一个未读，即最早的未读）
  const { data: notifList } = useQuery({
    queryKey: ["notifications", "preview"],
    queryFn: async () =>
      (await api.get("/notifications/", { params: { page_size: 10 } })).data.data as {
        id: number;
        title: string;
        is_read: boolean;
      }[],
    enabled: !!token && unreadCount > 0,
    refetchInterval: 30_000,
  });
  const latestUnread = useMemo(
    () => [...(notifList || [])].reverse().find((n) => !n.is_read),
    [notifList]
  );

  useEffect(() => {
    flowRef.current?.scrollTo({ top: flowRef.current.scrollHeight, behavior: "smooth" });
  }, [messages, open]);

  useEffect(() => {
    if (!file) {
      setPreviewUrl(null);
      return;
    }
    const url = URL.createObjectURL(file);
    setPreviewUrl(url);
    return () => URL.revokeObjectURL(url);
  }, [file]);

  const chat = useMutation({
    mutationFn: async (question: string) =>
      (await api.post("/qa/chat", { question, session_id: sessionId })).data as {
        answer: string;
        known: boolean;
        confidence: number;
        landmark: { id: number; name: string; image_url: string; intro: string; lat: number; lon: number } | null;
        landmarks?: { id: number; name: string }[];
      },
    onSuccess: (data) => {
      const lms = (data as any).landmarks?.filter(Boolean) ?? (data.landmark ? [data.landmark] : []);
      addMessage({
        role: "bot",
        content: data.answer,
        // 问答结果不带小百科（intro/百科图）；关联地标改走底部地标行
        landmark_id: data.landmark?.id,
        landmark_ids: lms.map((x: any) => x.id),
        landmark_names: lms.map((x: any) => x.name),
        lat: data.landmark?.lat,
        lon: data.landmark?.lon,
      });
    },
    onError: (e) => addMessage({ role: "bot", content: `请求失败：${errMessage(e)}` }),
  });

  const recognize = useMutation({
    mutationFn: async (image: File) => {
      const form = new FormData();
      form.append("image", image);
      return (await api.post("/recognition/recognize", form)).data as {
        success: boolean;
        message?: string;
        name?: string;
        confidence?: number;
        image_url?: string;
        intro?: string;
        landmark_id?: number;
        low_confidence?: boolean;
        candidates?: { landmark_id: number; name: string; confidence: number; image_url: string }[];
      };
    },
  });

  const flyToLandmark = (lmId: number) => {
    const s = spots?.find((x) => x.id === lmId);
    if (s) globeBus.flyTo(s.lat, s.lon, s.id);
    onFly?.(lmId);
  };

  const handleSend = async () => {
    const text = input.trim();
    if ((!text && !file) || sending) return;
    if (file && !token) {
      toast.error("请先登录后再上传图片识别");
      return;
    }
    setSending(true);
    const currentFile = file;
    const currentPreview = previewUrl;

    // 用户消息：文字 +（如有）上传图预览；[图片] 标记不再注入文字
    addMessage({
      role: "user",
      content: text,
      pending_image_url: currentPreview || undefined,
    });

    const pendingId = `pending-${Date.now()}`;
    setInput("");
    setFile(null);
    if (fileRef.current) fileRef.current.value = "";

    try {
      if (currentFile) {
        addMessage({
          id: pendingId,
          role: "bot",
          content: "",
          pending: true,
        });
        const res = await recognize.mutateAsync(currentFile);

        // 纯图片：显示识别结果 + 小百科；图片+文字：识别结果 + 置信度 + 问题回答
        const withQuestion = !!text;
        let answerText = "";
        let qaLandmarkIds: number[] | undefined;
        let qaLandmarkNames: string[] | undefined;
        if (withQuestion && res.success) {
          // 组合消息的问答走原始 API（不经 chat mutation 的 onSuccess，
          // 否则会多弹出一条独立 bot 消息 -> 出现"两个框"）
          try {
            const qa = (
              await api.post("/qa/chat", { question: text, session_id: sessionId })
            ).data as {
              answer: string;
              known: boolean;
              landmarks?: { id: number; name: string }[];
            };
            if (qa.known) {
              answerText = qa.answer;
              const lms = qa.landmarks ?? [];
              qaLandmarkIds = lms.map((x) => x.id);
              qaLandmarkNames = lms.map((x) => x.name);
            }
          } catch {
            // 问答失败不影响识别结果展示
          }
        }

        updateMessage(pendingId, {
          pending: false,
          content: res.success
            ? `${res.name}（${Math.round((res.confidence || 0) * 100)}%）`
            : res.message || "识别失败",
          // 纯图片才带小百科（intro）；带问题时用问答答案替代
          intro: withQuestion ? undefined : res.intro?.slice(0, 150) + (res.intro && res.intro.length > 150 ? "…" : ""),
          qa_answer: withQuestion ? answerText || undefined : undefined,
          image_url: undefined,  // 不显示识别图（百科图），上传图在用户消息侧展示
          confidence: res.confidence,
          // 关联地标：识别地标 + 问答回答的地标（去重）
          landmark_ids: [res.landmark_id, ...(qaLandmarkIds ?? [])].filter(
            (x, i, arr): x is number => x !== undefined && arr.indexOf(x) === i
          ),
          landmark_names: [res.success ? res.name ?? "" : "", ...(qaLandmarkNames ?? [])].filter(
            (x, i, arr): x is string => x !== "" && arr.indexOf(x) === i
          ),
          landmark_id: res.landmark_id,
          low_confidence: res.low_confidence,
          candidates: res.candidates,
        });
      } else if (text) {
        await chat.mutateAsync(text);
      }
    } finally {
      setSending(false);
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  const isResultCard = (m: ChatMessage) =>
    m.landmark_id !== undefined || m.low_confidence !== undefined || !!m.pending_image_url;

  const lastText = [...messages].reverse().find((m) => !m.pending)?.content ?? "问我地标知识，或拖一张照片来识别";

  /* ---------- 消息查看浮窗 ---------- */
  const viewMsgWindow = viewMsg ? (
    <FloatingWindow
      open
      onClose={() => setViewMsg(null)}
      title={viewMsg.role === "user" ? "我的消息" : "AI 回答"}
      width={420}
      fixedHeight="min(56vh, 480px)"
    >
      <div className="space-y-3">
        {viewMsg.role === "user" ? (
          <div className="rounded-xl bg-primary px-3.5 py-2 text-sm text-primary-foreground">{viewMsg.content}</div>
        ) : (
          <>
            <div className="whitespace-pre-wrap break-words text-sm leading-relaxed">{viewMsg.content}</div>
            {viewMsg.pending_image_url && (
              <img src={viewMsg.pending_image_url} alt="" className="max-h-60 w-full rounded-xl object-contain" />
            )}
            {viewMsg.image_url && (
              <img src={viewMsg.image_url} alt="" className="max-h-60 w-full rounded-xl object-contain" />
            )}
            {viewMsg.intro && <p className="text-sm leading-relaxed text-muted-foreground">{viewMsg.intro}</p>}
            {viewMsg.confidence !== undefined && (
              <div>
                <div className="h-1.5 w-full overflow-hidden rounded-full bg-muted">
                  <div
                    className="h-full rounded-full bg-gradient-to-r from-amber-400 to-primary"
                    style={{ width: `${Math.min(100, Math.round(viewMsg.confidence * 100))}%` }}
                  />
                </div>
                <div className="mt-1 flex justify-between text-[11px] text-muted-foreground">
                  <span>识别可信度</span>
                  <span>{Math.round(viewMsg.confidence * 100)}%</span>
                </div>
              </div>
            )}
          </>
        )}
      </div>
    </FloatingWindow>
  ) : null;

  /* ---------- 历史会话浮窗 ---------- */
  const historyWindow = historyOpen ? (
    <FloatingWindow open onClose={() => setHistoryOpen(false)} title="历史会话" width={440} fixedHeight="min(60vh, 540px)">
      <HistoryList />
    </FloatingWindow>
  ) : null;

  /* ---------- 收起态：无未读=圆形图标；有未读=拉长预览条 ---------- */
  if (!open) {
    const hasUnread = !!latestUnread;
    return (
      <button
        onClick={() => {
          setOpen(true);
          setTab(hasUnread ? "notifications" : "qa");
        }}
        className={`group flex items-center gap-2 overflow-hidden rounded-full border border-border/70 bg-card text-foreground shadow-md transition hover:bg-accent ${
          hasUnread && !narrow ? "pl-3.5 pr-4" : "justify-center"
        }`}
        style={{
          height: "var(--icon-btn)",
          width: hasUnread && !narrow ? "var(--ui-strip-w)" : "var(--icon-btn)",
          maxWidth: hasUnread && !narrow ? "var(--ui-strip-w)" : undefined,
        }}
        title={hasUnread ? "有未读通知" : "智能问答"}
      >
        {historyWindow}
        {viewMsgWindow}
        <div className="relative shrink-0">
          <Bell className="h-5 w-5 text-primary" />
          {hasUnread && (
            <span className="absolute -right-1.5 -top-1.5 flex h-3.5 min-w-3.5 items-center justify-center rounded-full bg-red-500 px-0.5 text-[9px] font-bold text-white">
              {unreadCount > 99 ? "99+" : unreadCount}
            </span>
          )}
        </div>
        {hasUnread && !narrow && (
          <span className="min-w-0 flex-1 truncate text-left text-[var(--ui-fs-sm)] text-foreground/75">
            {latestUnread!.title}
          </span>
        )}
      </button>
    );
  }

  /* ---------- 展开态：问答 / 通知 双 Tab 浮窗（固定尺寸，不随 Tab 变） ---------- */
  return (
    <div
      className="flex h-[46vh] flex-col overflow-hidden rounded-[var(--ui-radius)] border border-border/70 bg-card text-card-foreground shadow-xl"
      style={{
        width: "min(var(--ui-panel-max), 34vw)",
        fontSize: "var(--ui-fs)",
      }}
    >
      {/* 头部：问答 / 通知 双 Tab */}
      <div className="flex h-11 shrink-0 items-center justify-between border-b border-border/50 pl-2 pr-2">
        <div className="flex items-center gap-1">
          {(["qa", "notifications"] as const).map((t) => (
            <button
              key={t}
              onClick={() => setTab(t)}
              className={`relative flex items-center gap-1.5 rounded-lg px-2.5 py-1.5 text-sm font-medium transition ${
                tab === t
                  ? "bg-muted text-foreground"
                  : "text-muted-foreground hover:text-foreground"
              }`}
            >
              {t === "qa" ? <MessageSquare className="h-3.5 w-3.5" /> : <Bell className="h-3.5 w-3.5" />}
              {t === "qa" ? "问答" : "通知"}
              {t === "notifications" && unreadCount > 0 && (
                <span className="flex h-4 min-w-4 items-center justify-center rounded-full bg-red-500 px-1 text-[9px] font-bold text-white">
                  {unreadCount > 99 ? "99+" : unreadCount}
                </span>
              )}
            </button>
          ))}
        </div>
        <div className="flex items-center gap-1">
          {tab === "qa" && (
            <button
              onClick={() => setHistoryOpen(true)}
              className="flex items-center gap-1 rounded-lg px-2 py-1 text-[var(--ui-fs-sm)] text-muted-foreground transition hover:bg-muted hover:text-foreground"
              title="历史会话"
            >
              <History className="h-3.5 w-3.5" />
              {!narrow && "历史"}
            </button>
          )}
          <button
            onClick={() => setOpen(false)}
            className="rounded-lg p-1.5 text-muted-foreground transition hover:bg-muted hover:text-foreground"
            title="收起"
          >
            <X className="h-4 w-4" />
          </button>
        </div>
      </div>

      {/* 通知 Tab：全部 / 未读 两块 */}
      {tab === "notifications" && (
        <NotificationTab token={token} onRead={() => refetchUnread()} />
      )}

      {/* 问答 Tab：会话流 + 输入 */}
      {tab === "qa" && (
      <>

      {/* 会话流（当前会话不分页） */}
      <div ref={flowRef} className="flex flex-1 flex-col gap-2 overflow-y-auto px-3 py-3">
        {messages.length === 0 ? (
          <div className="flex flex-1 flex-col items-center justify-center gap-1.5 py-6 text-center">
            <div className="flex h-11 w-11 items-center justify-center rounded-full bg-muted">
              <MapPin className="h-5 w-5 text-white" />
            </div>
            <div className="text-[var(--ui-fs)] font-medium text-foreground">行旅识景</div>
            <div className="text-[var(--ui-fs-sm)] text-foreground/50">问我地标知识 · 或拖一张照片来识别</div>
          </div>
        ) : (
          messages.map((m) =>
            m.pending ? (
              <RecognizingSkeleton key={m.id} />
            ) : m.role === "user" ? (
              <div
                key={m.id}
                className="flex max-w-[85%] cursor-pointer flex-col gap-1.5 self-end"
                onClick={() => setViewMsg(m)}
                title="点击查看全文"
              >
                {m.pending_image_url && (
                  <img
                    src={m.pending_image_url}
                    alt=""
                    className="ml-auto max-h-32 w-auto rounded-2xl rounded-br-sm object-cover"
                  />
                )}
                {m.content && (
                  <div className="self-end rounded-2xl rounded-br-sm bg-sky-500 px-3 py-1.5 text-[var(--ui-fs)] text-foreground">
                    {m.content}
                  </div>
                )}
              </div>
            ) : isResultCard(m) ? (
              <div key={m.id} onClick={(e) => {
                // 点按钮不触发（按钮自身 stopPropagation）
                if ((e.target as HTMLElement).closest("button,a")) return;
                setViewMsg(m);
              }}>
                <RecognitionResultCard msg={m} onFly={flyToLandmark} />
              </div>
            ) : (
              <div
                key={m.id}
                className="max-w-[92%] cursor-pointer self-start rounded-2xl rounded-bl-sm border border-border/50 bg-muted/50 px-3 py-2 text-[var(--ui-fs)] text-foreground shadow-sm transition hover:border-primary/50"
                onClick={() => setViewMsg(m)}
                title="点击查看全文"
              >
                <div className="whitespace-pre-wrap break-words leading-relaxed">{m.content}</div>
                {/* 关联地标行：小按钮弹详情浮窗（详情内有飞过去/写手账） */}
                {m.landmark_ids && m.landmark_ids.length > 0 && (
                  <div className="mt-2 flex flex-wrap items-center gap-1.5 border-t border-border/40 pt-1.5">
                    <span className="text-[10px] text-foreground/50">关联地标</span>
                    {m.landmark_ids.map((id, i) => (
                      <button
                        key={id}
                        onClick={(e) => {
                          e.stopPropagation();
                          window.dispatchEvent(new CustomEvent("ts:open-detail", { detail: id }));
                        }}
                        className="flex items-center gap-1 rounded-lg bg-muted px-2 py-0.5 text-[var(--ui-fs-sm)] transition hover:bg-accent"
                        title={m.landmark_names?.[i] || "地标详情"}
                      >
                        <MapPin className="h-3 w-3" />
                        {m.landmark_names?.[i] || "详情"}
                      </button>
                    ))}
                  </div>
                )}
              </div>
            )
          )
        )}
      </div>

      {/* 底部输入框常驻 */}
      <div className="border-t border-border/50 p-2.5">
        {file && previewUrl && (
          <div className="group relative mb-2 h-20 w-20 overflow-hidden rounded-lg border border-border">
            <img src={previewUrl} alt="待识别图片" className="h-full w-full object-cover" />
            <button
              className="absolute right-1 top-1 rounded-full bg-black/60 p-1 text-white opacity-0 transition group-hover:opacity-100"
              onClick={() => {
                setFile(null);
                if (fileRef.current) fileRef.current.value = "";
              }}
              title="移除图片"
            >
              <X className="h-3 w-3" />
            </button>
            {sending && (
              <div className="absolute inset-0 flex items-center justify-center bg-black/40">
                <span className="h-4 w-4 animate-spin rounded-full border-2 border-white/40 border-t-white" />
              </div>
            )}
          </div>
        )}
        <div className="flex items-center gap-1.5 rounded-xl border border-border bg-background px-2 py-1.5 focus-within:border-primary">
          <textarea
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
            rows={1}
            className="max-h-20 min-h-[1.6em] flex-1 resize-none bg-transparent py-0.5 leading-[1.6] text-[var(--ui-fs)] text-foreground outline-none placeholder:text-foreground/40"
          />
          <input
            ref={fileRef}
            type="file"
            accept="image/png,image/jpeg"
            className="hidden"
            onChange={(e) => {
              const f = e.target.files?.[0];
              if (f && !f.type.startsWith("image/")) {
                toast.error("请选择图片文件（JPG/PNG）");
                return;
              }
              setFile(f || null);
            }}
          />
          <button
            onClick={() => fileRef.current?.click()}
            className="rounded-lg p-2 text-foreground/60 transition hover:bg-muted hover:text-foreground"
            title="上传图片识别"
          >
            <ImagePlus className="h-4 w-4" />
          </button>
          <button
            onClick={handleSend}
            disabled={sending || (!input.trim() && !file)}
            className="flex h-8 shrink-0 items-center gap-1 rounded-lg bg-sky-500 px-2.5 text-[var(--ui-fs-sm)] font-medium text-foreground transition hover:bg-sky-400 disabled:opacity-50"
          >
            {sending ? (
              <>
                <span className="h-1.5 w-1.5 animate-ping rounded-full bg-white" />
                识别中
              </>
            ) : (
              <>
                <Send className="h-3.5 w-3.5" />
                {!narrow && "发送"}
              </>
            )}
          </button>
        </div>
      </div>
      </>
      )}
      {historyWindow}
      {viewMsgWindow}
    </div>
  );
}

/* ================================================================== */
/* 历史会话列表                                                        */
/* ================================================================== */
function HistoryList() {
  const { data, isLoading } = useQuery({
    queryKey: ["qa-history"],
    queryFn: async () =>
      (await api.get("/qa/history")).data.data as {
        id: number;
        question: string;
        answer: string;
        landmark_name: string;
        created_at: string;
      }[],
  });
  if (isLoading) return <div className="py-10 text-center text-sm text-muted-foreground">加载中…</div>;
  if (!data?.length)
    return (
      <div className="flex flex-col items-center gap-1.5 py-12 text-center">
        <History className="h-8 w-8 text-muted-foreground/40" />
        <p className="text-sm text-muted-foreground">暂无历史会话，去和 AI 导游聊聊吧</p>
      </div>
    );
  return (
    <div className="space-y-2">
      {data.map((h) => (
        <div key={h.id} className="rounded-xl border border-border bg-muted/40 p-3">
          <div className="flex items-start gap-2">
            <MessageSquare className="mt-0.5 h-4 w-4 shrink-0 text-primary" />
            <div className="min-w-0 flex-1">
              <div className="text-sm font-medium">{h.question}</div>
              <p className="mt-1 line-clamp-3 text-sm text-muted-foreground">{h.answer}</p>
              <div className="mt-1.5 flex items-center gap-2 text-xs text-muted-foreground">
                {h.landmark_name && (
                  <span className="rounded-full bg-muted px-2 py-0.5">{h.landmark_name}</span>
                )}
                <span>{new Date(h.created_at).toLocaleString("zh-CN")}</span>
              </div>
            </div>
          </div>
        </div>
      ))}
    </div>
  );
}

/* ================================================================== */
/* 通知 Tab：全部 / 未读 两块                                          */
/* ================================================================== */
function NotificationTab({ token, onRead }: { token: string | null; onRead: () => void }) {
  const [filter, setFilter] = useState<"all" | "unread">("all");
  const qc = useQueryClient();

  const { data: notifications } = useQuery({
    queryKey: ["notifications", "list"],
    queryFn: async () => (await api.get("/notifications/", { params: { page_size: 30 } })).data.data,
    enabled: !!token,
  });

  const markOne = useMutation({
    mutationFn: async (id: number) => api.post(`/notifications/${id}/read`),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["notifications"] });
      onRead();
    },
  });

  const markAll = useMutation({
    mutationFn: async () => api.post("/notifications/read-all"),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["notifications"] });
      onRead();
    },
  });

  if (!token) {
    return (
      <div className="flex flex-1 flex-col items-center justify-center gap-2 py-10 text-center">
        <Bell className="h-8 w-8 text-muted-foreground/50" />
        <p className="text-sm text-muted-foreground">登录后可查看通知</p>
      </div>
    );
  }

  const list = (notifications || []).filter((n: any) => (filter === "unread" ? !n.is_read : true));

  return (
    <div className="flex min-h-0 flex-1 flex-col">
      {/* 全部/未读 切换 + 全部已读 */}
      <div className="flex items-center justify-between border-b border-border/50 px-3 py-2">
        <div className="flex gap-1 rounded-lg bg-muted p-0.5">
          {(["all", "unread"] as const).map((f) => (
            <button
              key={f}
              onClick={() => setFilter(f)}
              className={`rounded-md px-2.5 py-1 text-xs font-medium transition ${
                filter === f ? "bg-background shadow text-foreground" : "text-muted-foreground hover:text-foreground"
              }`}
            >
              {f === "all" ? "全部" : "未读"}
            </button>
          ))}
        </div>
        <button
          onClick={() => markAll.mutate()}
          disabled={markAll.isPending}
          className="rounded-lg px-2 py-1 text-xs text-muted-foreground transition hover:bg-muted hover:text-foreground"
        >
          全部已读
        </button>
      </div>

      {/* 列表 */}
      <div className="min-h-0 flex-1 overflow-y-auto p-2">
        {list.length ? (
          list.map((n: any) => (
            <div
              key={n.id}
              className={`flex items-start gap-2 rounded-xl border p-2.5 text-sm ${
                n.is_read ? "border-transparent opacity-70" : "border-primary/25 bg-accent/40"
              }`}
            >
              <div className="mt-0.5 shrink-0">
                {n.type === "badge" ? "🏆" : n.type === "reply" ? "💬" : n.type === "moderation" ? "📝" : "🔔"}
              </div>
              <div className="min-w-0 flex-1">
                <div className="font-medium">{n.title}</div>
                {n.content && <div className="mt-0.5 break-words text-muted-foreground">{n.content}</div>}
                <div className="mt-1 text-xs text-muted-foreground">
                  {new Date(n.created_at).toLocaleString("zh-CN")}
                </div>
              </div>
              {!n.is_read && (
                <button
                  onClick={() => markOne.mutate(n.id)}
                  className="shrink-0 self-center rounded-full p-1.5 text-muted-foreground hover:bg-muted hover:text-foreground"
                  title="标为已读"
                >
                  <Check className="h-3.5 w-3.5" />
                </button>
              )}
            </div>
          ))
        ) : (
          <p className="py-10 text-center text-sm text-muted-foreground">
            {filter === "unread" ? "没有未读通知" : "暂无通知"}
          </p>
        )}
      </div>
    </div>
  );
}
