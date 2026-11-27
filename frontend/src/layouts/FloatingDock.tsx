/**
 * 行旅识景 TripScape / src/layouts/FloatingDock
 *
 * 右上角头像菜单：个人主页、旅行手记、设置与管理后台入口。
 */

import { useEffect, useRef, useState } from "react";
import { toast } from "sonner";
import { User, Moon, Sun, LogOut, LayoutDashboard, MapPin, LogIn, Settings } from "lucide-react";
import { useAuthStore } from "@/stores/auth";
import { Avatar } from "@/components/ui/avatar";
import { useThemeStore } from "@/stores/theme";
import LoginWindow from "@/layouts/LoginWindow";
import ProfileWindow from "@/layouts/ProfileWindow";
import SettingsWindow from "@/layouts/SettingsWindow";
import AdminPanelWindow from "@/features/admin/AdminPanelWindow";

/**

 * 右上角浮动按钮组：

 * [昼夜切换] [登录(未登录) / 头像(已登录，点击弹菜单，点外部关闭)]

 * - 实底卡片 + 细边阴影（夜间不融入背景）

 * - 通知入口在左下消息栏；个人中心 / 设置 / 管理后台均为独立浮窗组件

 */

export default function FloatingDock() {

  const { user, token, logout } = useAuthStore();

  const { theme, toggle } = useThemeStore();

  const [loginOpen, setLoginOpen] = useState(false);

  const [menuOpen, setMenuOpen] = useState(false);

  const [profileOpen, setProfileOpen] = useState(false);
  const [profileTab, setProfileTab] = useState<"footprints" | "journals" | "comments" | "favorites" | "badges">("footprints");
  // 消息中心等位置通过事件打开个人主页，避免各自维护一份开关
  useEffect(() => {
    const onOpenProfile = (event: Event) => {
      const detail = (event as CustomEvent<{ tab?: string }>).detail;
      const tab = detail?.tab;
      if (
        tab === "footprints" ||
        tab === "journals" ||
        tab === "comments" ||
        tab === "favorites" ||
        tab === "badges"
      ) {
        setProfileTab(tab);
      } else {
        setProfileTab("footprints");
      }
      setProfileOpen(true);
    };
    window.addEventListener("ts:open-profile", onOpenProfile);
    return () => window.removeEventListener("ts:open-profile", onOpenProfile);
  }, []);


  const [settingsOpen, setSettingsOpen] = useState(false);

  const [adminOpen, setAdminOpen] = useState(false);

  const menuRef = useRef<HTMLDivElement>(null);

  useEffect(() => {

    const onOpenLogin = () => setLoginOpen(true);

    window.addEventListener("ts:open-login", onOpenLogin);

    return () => window.removeEventListener("ts:open-login", onOpenLogin);

  }, []);

  useEffect(() => {

    if (!menuOpen) return;

    const onDown = (e: MouseEvent) => {

      if (menuRef.current && !menuRef.current.contains(e.target as Node)) setMenuOpen(false);

    };

    document.addEventListener("mousedown", onDown);

    return () => document.removeEventListener("mousedown", onDown);

  }, [menuOpen]);

  const is_admin = user?.role === "admin" || user?.role === "local_admin";

  const btn =

    "flex items-center justify-center rounded-full border border-border/70 bg-card text-card-foreground shadow-md transition hover:bg-accent hover:text-accent-foreground active:scale-95";

  return (

    <>

      <div

        className="absolute right-0 top-0 z-40 flex items-center gap-[var(--ui-gap)]"

        style={{ right: "var(--ui-pad)", top: "var(--ui-pad)" }}

      >

        <button

          onClick={toggle}

          className={btn}

          style={{ width: "var(--icon-btn)", height: "var(--icon-btn)" }}

          title="切换日间/夜间模式"

        >

          {theme === "dark" ? <Sun className="h-[45%] w-[45%]" /> : <Moon className="h-[45%] w-[45%]" />}

        </button>

        {token && user ? (

          <div className="relative" ref={menuRef}>

            <button

              data-testid="dock-avatar"
              onClick={() => setMenuOpen((v) => !v)}

              className={btn}

              style={{ width: "var(--icon-btn)", height: "var(--icon-btn)" }}

              title={user.nickname}

            >

              {user.avatar ? (

                <Avatar src={user.avatar} name={user.nickname} size={26} />

              ) : (

                <User className="h-[45%] w-[45%]" />

              )}

            </button>

            {menuOpen && (

              <div className="absolute right-0 top-[calc(var(--icon-btn)+var(--ui-gap))] z-50 w-52 overflow-hidden rounded-panel border border-border/70 bg-card p-1.5 text-card-foreground shadow-xl">

                <div className="px-3 py-2">

                  <div className="truncate text-sm font-medium">{user.nickname}</div>

                  <div className="truncate text-xs text-muted-foreground">@{user.username}</div>

                </div>

                <div className="my-1 h-px bg-border" />

                <MenuItem

                  icon={<MapPin className="h-3.5 w-3.5" />}

                  label="个人主页"

                  onClick={() => {

                    setMenuOpen(false);

                    // 从菜单进入时始终从足迹页开始；徽章页只由通知跳转指定
                    setProfileTab("footprints");
                    try {
                      sessionStorage.setItem("ts:profile-tab", "footprints");
                    } catch {
                      /* 隐私模式忽略 */
                    }

                    setProfileOpen(true);

                  }}

                />

                <MenuItem

                  icon={<Settings className="h-3.5 w-3.5" />}

                  label="设置"

                  onClick={() => {

                    setMenuOpen(false);

                    setSettingsOpen(true);

                  }}

                />

                {is_admin && (

                  <>

                    <div className="my-1 h-px bg-border" />

                    <MenuItem

                      icon={<LayoutDashboard className="h-3.5 w-3.5" />}

                      label="管理后台"

                      onClick={() => {

                        setMenuOpen(false);

                        setAdminOpen(true);

                      }}

                    />

                  </>

                )}

                <div className="my-1 h-px bg-border" />

                <button

                  onClick={() => {

                    logout();

                    setMenuOpen(false);

                    toast.success("已退出登录");

                  }}

                  className="flex w-full items-center gap-2.5 rounded-xl px-3 py-2 text-sm text-destructive hover:bg-accent"

                >

                  <LogOut className="h-3.5 w-3.5" /> 退出登录

                </button>

              </div>

            )}

          </div>

        ) : (

          <button

            onClick={() => setLoginOpen(true)}

            className={`${btn} gap-1.5 px-3.5`}

            style={{ height: "var(--icon-btn)", width: "auto", fontSize: "var(--ui-fs-sm)" }}

            title="登录"

          >

            <LogIn className="h-[38%] w-[38%]" />

            <span className="whitespace-nowrap">登录</span>

          </button>

        )}

      </div>

      <LoginWindow open={loginOpen} onClose={() => setLoginOpen(false)} />

      {profileOpen && (
        <ProfileWindow
          key={profileTab}
          initialTab={profileTab}
          onClose={() => setProfileOpen(false)}
        />
      )}

      {settingsOpen && <SettingsWindow onClose={() => setSettingsOpen(false)} />}

      {adminOpen && <AdminPanelWindow onClose={() => setAdminOpen(false)} />}

    </>

  );

}

function MenuItem({ icon, label, onClick, testId }: { icon: React.ReactNode; label: string; onClick: () => void; testId?: string }) {

  return (

    <button data-testid={testId} onClick={onClick} className="flex w-full items-center gap-2.5 rounded-xl px-3 py-2 text-sm hover:bg-accent">

      {icon}

      {label}

    </button>

  );

}
