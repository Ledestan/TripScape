import { useEffect, useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";

import { api, errMessage } from "@/api/client";
import { useAuthStore } from "@/stores/auth";
import { useThemeStore } from "@/stores/theme";
import { FloatingWindow } from "@/components/FloatingWindow";

/* ================================================================== */
/* 设置浮窗（昵称/签名编辑 + 隐私五开关实时保存 + 昼夜切换）              */
/* ================================================================== */

interface PrivacyFlags {
  footprints: boolean;
  journals: boolean;
  comments: boolean;
  favorites: boolean;
  badges: boolean;
}

export default function SettingsWindow({ onClose }: { onClose: () => void }) {
  const { user, setUser } = useAuthStore();
  const { theme, toggle } = useThemeStore();
  const qc = useQueryClient();

  const [nick, setNick] = useState(user?.nickname ?? "");
  const [bio, setBio] = useState(user?.bio ?? "");
  const [saving, setSaving] = useState(false);
  const [privacy, setPrivacy] = useState<PrivacyFlags>({
    footprints: true, journals: true, comments: true, favorites: true, badges: true,
  });

  /* 拉取隐私设置（缓存优先，后台刷新同步） */
  const { data: privacyData } = useQuery({
    queryKey: ["privacy", user?.id],
    queryFn: async () => (await api.get(`/auth/${user!.id}/public`)).data.privacy as PrivacyFlags,
    enabled: !!user,
  });
  useEffect(() => {
    if (privacyData) setPrivacy(privacyData);
  }, [privacyData]);

  /* 保存昵称/签名 */
  const save = async () => {
    setSaving(true);
    try {
      const r = await api.put("/auth/profile", { nickname: nick.trim(), bio: bio.trim() });
      setUser({ ...user!, nickname: r.data.nickname, bio: r.data.bio });
      toast.success("资料已更新");
    } catch (e) {
      toast.error(errMessage(e, "保存失败"));
    } finally {
      setSaving(false);
    }
  };

  /* 隐私开关（即改即存；失败回滚） */
  const togglePrivacy = async (key: keyof PrivacyFlags) => {
    const next = { ...privacy, [key]: !privacy[key] };
    setPrivacy(next);
    try {
      await api.put("/auth/privacy", { [`public_${key}`]: next[key] });
      qc.setQueryData(["privacy", user?.id], next);
      toast.success(next[key] ? "已公开" : "已隐藏");
    } catch {
      setPrivacy(privacy);
      toast.error("设置失败");
    }
  };

  const privacyItems: { key: keyof PrivacyFlags; label: string }[] = [
    { key: "footprints", label: "公开我的足迹" },
    { key: "journals", label: "公开我的手账" },
    { key: "comments", label: "公开我的评论" },
    { key: "favorites", label: "公开我的收藏" },
    { key: "badges", label: "公开我的徽章" },
  ];

  return (
    <FloatingWindow open onClose={onClose} title="设置" width={400} fixedHeight="min(70vh, 600px)">
      <div className="space-y-4">
        {/* 个人资料 */}
        <div>
          <div className="mb-2 text-sm font-semibold">个人资料</div>
          <div className="space-y-1.5">
            <input
              value={nick}
              onChange={(e) => setNick(e.target.value)}
              placeholder="昵称"
              maxLength={64}
              className="w-full rounded-lg border border-border bg-background px-2.5 py-1.5 text-sm outline-none focus:border-primary"
            />
            <input
              value={bio}
              onChange={(e) => setBio(e.target.value)}
              placeholder="个性签名"
              maxLength={255}
              className="w-full rounded-lg border border-border bg-background px-2.5 py-1.5 text-xs outline-none focus:border-primary"
            />
          </div>
          <button
            onClick={save}
            disabled={saving}
            className="mt-2 w-full rounded-xl bg-primary py-2 text-sm font-medium text-primary-foreground transition hover:bg-primary/90 disabled:opacity-50"
          >
            {saving ? "保存中…" : "保存资料"}
          </button>
        </div>

        {/* 隐私设置 */}
        <div>
          <div className="mb-1 text-sm font-semibold">隐私设置</div>
          <p className="mb-2 text-[11px] text-muted-foreground">控制他人在你的公开主页能看到什么</p>
          <div className="space-y-1.5">
            {privacyItems.map((it) => (
              <button
                key={it.key}
                onClick={() => togglePrivacy(it.key)}
                className="flex w-full items-center justify-between rounded-xl border border-border bg-muted/40 px-3.5 py-2.5 text-sm transition hover:bg-accent"
              >
                <span>{it.label}</span>
                <span className={`relative h-5 w-9 rounded-full transition ${privacy[it.key] ? "bg-primary" : "bg-muted-foreground/40"}`}>
                  <span
                    className={`absolute top-0.5 h-4 w-4 rounded-full bg-white shadow transition-all ${privacy[it.key] ? "left-[18px]" : "left-0.5"}`}
                  />
                </span>
              </button>
            ))}
          </div>
        </div>

        {/* 外观 */}
        <div>
          <div className="mb-2 text-sm font-semibold">外观</div>
          <button
            onClick={toggle}
            className="flex w-full items-center justify-between rounded-xl border border-border bg-muted/40 px-3.5 py-2.5 text-sm transition hover:bg-accent"
          >
            <span>昼夜模式</span>
            <span className="text-muted-foreground">{theme === "dark" ? "夜间" : "日间"}</span>
          </button>
        </div>
      </div>
    </FloatingWindow>
  );
}
