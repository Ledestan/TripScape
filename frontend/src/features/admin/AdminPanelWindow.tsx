import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import ReactECharts from "echarts-for-react";
import { toast } from "sonner";
import {
  Users, MapPin, MessageSquare, ScanLine, NotebookPen, ShieldAlert, Search, Eye, FileText,
} from "lucide-react";

import { api, errMessage } from "@/api/client";
import { FloatingWindow } from "@/components/FloatingWindow";
import { useAuthStore } from "@/stores/auth";

/* ---------------- 筛选器（地区 + 地标级联，多 Tab 复用） ---------------- */
interface LandmarkLite {
  id: number;
  name: string;
  region: string;
}

function useLandmarks() {
  return useQuery({
    queryKey: ["landmarks", "all-lite"],
    queryFn: async () => (await api.get("/landmarks/", { params: { page_size: 100 } })).data.data as LandmarkLite[],
    staleTime: 5 * 60_000,
  });
}

function RegionLandmarkFilter({
  region,
  setRegion,
  landmarkId,
  setLandmarkId,
  landmarks,
}: {
  region: string;
  setRegion: (v: string) => void;
  landmarkId: number | null;
  setLandmarkId: (v: number | null) => void;
  landmarks?: LandmarkLite[];
}) {
  // 固定大区（含预留空区）+ 数据中出现的区域合并
  const FIXED_REGIONS = ["亚洲", "欧洲", "非洲", "北美洲", "南美洲", "大洋洲"];
  const extra = Array.from(new Set((landmarks || []).map((l) => l.region).filter(Boolean))).filter(
    (r) => !FIXED_REGIONS.includes(r)
  );
  const regions = [...FIXED_REGIONS, ...extra.sort()];

  const [lmQuery, setLmQuery] = useState("");
  const pool = region ? (landmarks || []).filter((l) => l.region === region) : landmarks || [];
  const lms = lmQuery.trim() ? pool.filter((l) => l.name.includes(lmQuery.trim())) : pool;

  return (
    <div className="flex flex-wrap items-center gap-1.5">
      <select
        value={region}
        onChange={(e) => {
          setRegion(e.target.value);
          setLandmarkId(null);
          setLmQuery("");
        }}
        className="rounded-lg border border-border bg-background px-2 py-1.5 text-xs outline-none"
      >
        <option value="">全部地区</option>
        {regions.map((r) => (
          <option key={r} value={r}>
            {r}
          </option>
        ))}
      </select>
      <select
        value={landmarkId ?? ""}
        onChange={(e) => setLandmarkId(e.target.value ? Number(e.target.value) : null)}
        className="max-w-40 rounded-lg border border-border bg-background px-2 py-1.5 text-xs outline-none"
      >
        <option value="">全部地标</option>
        {pool.map((l) => (
          <option key={l.id} value={l.id}>
            {l.name}
          </option>
        ))}
      </select>
      <div className="relative">
        <input
          value={lmQuery}
          onChange={(e) => setLmQuery(e.target.value)}
          placeholder="搜索地标…"
          className="w-32 rounded-lg border border-border bg-background px-2.5 py-1.5 text-xs outline-none focus:border-primary"
        />
        {lmQuery.trim() && (
          <div className="absolute left-0 top-full z-20 mt-1 max-h-48 w-56 overflow-y-auto rounded-xl border border-border/70 bg-card p-1 shadow-xl">
            {lms.length ? (
              lms.slice(0, 20).map((l) => (
                <button
                  key={l.id}
                  onClick={() => {
                    setLandmarkId(l.id);
                    setRegion(l.region);
                    setLmQuery("");
                  }}
                  className="flex w-full items-center gap-1.5 rounded-lg px-2 py-1.5 text-left text-xs transition hover:bg-accent"
                >
                  <MapPin className="h-3 w-3 shrink-0 text-muted-foreground" />
                  <span className="truncate">{l.name}</span>
                  <span className="ml-auto shrink-0 text-[10px] text-muted-foreground">{l.region}</span>
                </button>
              ))
            ) : (
              <p className="px-2 py-3 text-center text-xs text-muted-foreground">无匹配地标</p>
            )}
          </div>
        )}
      </div>
    </div>
  );
}

/* ---------------- 原文查看弹窗 ---------------- */
function ExcerptView({
  text,
  title,
  landmarkName,
  region,
  onClose,
}: {
  text: string;
  title: string;
  landmarkName?: string;
  region?: string;
  onClose: () => void;
}) {
  return (
    <div className="fixed inset-0 z-[70] flex items-center justify-center p-4">
      <div className="absolute inset-0 bg-black/50" onClick={onClose} />
      <div className="relative w-full max-w-md rounded-2xl border border-border/70 bg-card p-5 text-card-foreground shadow-xl">
        <div className="mb-2 flex items-center justify-between">
          <div className="text-sm font-semibold">{title}</div>
          <button onClick={onClose} className="rounded-lg px-2 py-1 text-xs text-muted-foreground hover:bg-muted">
            关闭
          </button>
        </div>
        {(landmarkName || region) && (
          <div className="mb-2 flex flex-wrap items-center gap-1.5 text-xs text-muted-foreground">
            <MapPin className="h-3 w-3 text-primary" />
            {landmarkName && <span>{landmarkName}</span>}
            {region && <span className="rounded-full bg-muted px-1.5 py-0.5">{region}</span>}
          </div>
        )}
        <div className="max-h-72 overflow-y-auto whitespace-pre-wrap text-sm leading-relaxed">{text}</div>
      </div>
    </div>
  );
}

/* ---------------- 统一确认弹窗（支持自定义天数） ---------------- */
function ConfirmBox({
  title,
  hint,
  withDays,
  days,
  setDays,
  customDays,
  setCustomDays,
  reason,
  setReason,
  onCancel,
  onOk,
  pending,
  danger,
}: {
  title: string;
  hint?: string;
  withDays?: boolean;
  days: number;
  setDays: (v: number) => void;
  customDays: string;
  setCustomDays: (v: string) => void;
  reason: string;
  setReason: (v: string) => void;
  onCancel: () => void;
  onOk: () => void;
  pending?: boolean;
  danger?: boolean;
}) {
  return (
    <div className="fixed inset-0 z-[70] flex items-center justify-center p-4">
      <div className="absolute inset-0 bg-black/40" onClick={onCancel} />
      <div className="relative w-full max-w-sm rounded-2xl border border-border/70 bg-card p-5 text-card-foreground shadow-xl">
        <div className="text-sm font-semibold">{title}</div>
        {hint && <p className="mt-1.5 text-xs text-muted-foreground">{hint}</p>}

        {withDays && (
          <div className="mt-3">
            <div className="mb-1.5 text-xs text-muted-foreground">时长</div>
            <div className="grid grid-cols-5 gap-1">
              {[1, 3, 7, 30, 999].map((d) => (
                <button
                  key={d}
                  onClick={() => {
                    setDays(d);
                    setCustomDays("");
                  }}
                  className={`rounded-lg border py-1.5 text-xs transition ${
                    days === d && !customDays ? "border-primary bg-primary/10 text-primary" : "border-border hover:bg-accent"
                  }`}
                >
                  {d === 999 ? "永久" : `${d}天`}
                </button>
              ))}
            </div>
            <input
              value={customDays}
              onChange={(e) => {
                const v = e.target.value.replace(/\D/g, "");
                setCustomDays(v);
                if (v) setDays(Number(v));
              }}
              placeholder="自定义天数"
              className="mt-1.5 w-full rounded-lg border border-border bg-background px-3 py-1.5 text-center text-xs outline-none focus:border-primary"
            />
          </div>
        )}

        <div className="mt-3">
          <div className="mb-1.5 text-xs text-muted-foreground">原因（可选，记录到审计日志）</div>
          <input
            value={reason}
            onChange={(e) => setReason(e.target.value)}
            placeholder="填写原因"
            className="w-full rounded-lg border border-border bg-background px-3 py-2 text-sm outline-none focus:border-primary"
          />
        </div>

        <div className="mt-4 flex justify-end gap-2">
          <button onClick={onCancel} className="rounded-lg border border-border px-3 py-1.5 text-sm transition hover:bg-accent">
            取消
          </button>
          <button
            onClick={onOk}
            disabled={pending || (withDays && !days)}
            className={`rounded-lg px-3.5 py-1.5 text-sm font-medium text-white transition disabled:opacity-50 ${
              danger ? "bg-destructive hover:bg-destructive/90" : "bg-primary hover:bg-primary/90"
            }`}
          >
            {pending ? "执行中…" : "确认执行"}
          </button>
        </div>
      </div>
    </div>
  );
}

