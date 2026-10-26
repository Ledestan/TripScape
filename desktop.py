"""行旅识景 TripScape
创建日期：2025-09-01

项目名称: 行旅识景：世界著名地标智能识别

模块名称：桌面应用入口

把 Django 服务跑在后台线程，用 pywebview 打开原生窗口，
外观上就是一个独立桌面应用，而不是浏览器标签页。

用法（在仓库根目录执行）：
    python desktop.py
"""

import sys
import threading
import time
import warnings
from pathlib import Path

sys.dont_write_bytecode = True
warnings.filterwarnings("ignore", category=UserWarning, module="jieba")

# PyInstaller 冻结时资源在 _internal/（6.x 布局）；源码运行在仓库根
if getattr(sys, "frozen", False):
    ROOT = Path(sys.executable).resolve().parent / "_internal"
else:
    ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "backend"))

import webview

HOST = "127.0.0.1"
PORT = 8000
URL = f"http://{HOST}:{PORT}"

# 后台线程启动异常（主线程据此报错退出，而不是打开白屏窗口）
_STARTUP_ERROR = []


def _mysql_reachable() -> bool:
    """探测 .env 配置的 MySQL 是否可连接（决定是否回退 SQLite）。

    返回：
        bool，可连接 True；未配置/连不上 False。
    """
    import socket

    try:
        import environ

        env = environ.Env()
        env.read_env(str(ROOT / ".env"))
        host = env.str("MYSQL_HOST", default="127.0.0.1")
        port = env.int("MYSQL_PORT", default=3306)
    except Exception:
        host, port = "127.0.0.1", 3306
    try:
        with socket.create_connection((host, port), timeout=1.5):
            return True
    except OSError:
        return False


def start_django():
    """在后台线程里启动 Django 开发服务器（冻结环境切工作目录到 exe 侧）。"""
    import os
    import traceback

    try:
        os.chdir(ROOT)  # runtime/ 等相对路径以 exe 目录为根
        os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
        os.environ.setdefault("DJANGO_DEPLOY", "dev")

        # 数据库选择：打包版固定 SQLite；源码运行 MySQL 可用则用 MySQL，
        # 连不上自动回退 SQLite（本地无 MySQL 也能一键启动）
        if getattr(sys, "frozen", False):
            os.environ["DB_ENGINE"] = "sqlite"
        elif not _mysql_reachable():
            os.environ["DB_ENGINE"] = "sqlite"
            print("MySQL 不可用，已自动切换 SQLite（runtime/tripscape.db）")

        from django.core.management import execute_from_command_line

        # 首次启动自动建库（迁移 + 种子账号 + 种子数据）
        if not (ROOT / "runtime" / "tripscape.db").exists():
            execute_from_command_line(["manage.py", "migrate", "--noinput"])
            execute_from_command_line(["manage.py", "init_tripscape"])

        execute_from_command_line(
            ["manage.py", "runserver", f"{HOST}:{PORT}", "--noreload"]
        )
    except Exception as exc:
        _STARTUP_ERROR.append(f"{exc}")
        traceback.print_exc()


def wait_server_ready(timeout=60):
    """
    等待 Django 服务就绪（首次会加载识别模型，给足超时）。

    参数：
        timeout : int
            最大等待秒数，默认 60

    返回：
        bool，是否在超时前就绪
    """
    import urllib.error
    import urllib.request

    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            urllib.request.urlopen(f"{URL}/healthz", timeout=1)
            return True
        except (urllib.error.URLError, ConnectionError, OSError):
            time.sleep(0.3)
    return False


def main():
    # 冻结环境：确保 .env 是分发配置（sqlite、无密码）；
    # 源码运行不碰（用开发者自己的 .env）
    if getattr(sys, "frozen", False):
        env_file = ROOT / ".env"
        if not env_file.exists():
            env_file.write_text(
                "# TripScape 分发环境配置（SQLite 模式）\n"
                "DB_ENGINE=sqlite\n"
                "HF_ENDPOINT=https://hf-mirror.com\n",
                encoding="utf-8",
            )

    # 后台启动 Django
    t = threading.Thread(target=start_django, daemon=True)
    t.start()

    # 等服务器起来再开窗口，避免白屏（识别/问答模型惰性加载，超时给足）
    ready = wait_server_ready(timeout=120)
    if not ready:
        reason = _STARTUP_ERROR[-1] if _STARTUP_ERROR else "服务未在 120 秒内就绪"
        print("\n启动失败：" + reason)
        print("常见原因：数据库不可用、端口 8000 被占用、前端未构建（frontend/dist 缺失）。")
        sys.exit(1)

    webview.create_window(
        "行旅识景 · 世界著名地标智能识别",
        URL,
        width=1280,
        height=820,
        min_size=(960, 640),
        background_color="#0a1220",
    )
    webview.start()


if __name__ == "__main__":
    main()
