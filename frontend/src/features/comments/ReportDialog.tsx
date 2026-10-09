import { useState } from "react";
import { useMutation } from "@tanstack/react-query";
import { toast } from "sonner";
import { Flag, X } from "lucide-react";

import { api, errMessage } from "@/api/client";

const REASONS = [
  { key: "spam", label: "垃圾广告" },
  { key: "abuse", label: "辱骂攻击" },
  { key: "porn", label: "色情低俗" },
  { key: "politics", label: "政治敏感" },
  { key: "falsehood", label: "虚假信息" },
  { key: "privacy", label: "侵犯隐私" },
  { key: "other", label: "其他" },
];

/** 举报浮窗（分类 + 补充说明） */
export default function ReportDialog({
  targetType,
  targetId,
  onClose,
}: {
  targetType: "comment" | "journal";
  targetId: number;
  onClose: () => void;
}) {
  const [reason, setReason] = useState("spam");
  const [detail, setDetail] = useState("");

  const submit = useMutation({
    mutationFn: async () =>
      api.post("/comments/report", { target_type: targetType, target_id: targetId, reason, detail }),
    onSuccess: () => {
      toast.success("举报已提交，管理员会尽快处理");
      onClose();
    },
    onError: (e) => toast.error(errMessage(e, "举报失败")),
  });

  return (
    <div className="fixed inset-0 z-[60] flex items-center justify-center p-4">
      <div className="absolute inset-0 bg-black/30" onClick={onClose} />
      <div className="relative w-full max-w-sm rounded-2xl border border-border/70 bg-card p-5 text-card-foreground shadow-xl">
        <div className="mb-3 flex items-center justify-between">
          <div className="flex items-center gap-2 font-semibold">
            <Flag className="h-4 w-4 text-destructive" /> 举报{targetType === "comment" ? "评论" : "手账"}
          </div>
          <button onClick={onClose} className="rounded-lg p-1 text-muted-foreground hover:bg-muted">
            <X className="h-4 w-4" />
          </button>
        </div>

        <div className="grid grid-cols-2 gap-1.5">
          {REASONS.map((r) => (
            <button
              key={r.key}
              onClick={() => setReason(r.key)}
              className={`rounded-lg border px-2.5 py-1.5 text-sm transition ${
                reason === r.key
                  ? "border-primary bg-primary/10 text-primary"
                  : "border-border hover:bg-accent"
              }`}
            >
              {r.label}
            </button>
          ))}
        </div>

        <textarea
          value={detail}
          onChange={(e) => setDetail(e.target.value)}
          placeholder="补充说明（可选）"
          rows={2}
          className="mt-3 w-full rounded-xl border border-border bg-background px-3 py-2 text-sm outline-none focus:border-primary"
        />

        <button
          onClick={() => submit.mutate()}
          disabled={submit.isPending}
          className="mt-3 w-full rounded-xl bg-destructive py-2 text-sm font-medium text-white transition hover:bg-destructive/90 disabled:opacity-50"
        >
          {submit.isPending ? "提交中…" : "提交举报"}
        </button>
      </div>
    </div>
  );
}