/* ================================================================== */
/* 管理后台大浮窗（五 Tab）                                              */
/* ================================================================== */
type Tab = "review" | "landmarks" | "trash" | "overview" | "users" | "reports" | "audit";

export default function AdminPanelWindow({ onClose }: { onClose: () => void }) {
  const [tab, setTab] = useState<Tab>("review");

  // 待处理举报计数（Tab 徽章 + 看板待办）
  const { data: pendingReports } = useQuery({
    queryKey: ["admin-reports", "count"],
    queryFn: async () => (await api.get("/admin/reports", { params: { status: "pending", page_size: 1 } })).data.meta.total as number,
    refetchInterval: 30_000,
  });
  const pendingCount = pendingReports ?? 0;

  const tabs: { key: Tab; label: string }[] = [
    { key: "review", label: "审核中心" },
    { key: "landmarks", label: "地标管理" },
    { key: "trash", label: "回收站" },
    { key: "overview", label: "运营看板" },
    { key: "users", label: "账号管理" },
    { key: "reports", label: "举报处理" },
    { key: "audit", label: "审计日志" },
  ];

  return (
    <FloatingWindow open onClose={onClose} title="管理后台" width={940} fixedHeight="min(90vh, 800px)">
      <div className="grid grid-cols-7 gap-1 rounded-xl bg-muted p-1">
        {tabs.map((t) => (
          <button
            key={t.key}
            onClick={() => setTab(t.key)}
            className={`relative flex items-center justify-center gap-1.5 rounded-lg py-1.5 text-sm font-medium transition ${
              tab === t.key ? "bg-background shadow" : "text-muted-foreground hover:text-foreground"
            }`}
          >
            {t.label}
            {t.key === "reports" && pendingCount > 0 && (
              <span className="flex h-4 min-w-4 items-center justify-center rounded-full bg-destructive px-1 text-[10px] font-bold text-white">
                {pendingCount > 99 ? "99+" : pendingCount}
              </span>
            )}
          </button>
        ))}
      </div>
      <div className="mt-3 flex-1 overflow-y-auto pr-0.5">
        {tab === "review" && <ReviewTab />}
        {tab === "landmarks" && <LandmarksTab />}
        {tab === "trash" && <TrashTab />}
        {tab === "overview" && <OverviewTab onGoReports={() => setTab("reports")} onGoReview={() => setTab("review")} />}
        {tab === "users" && <UsersTab />}
        {tab === "reports" && <ReportsTab />}
        {tab === "audit" && <AuditTab />}
      </div>
    </FloatingWindow>
  );
}

/* ---------------- 审核中心（评论在前 + 地区/地标筛选 + 查看原文） ---------------- */
interface ReviewItem {
  id: number;
  title?: string;
  content?: string;
  user: { nickname: string; username?: string };
  landmark?: { name: string; region?: string };
  landmark_name?: string;
  is_public?: boolean;
  status?: string;
  is_hidden?: boolean;
  edit_pending?: boolean;
  new_title?: string;
  new_content?: string;
  risk?: string[];
  created_at: string;
}

