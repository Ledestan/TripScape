import { useEffect, useRef, useState } from "react";

import { toast } from "sonner";

import { User, Moon, Sun, LogOut, LayoutDashboard, MapPin, LogIn, Settings } from "lucide-react";



import { useAuthStore } from "@/stores/auth";

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

        className="absolute right-0 top-0 z-30 flex items-center gap-[var(--ui-gap)]"

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

              onClick={() => setMenuOpen((v) => !v)}

              className={btn}

              style={{ width: "var(--icon-btn)", height: "var(--icon-btn)" }}

              title={user.nickname}

            >

              {user.avatar ? (

                <img src={user.avatar} alt="" className="h-[75%] w-[75%] rounded-full object-cover" />

              ) : (

                <User className="h-[45%] w-[45%]" />

              )}

            </button>



            {menuOpen && (

              <div className="absolute right-0 top-[calc(var(--icon-btn)+var(--ui-gap))] z-50 w-52 overflow-hidden rounded-2xl border border-border/70 bg-card p-1.5 text-card-foreground shadow-xl">

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

      {profileOpen && <ProfileWindow onClose={() => setProfileOpen(false)} />}

      {settingsOpen && <SettingsWindow onClose={() => setSettingsOpen(false)} />}

      {adminOpen && <AdminPanelWindow onClose={() => setAdminOpen(false)} />}

    </>

  );

}



function MenuItem({ icon, label, onClick }: { icon: React.ReactNode; label: string; onClick: () => void }) {

  return (

    <button onClick={onClick} className="flex w-full items-center gap-2.5 rounded-xl px-3 py-2 text-sm hover:bg-accent">

      {icon}

      {label}

    </button>

  );

}

