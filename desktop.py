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

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "backend"))

import webview

HOST = "127.0.0.1"
PORT = 8000
URL = f"http://{HOST}:{PORT}"


def start_django():
    """在后台线程里启动 Django 开发服务器。"""
    import os

    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
    os.environ.setdefault("DJANGO_DEPLOY", "dev")

    from django.core.management import execute_from_command_line

    execute_from_command_line(
        ["manage.py", "runserver", f"{HOST}:{PORT}", "--noreload"]
    )


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
    # 后台启动 Django
    t = threading.Thread(target=start_django, daemon=True)
    t.start()

    # 等服务器起来再开窗口，避免白屏
    if not wait_server_ready():
        print("服务器启动超时，窗口仍会打开但可能显示异常")

    webview.create_window(
        "行旅识景 · 世界著名地标智能识别",
        URL,
        width=1280,
        height=820,
        min_size=(960, 640),
        background_color="#9bb7d7",
    )
    webview.start()


if __name__ == "__main__":
    main()