function ReviewTab() {
  const qc = useQueryClient();
  const { data: landmarks } = useLandmarks();

  const [sub, setSub] = useState<"comments" | "journals">("comments");
  const [region, setRegion] = useState("");
  const [lmFilter, setLmFilter] = useState<number | null>(null);
  const [cHidden, setCHidden] = useState<"all" | "shown" | "hidden">("shown");
  const [jStatus, setJStatus] = useState<"all" | "published" | "pending" | "rejected" | "hidden">("published");
  const [selected, setSelected] = useState<Set<number>>(new Set());
  const [viewText, setViewText] = useState<{ title: string; text: string; landmarkName?: string; region?: string } | null>(null);
  const [batchBox, setBatchBox] = useState<{ action: string; label: string } | null>(null);

  const { data: comments } = useQuery({
    queryKey: ["review-comments", cHidden, region, lmFilter],
    queryFn: async () =>
      (
        await api.get("/admin/review/comments", {
          params: {
            hidden: cHidden === "all" ? "all" : String(cHidden === "hidden"),
            region,
            landmark_id: lmFilter ?? undefined,
            page_size: 50,
          },
        })
      ).data.data as ReviewItem[],
    enabled: sub === "comments",
  });

  const { data: journals } = useQuery({
    queryKey: ["review-journals", jStatus, region, lmFilter],
    queryFn: async () =>
      (
        await api.get("/admin/review/journals", {
          params: { status: jStatus, region, landmark_id: lmFilter ?? undefined, page_size: 50 },
        })
      ).data.data as ReviewItem[],
    enabled: sub === "journals",
  });

  const items = sub === "comments" ? comments : journals;
  const toggle = (id: number) =>
    setSelected((p) => {
      const n = new Set(p);
      if (n.has(id)) n.delete(id);
      else n.add(id);
      return n;
    });

  const moderate = useMutation({
    mutationFn: async (p: { action: string }) =>
      sub === "journals"
        ? api.post("/admin/review/journals/moderate", { ids: [...selected], action: p.action })
        : api.post("/admin/review/comments/moderate", { ids: [...selected], action: p.action }),
    onSuccess: (_d, v) => {
      toast.success(`已执行：${v.action}`);
      setSelected(new Set());
      qc.invalidateQueries({ queryKey: ["review-journals"] });
      qc.invalidateQueries({ queryKey: ["review-comments"] });
    },
    onError: (e) => toast.error(errMessage(e)),
  });

  const cActions =
    cHidden === "hidden"
      ? [
          { action: "restore", label: "恢复展示", tone: "ok" as const },
          { action: "delete", label: "删除", tone: "danger" as const },
        ]
      : [
          { action: "hide", label: "隐藏", tone: "warn" as const },
          { action: "restore", label: "恢复展示", tone: "ok" as const },
          { action: "delete", label: "删除", tone: "danger" as const },
        ];

  const jActions =
    jStatus === "published"
      ? [
          { action: "hide", label: "隐藏", tone: "warn" as const },
          { action: "delete", label: "删除", tone: "danger" as const },
        ]
      : jStatus === "pending"
        ? [
            { action: "approve", label: "通过", tone: "ok" as const },
            { action: "reject", label: "驳回", tone: "warn" as const },
            { action: "delete", label: "删除", tone: "danger" as const },
          ]
        : jStatus === "rejected"
          ? [
              { action: "approve", label: "通过", tone: "ok" as const },
              { action: "delete", label: "删除", tone: "danger" as const },
            ]
          : jStatus === "hidden"
            ? [
                { action: "restore", label: "恢复公开", tone: "ok" as const },
                { action: "delete", label: "删除", tone: "danger" as const },
              ]
            : [
                { action: "hide", label: "隐藏", tone: "warn" as const },
                { action: "restore", label: "恢复公开", tone: "ok" as const },
                { action: "delete", label: "删除", tone: "danger" as const },
              ];

  const actions = sub === "comments" ? cActions : jActions;

  return (
    <div>
      {/* 内容切换（评论在前）+ 筛选 */}
      <div className="flex flex-wrap items-center gap-2">
        <div className="grid grid-cols-2 gap-1 rounded-xl bg-muted p-1">
          {(["comments", "journals"] as const).map((s) => (
            <button
              key={s}
              onClick={() => {
                setSub(s);
                setSelected(new Set());
              }}
              className={`rounded-lg px-3 py-1.5 text-sm font-medium transition ${
                sub === s ? "bg-background shadow" : "text-muted-foreground hover:text-foreground"
              }`}
            >
              {s === "comments" ? "评论" : "手账"}
            </button>
          ))}
        </div>

        {sub === "comments" ? (
          <div className="flex gap-1">
            {(["all", "shown", "hidden"] as const).map((h) => (
              <button
                key={h}
                onClick={() => {
                  setCHidden(h);
                  setSelected(new Set());
                }}
                className={`rounded-lg border px-2.5 py-1 text-xs transition ${
                  cHidden === h ? "border-primary bg-primary/10 text-primary" : "border-border hover:bg-accent"
                }`}
              >
                {h === "all" ? "全部" : h === "shown" ? "展示中" : "已隐藏"}
              </button>
            ))}
          </div>
        ) : (
          <div className="flex gap-1">
            {(["all", "published", "pending", "rejected", "hidden"] as const).map((st) => (
              <button
                key={st}
                onClick={() => {
                  setJStatus(st);
                  setSelected(new Set());
                }}
                className={`rounded-lg border px-2.5 py-1 text-xs transition ${
                  jStatus === st ? "border-primary bg-primary/10 text-primary" : "border-border hover:bg-accent"
                }`}
              >
                {st === "all" ? "全部" : st === "published" ? "展示中" : st === "pending" ? "待审核" : st === "rejected" ? "已驳回" : "已隐藏"}
              </button>
            ))}
          </div>
        )}

        <RegionLandmarkFilter
          region={region}
          setRegion={setRegion}
          landmarkId={lmFilter}
          setLandmarkId={setLmFilter}
          landmarks={landmarks}
        />
        <span className="ml-auto text-xs text-muted-foreground">已选 {selected.size} 条</span>
      </div>

      {/* 批量操作条 */}
      <div className="mt-2.5 flex items-center gap-1.5 rounded-xl border border-border bg-muted/40 p-2">
        <button
          onClick={() =>
            setSelected(
              items?.length && selected.size === items.length ? new Set() : new Set(items?.map((i) => i.id) || [])
            )
          }
          className="rounded-lg border border-border bg-card px-2.5 py-1 text-xs transition hover:bg-accent"
        >
          {items?.length && selected.size === items.length ? "取消全选" : "全选"}
        </button>
        <div className="mx-1 h-4 w-px bg-border" />
        {actions.map((a) => (
          <button
            key={a.action}
            onClick={() => {
              if (!selected.size) return toast.error("请先勾选条目");
              setBatchBox(a);
            }}
            className={`rounded-lg border px-2 py-1 text-[11px] transition ${
              a.tone === "danger"
                ? "border-destructive/40 text-destructive hover:bg-destructive/10"
                : a.tone === "warn"
                  ? "border-amber-400/40 text-amber-500 hover:bg-amber-400/10"
                  : "border-emerald-400/40 text-emerald-500 hover:bg-emerald-400/10"
            }`}
          >
            {a.label}
          </button>
        ))}
      </div>

      {/* 列表 */}
      <div className="mt-2.5 space-y-1.5">
        {items?.length ? (
          items.map((it) => (
            <div
              key={it.id}
              className="flex items-start gap-2.5 rounded-xl border border-border bg-muted/40 p-3 transition hover:bg-accent/50"
            >
              <input
                type="checkbox"
                checked={selected.has(it.id)}
                onChange={() => toggle(it.id)}
                className="mt-1 h-4 w-4 shrink-0 accent-primary"
              />
              <div className="min-w-0 flex-1">
                <div className="flex flex-wrap items-center gap-1.5 text-xs text-muted-foreground">
                  <span className="font-medium text-foreground">{it.user?.nickname || it.user?.username}</span>
                  {(it.landmark?.name || it.landmark_name) && (
                    <span className="flex items-center gap-0.5">
                      <MapPin className="h-3 w-3" />
                      {it.landmark?.name || it.landmark_name}
                    </span>
                  )}
                  {it.landmark?.region && <span className="rounded-full bg-muted px-1.5 py-0.5">{it.landmark.region}</span>}
                  <span className="ml-auto">{new Date(it.created_at).toLocaleString("zh-CN")}</span>
                </div>
                {it.edit_pending && (
                  <span className="mr-1 rounded-full bg-sky-500/15 px-1.5 py-0.5 text-[10px] text-sky-500">二次编辑待审</span>
                )}
                {it.risk?.map((r) => (
                  <span key={r} className="mr-1 rounded-full bg-rose-500/15 px-1.5 py-0.5 text-[10px] text-rose-500">
                    {r}
                  </span>
                ))}
                {sub === "journals" && it.edit_pending ? (
                  <>
                    <div className="mt-1 truncate text-sm font-medium">{it.new_title || it.title}</div>
                    <p className="mt-0.5 line-clamp-2 text-sm text-muted-foreground">{it.new_content || it.content}</p>
                    <p className="mt-0.5 text-[11px] text-muted-foreground/70">当前展示旧版：《{it.title}》</p>
                  </>
                ) : (
                  <>
                    {it.title && <div className="mt-1 truncate text-sm font-medium">{it.title}</div>}
                    <p className="mt-0.5 line-clamp-2 text-sm text-muted-foreground">{it.content}</p>
                  </>
                )}
              </div>
              <button
                onClick={() =>
                  setViewText({
                    title: it.edit_pending ? `新版待审 · ${it.new_title || it.title}` : it.title || `评论 #${it.id}`,
                    text: it.edit_pending
                      ? `${it.new_content || it.content}\n\n——— 当前展示旧版 ———\n${it.content || ""}`
                      : it.content || "",
                    landmarkName: it.landmark?.name || it.landmark_name,
                    region: it.landmark?.region,
                  })
                }
                className="mt-0.5 flex shrink-0 items-center gap-1 rounded-lg border border-border bg-card px-2 py-1 text-[11px] transition hover:bg-accent"
                title="查看原文"
              >
                <Eye className="h-3 w-3" /> 原文
              </button>
            </div>
          ))
        ) : (
          <p className="py-10 text-center text-sm text-muted-foreground">暂无内容</p>
        )}
      </div>

      {viewText && <ExcerptView {...viewText} onClose={() => setViewText(null)} />}

      {batchBox && (
        <ConfirmBox
          title={`确认对 ${selected.size} 条内容执行【${batchBox.label}】？`}
          hint={batchBox.action === "delete" ? "删除不可恢复。" : undefined}
          days={0}
          setDays={() => {}}
          customDays=""
          setCustomDays={() => {}}
          reason=""
          setReason={() => {}}
          onCancel={() => setBatchBox(null)}
          onOk={() => moderate.mutate({ action: batchBox.action }, { onSuccess: () => setBatchBox(null) })}
          pending={moderate.isPending}
          danger
        />
      )}
    </div>
  );
}

