import { useState } from "react";
import { toast } from "sonner";

import { api, errMessage } from "@/api/client";
import { useAuthStore } from "@/stores/auth";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { FloatingWindow } from "@/components/FloatingWindow";

/* ================================================================== */
/* 登录浮窗：账号密码登录 / 注册（用户名英文数字下划线，密码≥6含字母数字） */
/* ================================================================== */
export default function LoginWindow({ open, onClose }: { open: boolean; onClose: () => void }) {
  const { setAuth } = useAuthStore();
  const [mode, setMode] = useState<"login" | "register">("login");
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [busy, setBusy] = useState(false);

  const submit = async () => {
    if (busy) return;
    setBusy(true);
    try {
      const url = mode === "login" ? "/auth/login" : "/auth/register";
      const r = await api.post(url, { username: username.trim(), password });
      setAuth(r.data.token, r.data.user ?? r.data);
      toast.success(mode === "login" ? "欢迎回来" : "注册成功，开始探索吧");
      onClose();
      setUsername("");
      setPassword("");
    } catch (e) {
      toast.error(errMessage(e, mode === "login" ? "登录失败" : "注册失败"));
    } finally {
      setBusy(false);
    }
  };

  return (
    <FloatingWindow open={open} onClose={onClose} title={mode === "login" ? "登录" : "注册"} width={360}>
      <form
        className="space-y-3"
        onSubmit={(e) => {
          e.preventDefault();
          submit();
        }}
      >
        <div className="mb-4 grid grid-cols-2 gap-1 rounded-xl bg-muted p-1">
          {(["login", "register"] as const).map((m) => (
            <button
              key={m}
              type="button"
              onClick={() => setMode(m)}
              className={`rounded-lg py-1.5 text-sm font-medium transition ${
                mode === m ? "bg-background shadow" : "text-muted-foreground hover:text-foreground"
              }`}
            >
              {m === "login" ? "登录" : "注册"}
            </button>
          ))}
        </div>

        <div className="space-y-1">
          <Input
            value={username}
            onChange={(e) => setUsername(e.target.value)}
            placeholder="用户名（英文/数字/下划线）"
            autoComplete="username"
          />
        </div>
        <div className="space-y-1">
          <Input
            type="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            placeholder="密码（≥6位，含字母和数字）"
            autoComplete={mode === "login" ? "current-password" : "new-password"}
          />
        </div>

        <Button type="submit" disabled={busy || !username || !password} className="w-full">
          {busy ? "请稍候…" : mode === "login" ? "登录" : "注册"}
        </Button>
      </form>
    </FloatingWindow>
  );
}