/* ---------------- 运营看板 ---------------- */
function OverviewTab({ onGoReports, onGoReview }: { onGoReports: () => void; onGoReview: () => void }) {
  const { data: pendingReports } = useQuery({
    queryKey: ["admin-reports", "count"],
    queryFn: async () => (await api.get("/admin/reports", { params: { status: "pending", page_size: 1 } })).data.meta.total as number,
  });
  const { data: pendingJournals } = useQuery({
    queryKey: ["review-journals", "count"],
    queryFn: async () => (await api.get("/admin/review/journals", { params: { status: "pending", page_size: 1 } })).data.meta.total as number,
  });
  const { data } = useQuery({
    queryKey: ["dashboard"],
    queryFn: async () => (await api.get("/dashboard/stats", { params: { days: 14 } })).data.data,
    refetchInterval: 60_000,
  });

  if (!data) return <div className="py-10 text-center text-sm text-muted-foreground">加载中…</div>;

  const trendOption = {
    tooltip: { trigger: "axis" },
    legend: { data: ["识别次数", "评论", "手账", "新用户"], textStyle: { fontSize: 11 } },
    grid: { left: 40, right: 16, top: 36, bottom: 28 },
    xAxis: { type: "category", data: data.trends.map((t: any) => t.date.slice(5)) },
    yAxis: { type: "value", minInterval: 1 },
    series: [
      { name: "识别次数", type: "line", smooth: true, data: data.trends.map((t: any) => t.recognitions), areaStyle: { opacity: 0.12 } },
      { name: "评论", type: "line", smooth: true, data: data.trends.map((t: any) => t.comments) },
      { name: "手账", type: "line", smooth: true, data: data.trends.map((t: any) => t.journals) },
      { name: "新用户", type: "line", smooth: true, data: data.trends.map((t: any) => t.new_users) },
    ],
  };

  const cards = [
    { label: "用户数", value: data.totals.users, icon: <Users className="h-4 w-4" /> },
    { label: "地标数", value: data.totals.landmarks, icon: <MapPin className="h-4 w-4" /> },
    { label: "评论数", value: data.totals.comments, icon: <MessageSquare className="h-4 w-4" /> },
    { label: "手账数", value: data.totals.journals, icon: <NotebookPen className="h-4 w-4" /> },
    { label: "识别次数", value: data.totals.recognitions, icon: <ScanLine className="h-4 w-4" /> },
  ];

  const todo =
    (pendingReports ?? 0) + (pendingJournals ?? 0) > 0
      ? [
          { label: `${pendingReports ?? 0} 条待处理举报`, onClick: onGoReports },
          { label: `${pendingJournals ?? 0} 篇手账待审核`, onClick: onGoReview },
        ].filter((x) => !x.label.startsWith("0"))
      : [];

  return (
    <div>
      {todo.length > 0 && (
        <div className="mb-3 flex flex-wrap items-center gap-2 rounded-xl border border-amber-400/40 bg-amber-400/10 p-2.5">
          <ShieldAlert className="h-4 w-4 shrink-0 text-amber-500" />
          <span className="text-sm font-medium text-amber-600 dark:text-amber-400">待办</span>
          {todo.map((x) => (
            <button
              key={x.label}
              onClick={x.onClick}
              className="rounded-full bg-background px-3 py-1 text-xs font-medium text-primary shadow-sm transition hover:bg-accent"
            >
              {x.label} →
            </button>
          ))}
        </div>
      )}
      <div className="grid grid-cols-5 gap-2">
        {cards.map((c) => (
          <div key={c.label} className="rounded-xl border border-border bg-muted/40 p-2.5 text-center">
            <div className="mx-auto mb-1 flex h-8 w-8 items-center justify-center rounded-full bg-primary/10 text-primary">
              {c.icon}
            </div>
            <div className="text-lg font-bold">{c.value}</div>
            <div className="text-[11px] text-muted-foreground">{c.label}</div>
          </div>
        ))}
      </div>
      <div className="mt-4 rounded-xl border border-border p-2">
        <ReactECharts option={trendOption} style={{ height: 280 }} notMerge />
      </div>
      {data.hot_landmarks?.length > 0 && (
        <div className="mt-3">
          <div className="mb-1.5 text-sm font-semibold">地标热度 Top10（按手账数）</div>
          <div className="space-y-1">
            {data.hot_landmarks.map((h: any, i: number) => (
              <div key={h.id} className="flex items-center gap-2 text-sm">
                <span className="w-5 text-right text-xs text-muted-foreground">{i + 1}</span>
                <span className="w-28 truncate">{h.name}</span>
                <div className="h-2 flex-1 overflow-hidden rounded-full bg-muted">
                  <div
                    className="h-full rounded-full bg-primary"
                    style={{ width: `${Math.min(100, (h.journals / data.hot_landmarks[0].journals) * 100)}%` }}
                  />
                </div>
                <span className="w-10 text-right text-xs text-muted-foreground">{h.journals}</span>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

/* ---------------- 账号管理（自定义时长） ---------------- */
function UsersTab() {
  const qc = useQueryClient();
  const me = useAuthStore((s) => s.user);
  const [q, setQ] = useState("");

  const { data: users } = useQuery({
    queryKey: ["admin-users", q],
    queryFn: async () =>
      (await api.get("/admin/users", { params: { q, page_size: 50 } })).data.data as {
        id: number;
        username: string;
        nickname: string;
        role: string;
        is_active: boolean;
        banned: boolean;
        banned_reason: string;
        muted_until: string | null;
        is_muted: boolean;
        locked_until?: string | null;
        created_at: string;
      }[],
  });

  const act = useMutation({
    mutationFn: async (p: { id: number; action: string; reason?: string; days?: number }) =>
      api.post(`/admin/users/${p.id}/account`, { action: p.action, reason: p.reason || "", days: p.days ?? 7 }),
    onSuccess: () => {
      toast.success("操作成功");
      qc.invalidateQueries({ queryKey: ["admin-users"] });
    },
    onError: (e) => toast.error(errMessage(e)),
  });

  const [box, setBox] = useState<{
    user: { id: number; username: string };
    action: string;
    label: string;
    withDays: boolean;
  } | null>(null);
  const [days, setDays] = useState(7);
  const [customDays, setCustomDays] = useState("");
  const [reason, setReason] = useState("");

  const ask = (u: { id: number; username: string }, action: string, label: string, withDays = false) => {
    setDays(7);
    setCustomDays("");
    setReason("");
    setBox({ user: u, action, label, withDays });
  };

  return (
    <div>
      <div className="flex items-center gap-2 rounded-xl border border-border/70 bg-background px-3 py-2">
        <Search className="h-4 w-4 text-muted-foreground" />
        <input
          value={q}
          onChange={(e) => setQ(e.target.value)}
          placeholder="搜索用户名/昵称"
          className="min-w-0 flex-1 bg-transparent text-sm outline-none"
        />
      </div>

      <div className="mt-3 space-y-1.5">
        {users?.map((u) => (
          <div key={u.id} className="flex items-start justify-between gap-2 rounded-xl border border-border bg-muted/40 p-3">
            <div className="min-w-0">
              <div className="flex flex-wrap items-center gap-1.5 text-sm">
                <span className="font-medium">{u.nickname}</span>
                <span className="text-xs text-muted-foreground">@{u.username}</span>
                {u.role === "admin" && (
                  <span className="rounded-full bg-primary/15 px-1.5 py-0.5 text-[10px] text-primary">管理员</span>
                )}
                {u.banned && (
                  <span className="rounded-full bg-destructive/15 px-1.5 py-0.5 text-[10px] text-destructive">封禁</span>
                )}
                {u.is_muted && (
                  <span className="rounded-full bg-amber-400/20 px-1.5 py-0.5 text-[10px] text-amber-500">
                    禁言至 {u.muted_until?.slice(5, 16).replace("T", " ")}
                  </span>
                )}
                {!u.is_active && (
                  <span className="rounded-full bg-muted px-1.5 py-0.5 text-[10px] text-muted-foreground">限制登录</span>
                )}
                {u.locked_until && (
                  <span className="rounded-full bg-muted px-1.5 py-0.5 text-[10px] text-muted-foreground">
                    限登至 {u.locked_until.slice(5, 16).replace("T", " ")}
                  </span>
                )}
              </div>
              <div className="mt-0.5 text-[11px] text-muted-foreground">
                {new Date(u.created_at).toLocaleDateString("zh-CN")} 加入
                {u.banned_reason && ` · 封禁原因：${u.banned_reason}`}
              </div>
            </div>

            {u.id !== me?.id && u.role !== "admin" && (
              <div className="flex shrink-0 flex-wrap justify-end gap-1">
                {u.banned ? (
                  <ActBtn onClick={() => ask(u, "unban", "解除封禁")} tone="ok">解封</ActBtn>
                ) : (
                  <ActBtn onClick={() => ask(u, "ban", "封禁")} tone="danger">封禁</ActBtn>
                )}
                {u.is_muted ? (
                  <ActBtn onClick={() => ask(u, "unmute", "解除禁言")} tone="ok">解禁言</ActBtn>
                ) : (
                  <ActBtn onClick={() => ask(u, "mute", "禁言", true)} tone="warn">禁言</ActBtn>
                )}
                {u.is_active && !u.locked_until ? (
                  <ActBtn onClick={() => ask(u, "lock", "限制登录", true)} tone="warn">限制登录</ActBtn>
                ) : (
                  <ActBtn onClick={() => ask(u, "unlock", "恢复登录")} tone="ok">恢复登录</ActBtn>
                )}
              </div>
            )}
          </div>
        ))}
        {!users?.length && <p className="py-8 text-center text-sm text-muted-foreground">无匹配用户</p>}
      </div>

      {box && (
        <ConfirmBox
          title={`确认对用户「${box.user.username}」执行【${box.label}】？`}
          withDays={box.withDays}
          days={days}
          setDays={setDays}
          customDays={customDays}
          setCustomDays={setCustomDays}
          reason={reason}
          setReason={setReason}
          onCancel={() => setBox(null)}
          onOk={() =>
            act.mutate(
              { id: box.user.id, action: box.action, reason, days },
              { onSuccess: () => setBox(null) }
            )
          }
          pending={act.isPending}
          danger
        />
      )}
    </div>
  );
}

function ActBtn({
  onClick,
  tone,
  children,
}: {
  onClick: () => void;
  tone: "danger" | "warn" | "ok";
  children: React.ReactNode;
}) {
  const tones = {
    danger: "text-destructive hover:bg-destructive/10 border-destructive/40",
    warn: "text-amber-500 hover:bg-amber-400/10 border-amber-400/40",
    ok: "text-emerald-500 hover:bg-emerald-400/10 border-emerald-400/40",
  };
  return (
    <button onClick={onClick} className={`rounded-lg border px-2 py-1 text-[11px] transition ${tones[tone]}`}>
      {children}
    </button>
  );
}

/* ---------------- 举报处理（待处理/已处理 + 分类型 + 筛选 + 原文带地标定位） ---------------- */
interface ReportRow {
  id: number;
  reporter: string;
  target_type: string;
  target_id: number;
  reason_label: string;
  detail: string;
  target_excerpt: { text: string; landmark_id: number | null; landmark_name: string; region: string };
  status: string;
  status_label: string;
  resolution: string;
  handled_by: string;
  created_at: string;
}

function ReportsTab() {
  const qc = useQueryClient();
  const { data: landmarks } = useLandmarks();
  const [rStatus, setRStatus] = useState<"pending" | "resolved" | "dismissed" | "rejected" | "done">("pending");
  const [targetType, setTargetType] = useState<"" | "comment" | "journal">("");
  const [region, setRegion] = useState("");
  const [lmFilter, setLmFilter] = useState<number | null>(null);
  const [viewText, setViewText] = useState<{
    title: string;
    text: string;
    landmarkName?: string;
    region?: string;
  } | null>(null);
  const [box, setBox] = useState<{ r: { id: number }; action: string; label: string } | null>(null);

  const { data: reports } = useQuery({
    queryKey: ["admin-reports", rStatus, targetType, region, lmFilter],
    queryFn: async () =>
      (
        await api.get("/admin/reports", {
          params: {
            status: rStatus,
            target_type: targetType || undefined,
            region,
            landmark_id: lmFilter ?? undefined,
            page_size: 50,
          },
        })
      ).data.data as ReportRow[],
  });

  const handle = useMutation({
    mutationFn: async (p: { id: number; action: string; resolution: string }) =>
      api.post(`/admin/reports/${p.id}/handle`, { action: p.action, resolution: p.resolution }),
    onSuccess: () => {
      toast.success("已处理");
      qc.invalidateQueries({ queryKey: ["admin-reports"] });
    },
    onError: (e) => toast.error(errMessage(e)),
  });

  // 查看原文（地标信息 + 内容）
  const openExcerpt = (r: ReportRow) => {
    setViewText({
      title: `被举报${r.target_type === "comment" ? "评论" : "手账"} #${r.target_id}`,
      text: r.target_excerpt?.text || "（内容已不存在）",
      landmarkName: r.target_excerpt?.landmark_name,
      region: r.target_excerpt?.region,
    });
  };

  return (
    <div>
      <div className="flex flex-wrap items-center gap-2">
        {/* 类型切换：左侧分段控件（与审核中心一致） */}
        <div className="grid grid-cols-3 gap-1 rounded-xl bg-muted p-1">
          {([
            { v: "", label: "全部" },
            { v: "comment", label: "评论" },
            { v: "journal", label: "手账" },
          ] as const).map((t) => (
            <button
              key={t.v}
              onClick={() => setTargetType(t.v)}
              className={`rounded-lg px-3 py-1.5 text-sm font-medium transition ${
                targetType === t.v ? "bg-background shadow text-foreground" : "text-muted-foreground hover:text-foreground"
              }`}
            >
              {t.label}
            </button>
          ))}
        </div>

        {/* 状态筛选：右侧条件组 */}
        <div className="flex gap-1">
          {([
            { v: "done", label: "全部" },
            { v: "pending", label: "待处理" },
            { v: "resolved", label: "已下架" },
            { v: "dismissed", label: "仅标记" },
            { v: "rejected", label: "已驳回" },
          ] as const).map((s) => (
            <button
              key={s.v}
              onClick={() => setRStatus(s.v)}
              className={`rounded-lg border px-2.5 py-1 text-xs transition ${
                rStatus === s.v ? "border-primary bg-primary/10 text-primary" : "border-border hover:bg-accent"
              }`}
            >
              {s.label}
            </button>
          ))}
        </div>

        <RegionLandmarkFilter
          region={region}
          setRegion={setRegion}
          landmarkId={lmFilter}
          setLandmarkId={setLmFilter}
          landmarks={landmarks}
        />
      </div>

      <div className="mt-3 space-y-2">
        {reports?.length ? (
          reports.map((r) => (
            <div key={r.id} className="rounded-xl border border-border bg-muted/40 p-3">
              <div className="flex flex-wrap items-center gap-2 text-xs text-muted-foreground">
                <ShieldAlert className={`h-4 w-4 ${r.status === "pending" ? "text-destructive" : "text-muted-foreground/50"}`} />
                <span>
                  {r.reporter} 举报了{r.target_type === "comment" ? "评论" : "手账"} #{r.target_id}
                </span>
                {r.target_excerpt?.landmark_name && (
                  <span className="flex items-center gap-0.5">
                    <MapPin className="h-3 w-3" /> {r.target_excerpt.landmark_name}
                  </span>
                )}
                <span className="rounded-full bg-destructive/10 px-2 py-0.5 text-destructive">{r.reason_label}</span>
                {rStatus !== "pending" && (
                  <span className={`rounded-full px-2 py-0.5 ${
                    r.status === "resolved"
                      ? "bg-destructive/10 text-destructive"
                      : r.status === "dismissed"
                        ? "bg-amber-400/15 text-amber-500"
                        : r.status === "rejected"
                          ? "bg-muted text-muted-foreground"
                          : ""
                  }`}>
                    {r.status_label || r.status}
                    {r.handled_by && ` · ${r.handled_by}`}
                  </span>
                )}
                <span className="ml-auto">{new Date(r.created_at).toLocaleString("zh-CN")}</span>
              </div>
              {r.detail && <p className="mt-1.5 text-sm">{r.detail}</p>}
              {r.target_excerpt?.text && (
                <p className="mt-1 line-clamp-1 text-xs text-muted-foreground">原文：{r.target_excerpt.text}</p>
              )}
              {rStatus !== "pending" && r.resolution && (
                <p className="mt-1 text-xs text-muted-foreground">处理结果：{r.resolution}</p>
              )}
              <div className="mt-2 flex justify-end gap-1.5">
                <button
                  onClick={() => openExcerpt(r)}
                  className="flex items-center gap-1 rounded-lg border border-border bg-card px-2 py-1 text-[11px] transition hover:bg-accent"
                >
                  <Eye className="h-3 w-3" /> 原文
                </button>
                {r.status === "pending" ? (
                  <>
                    <ActBtn onClick={() => setBox({ r, action: "resolve", label: "下架内容" })} tone="danger">下架内容</ActBtn>
                    <ActBtn onClick={() => setBox({ r, action: "dismiss", label: "仅标记" })} tone="warn">仅标记</ActBtn>
                    <ActBtn onClick={() => setBox({ r, action: "reject", label: "驳回" })} tone="ok">驳回</ActBtn>
                  </>
                ) : (
                  <ActBtn onClick={() => setBox({ r, action: "reopen", label: "重新打开" })} tone="warn">重新打开</ActBtn>
                )}
              </div>
            </div>
          ))
        ) : (
          <p className="py-10 text-center text-sm text-muted-foreground">没有相关举报</p>
        )}
      </div>

      {viewText && (
        <ExcerptView {...viewText} onClose={() => setViewText(null)} />
      )}

      {box && (
        <ConfirmBox
          title={`确认【${box.label}】该举报？`}
          hint={
            box.action === "resolve"
              ? "被举报内容将被下架（评论隐藏 / 手账转私密并驳回）。"
              : box.action === "reopen"
                ? "该举报将回到待处理列表。"
                : undefined
          }
          days={0}
          setDays={() => {}}
          customDays=""
          setCustomDays={() => {}}
          reason=""
          setReason={() => {}}
          onCancel={() => setBox(null)}
          onOk={() =>
            handle.mutate(
              { id: box.r.id, action: box.action, resolution: box.label },
              { onSuccess: () => setBox(null) }
            )
          }
          pending={handle.isPending}
          danger={box.action !== "reopen"}
        />
      )}
    </div>
  );
}

/* ---------------- 审计日志（筛选 + 导出 CSV） ---------------- */
function AuditTab() {
  const [page, setPage] = useState(1);
  const [username, setUsername] = useState("");
  const [action, setAction] = useState("");
  const [submitted, setSubmitted] = useState({ u: "", a: "" });
  const [exporting, setExporting] = useState(false);

  const { data } = useQuery({
    queryKey: ["audit-logs", page, submitted],
    queryFn: async () =>
      (
        await api.get("/admin/audit-logs", {
          params: { page, page_size: 30, username: submitted.u || undefined, action: submitted.a || undefined },
        })
      ).data as {
        data: {
          id: number;
          username: string;
          action: string;
          target: string;
          detail: string;
          level: string;
          ip: string;
          created_at: string;
        }[];
        meta: { page: number; total_pages: number; total: number };
      },
  });

  const doSearch = () => {
    setPage(1);
    setSubmitted({ u: username.trim(), a: action.trim() });
  };

  const doExport = async () => {
    setExporting(true);
    try {
      const token = JSON.parse(localStorage.getItem("tripscape-auth") || "{}").state?.token;
      const resp = await fetch(
        `/api/admin/audit-logs/export?username=${encodeURIComponent(submitted.u)}&action=${encodeURIComponent(submitted.a)}`,
        { headers: { Authorization: `Bearer ${token}` } }
      );
      if (!resp.ok) throw new Error(String(resp.status));
      const blob = await resp.blob();
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `audit_logs_${new Date().toISOString().slice(0, 10)}.csv`;
      a.click();
      URL.revokeObjectURL(url);
      toast.success("已导出 CSV");
    } catch (e) {
      toast.error(`导出失败：${e}`);
    } finally {
      setExporting(false);
    }
  };

  const items = data?.data ?? [];

  return (
    <div>
      {/* 筛选 + 导出 */}
      <div className="flex flex-wrap items-center gap-2">
        <input
          value={username}
          onChange={(e) => setUsername(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && doSearch()}
          placeholder="按操作者筛选"
          className="w-36 rounded-lg border border-border bg-background px-2.5 py-1.5 text-xs outline-none focus:border-primary"
        />
        <input
          value={action}
          onChange={(e) => setAction(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && doSearch()}
          placeholder="按动作筛选（如 journal.）"
          className="w-44 rounded-lg border border-border bg-background px-2.5 py-1.5 text-xs outline-none focus:border-primary"
        />
        <button
          onClick={doSearch}
          className="flex items-center gap-1 rounded-lg border border-border bg-card px-2.5 py-1.5 text-xs transition hover:bg-accent"
        >
          <Search className="h-3 w-3" /> 筛选
        </button>
        <button
          onClick={doExport}
          disabled={exporting}
          className="ml-auto flex items-center gap-1 rounded-lg bg-primary px-2.5 py-1.5 text-xs font-medium text-primary-foreground transition hover:bg-primary/90 disabled:opacity-50"
        >
          <FileText className="h-3 w-3" /> {exporting ? "导出中…" : "导出 CSV"}
        </button>
      </div>

      <div className="mt-2 mb-2 flex items-center justify-between text-xs text-muted-foreground">
        <span>共 {data?.meta.total ?? 0} 条</span>
        <div className="flex items-center gap-2">
          <button
            onClick={() => setPage((p) => Math.max(1, p - 1))}
            disabled={page <= 1}
            className="rounded-lg border border-border px-2 py-1 transition hover:bg-accent disabled:opacity-40"
          >
            上一页
          </button>
          <span>
            {page} / {data?.meta.total_pages ?? 1}
          </span>
          <button
            onClick={() => setPage((p) => Math.min(data?.meta.total_pages ?? 1, p + 1))}
            disabled={page >= (data?.meta.total_pages ?? 1)}
            className="rounded-lg border border-border px-2 py-1 transition hover:bg-accent disabled:opacity-40"
          >
            下一页
          </button>
        </div>
      </div>

      <div className="space-y-1">
        {items.map((l) => (
          <div
            key={l.id}
            className="flex flex-wrap items-center gap-2 rounded-xl border border-border bg-muted/40 px-3 py-2 text-xs"
          >
            <span className="w-32 shrink-0 text-muted-foreground">{new Date(l.created_at).toLocaleString("zh-CN")}</span>
            <span className="w-20 shrink-0 truncate font-medium">{l.username || "-"}</span>
            <span
              className={`rounded-full px-2 py-0.5 font-mono text-[10px] ${
                l.level === "warning" || l.action.includes("delete")
                  ? "bg-destructive/10 text-destructive"
                  : "bg-primary/10 text-primary"
              }`}
            >
              {l.action}
            </span>
            <span className="w-36 shrink-0 truncate text-muted-foreground">{l.target}</span>
            <span className="min-w-0 flex-1 truncate text-muted-foreground">{l.detail}</span>
            <span className="shrink-0 text-muted-foreground/60">{l.ip}</span>
          </div>
        ))}
        {!items.length && <p className="py-10 text-center text-sm text-muted-foreground">暂无日志</p>}
      </div>
    </div>
  );
}


/* ---------------- 地标管理 ---------------- */
interface AdminLandmark {
  id: number;
  target_id: string;
  name: string;
  name_en: string;
  region: string;
  country: string;
  lat: number;
  lon: number;
  intro: string;
  image_url: string;
  is_active: boolean;
}

function LandmarksTab() {
  const qc = useQueryClient();
  const [q, setQ] = useState("");
  const [submitted, setSubmitted] = useState("");
  const [region, setRegion] = useState("");
  const [active, setActive] = useState<"" | "true" | "false">("");
  const [editing, setEditing] = useState<AdminLandmark | null>(null);
  const [creating, setCreating] = useState(false);
  const [delBox, setDelBox] = useState<AdminLandmark | null>(null);

  const { data } = useQuery({
    queryKey: ["admin-landmarks", submitted, region, active],
    queryFn: async () =>
      (
        await api.get("/admin/landmarks", {
          params: { q: submitted, region, is_active: active || undefined, page_size: 100 },
        })
      ).data as { data: AdminLandmark[]; meta: { total: number } },
  });

  const toggle = useMutation({
    mutationFn: async (id: number) => api.post(`/admin/landmarks/${id}/toggle`),
    onSuccess: () => {
      toast.success("已切换上下架");
      qc.invalidateQueries({ queryKey: ["admin-landmarks"] });
    },
    onError: (e) => toast.error(errMessage(e)),
  });

  const items = data?.data ?? [];

  return (
    <div>
      <div className="flex flex-wrap items-center gap-2">
        <div className="flex items-center gap-2 rounded-xl border border-border/70 bg-background px-3 py-2">
          <Search className="h-4 w-4 text-muted-foreground" />
          <input
            value={q}
            onChange={(e) => setQ(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && setSubmitted(q.trim())}
            placeholder="名称/国家"
            className="min-w-0 flex-1 bg-transparent text-sm outline-none"
          />
        </div>
        <select
          value={region}
          onChange={(e) => setRegion(e.target.value)}
          className="rounded-lg border border-border bg-background px-2 py-1.5 text-xs outline-none"
        >
          <option value="">全部地区</option>
          {["亚洲", "欧洲", "非洲", "北美洲", "南美洲", "大洋洲"].map((r) => (
            <option key={r}>{r}</option>
          ))}
        </select>
        <select
          value={active}
          onChange={(e) => setActive(e.target.value as "" | "true" | "false")}
          className="rounded-lg border border-border bg-background px-2 py-1.5 text-xs outline-none"
        >
          <option value="">全部状态</option>
          <option value="true">上架中</option>
          <option value="false">已下架</option>
        </select>
        <button
          onClick={() => setCreating(true)}
          className="ml-auto rounded-lg bg-primary px-2.5 py-1.5 text-xs font-medium text-primary-foreground transition hover:bg-primary/90"
        >
          + 新增地标
        </button>
      </div>

      <div className="mt-3 space-y-1.5">
        {items.map((lm) => (
          <div key={lm.id} className="flex items-center justify-between gap-2 rounded-xl border border-border bg-muted/40 p-3">
            <div className="flex min-w-0 items-center gap-2.5">
              {lm.image_url ? (
                <img src={lm.image_url} alt="" className="h-9 w-9 shrink-0 rounded-lg object-cover" />
              ) : (
                <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-muted">
                  <MapPin className="h-4 w-4 text-muted-foreground" />
                </div>
              )}
              <div className="min-w-0">
                <div className="flex flex-wrap items-center gap-1.5 text-sm">
                  <span className="font-medium">{lm.name}</span>
                  {lm.name_en && <span className="text-xs text-muted-foreground">{lm.name_en}</span>}
                  {!lm.is_active && (
                    <span className="rounded-full bg-muted px-1.5 py-0.5 text-[10px] text-muted-foreground">已下架</span>
                  )}
                </div>
                <div className="mt-0.5 truncate text-[11px] text-muted-foreground">
                  {lm.region || "未分区"} · {lm.country || "-"} · ({lm.lat.toFixed(2)}, {lm.lon.toFixed(2)})
                </div>
              </div>
            </div>
            <div className="flex shrink-0 gap-1">
              <button
                onClick={() => setEditing(lm)}
                className="rounded-lg border border-border bg-card px-2 py-1 text-[11px] transition hover:bg-accent"
              >
                编辑
              </button>
              <button
                onClick={() => {
                  if (confirm(`确认${lm.is_active ? "下架" : "上架"}「${lm.name}」？下架后地球与搜索不再展示。`))
                    toggle.mutate(lm.id);
                }}
                className={`rounded-lg border px-2 py-1 text-[11px] transition ${
                  lm.is_active
                    ? "border-amber-400/40 text-amber-500 hover:bg-amber-400/10"
                    : "border-emerald-400/40 text-emerald-500 hover:bg-emerald-400/10"
                }`}
              >
                {lm.is_active ? "下架" : "上架"}
              </button>
            </div>
          </div>
        ))}
        {!items.length && <p className="py-10 text-center text-sm text-muted-foreground">无匹配地标</p>}
      </div>

      {(editing || creating) && (
        <LandmarkEditBox
          lm={editing}
          onClose={() => {
            setEditing(null);
            setCreating(false);
          }}
          onSaved={() => {
            setEditing(null);
            setCreating(false);
            qc.invalidateQueries({ queryKey: ["admin-landmarks"] });
          }}
        />
      )}
    </div>
  );
}

function LandmarkEditBox({ lm, onClose, onSaved }: { lm: AdminLandmark | null; onClose: () => void; onSaved: () => void }) {
  const [form, setForm] = useState({
    name: lm?.name ?? "",
    name_en: lm?.name_en ?? "",
    region: lm?.region ?? "",
    country: lm?.country ?? "",
    lat: String(lm?.lat ?? 0),
    lon: String(lm?.lon ?? 0),
    intro: lm?.intro ?? "",
    image_url: lm?.image_url ?? "",
  });

  const save = useMutation({
    mutationFn: async () => {
      const payload = { ...form, lat: Number(form.lat), lon: Number(form.lon) };
      if (lm) return api.put(`/admin/landmarks/${lm.id}`, payload);
      return api.post("/admin/landmarks", payload);
    },
    onSuccess: () => {
      toast.success(lm ? "已保存" : "已创建");
      onSaved();
    },
    onError: (e) => toast.error(errMessage(e)),
  });

  const field = (k: keyof typeof form, label: string, extra?: string) => (
    <label className="block">
      <span className="mb-1 block text-xs text-muted-foreground">{label}</span>
      <input
        value={form[k]}
        onChange={(e) => setForm({ ...form, [k]: e.target.value })}
        className={`w-full rounded-lg border border-border bg-background px-2.5 py-1.5 text-sm outline-none focus:border-primary ${extra ?? ""}`}
      />
    </label>
  );

  return (
    <div className="fixed inset-0 z-[70] flex items-center justify-center p-4">
      <div className="absolute inset-0 bg-black/40" onClick={onClose} />
      <div className="relative max-h-[85vh] w-full max-w-lg overflow-y-auto rounded-2xl border border-border/70 bg-card p-5 text-card-foreground shadow-xl">
        <div className="mb-3 text-sm font-semibold">{lm ? `编辑：${lm.name}` : "新增地标"}</div>
        <div className="grid grid-cols-2 gap-3">
          {field("name", "中文名称 *")}
          {field("name_en", "英文名称")}
          {field("region", "区域（亚洲/欧洲/…）")}
          {field("country", "国家/地区")}
          {field("lat", "纬度 *")}
          {field("lon", "经度 *")}
        </div>
        <div className="mt-3 space-y-3">
          {field("image_url", "百科图片 URL")}
          <label className="block">
            <span className="mb-1 block text-xs text-muted-foreground">百科介绍</span>
            <textarea
              value={form.intro}
              onChange={(e) => setForm({ ...form, intro: e.target.value })}
              rows={4}
              className="w-full rounded-lg border border-border bg-background px-2.5 py-1.5 text-sm outline-none focus:border-primary"
            />
          </label>
        </div>
        <div className="mt-4 flex justify-end gap-2">
          <button onClick={onClose} className="rounded-lg border border-border px-3 py-1.5 text-sm transition hover:bg-accent">
            取消
          </button>
          <button
            onClick={() => save.mutate()}
            disabled={save.isPending || !form.name.trim()}
            className="rounded-lg bg-primary px-3.5 py-1.5 text-sm font-medium text-primary-foreground transition hover:bg-primary/90 disabled:opacity-50"
          >
            {save.isPending ? "保存中…" : "保存"}
          </button>
        </div>
      </div>
    </div>
  );
}

/* ---------------- 回收站 ---------------- */
function TrashTab() {
  const qc = useQueryClient();
  const [kind, setKind] = useState<"journal" | "comment">("journal");

  const { data } = useQuery({
    queryKey: ["admin-trash", kind],
    queryFn: async () => (await api.get("/admin/trash", { params: { kind } })).data.data as {
      id: number;
      kind: string;
      title: string;
      content: string;
      user: string;
      landmark: string;
      deleted_at: string;
    }[],
  });

  const restore = useMutation({
    mutationFn: async (p: { kind: string; id: number }) => api.post(`/admin/trash/${p.kind}/${p.id}/restore`),
    onSuccess: () => {
      toast.success("已恢复");
      qc.invalidateQueries({ queryKey: ["admin-trash"] });
    },
    onError: (e) => toast.error(errMessage(e)),
  });

  const purge = useMutation({
    mutationFn: async () => api.post("/admin/trash/purge"),
    onSuccess: (r) => {
      toast.success(`已物理清理 ${r.data.purged} 条（30 天前）`);
      qc.invalidateQueries({ queryKey: ["admin-trash"] });
    },
    onError: (e) => toast.error(errMessage(e)),
  });

  const items = data ?? [];

  return (
    <div>
      <div className="flex flex-wrap items-center gap-2">
        <div className="grid grid-cols-2 gap-1 rounded-xl bg-muted p-1">
          {(["journal", "comment"] as const).map((k) => (
            <button
              key={k}
              onClick={() => setKind(k)}
              className={`rounded-lg px-3 py-1.5 text-sm font-medium transition ${
                kind === k ? "bg-background shadow" : "text-muted-foreground hover:text-foreground"
              }`}
            >
              {k === "journal" ? "手账" : "评论"}
            </button>
          ))}
        </div>
        <button
          onClick={() => {
            if (confirm("确认物理清理 30 天前删除的内容？不可恢复。")) purge.mutate();
          }}
          disabled={purge.isPending}
          className="ml-auto rounded-lg border border-destructive/40 px-2.5 py-1.5 text-xs text-destructive transition hover:bg-destructive/10 disabled:opacity-50"
        >
          {purge.isPending ? "清理中…" : "清理 30 天前"}
        </button>
      </div>

      <div className="mt-3 space-y-1.5">
        {items.length ? (
          items.map((it) => (
            <div key={it.id} className="flex items-center justify-between gap-2 rounded-xl border border-border bg-muted/40 p-3">
              <div className="min-w-0 flex-1">
                <div className="flex flex-wrap items-center gap-1.5 text-xs text-muted-foreground">
                  <span className="font-medium text-foreground">{it.user}</span>
                  {it.landmark && <span>@ {it.landmark}</span>}
                  <span className="ml-auto">{new Date(it.deleted_at).toLocaleString("zh-CN")}</span>
                </div>
                {it.title && <div className="mt-1 truncate text-sm font-medium">{it.title}</div>}
                <p className="mt-0.5 line-clamp-2 text-sm text-muted-foreground">{it.content}</p>
              </div>
              <button
                onClick={() => restore.mutate({ kind: it.kind, id: it.id })}
                className="shrink-0 rounded-lg border border-emerald-400/40 px-2 py-1 text-[11px] text-emerald-500 transition hover:bg-emerald-400/10"
              >
                恢复
              </button>
            </div>
          ))
        ) : (
          <p className="py-10 text-center text-sm text-muted-foreground">回收站为空</p>
        )}
      </div>
    </div>
  );
}
