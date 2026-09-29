"""
项目名称: 行旅识景：世界著名地标智能识别

模块名称：桌面应用入口

把 Flask 服务跑在后台线程，用 pywebview 打开原生窗口，
外观上就是一个独立桌面应用，而不是浏览器标签页。

用法：
    python desktop.py
"""

import sys
import threading
import time
import warnings

sys.dont_write_bytecode = True
warnings.filterwarnings("ignore", category=UserWarning, module="jieba")

import webview

from app import create_app

HOST = "127.0.0.1"
PORT = 5000
URL = f"http://{HOST}:{PORT}"


def start_flask():
    """在后台线程里启动 Flask 服务。"""
    app = create_app()
    app.run(host=HOST, port=PORT, debug=False, use_reloader=False)


def wait_server_ready(timeout=30):
    """
    等待 Flask 服务就绪。

    参数：
        timeout : int
            最大等待秒数，默认 30

    返回：
        bool，是否在超时前就绪
    """
    import urllib.error
    import urllib.request

    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            urllib.request.urlopen(URL, timeout=1)
            return True
        except (urllib.error.URLError, ConnectionError, OSError):
            time.sleep(0.3)
    return False


def main():
    # 后台启动 Flask
    t = threading.Thread(target=start_flask, daemon=True)
    t.start()

    # 等服务器起来再开窗口，避免白屏
    if not wait_server_ready():
        print("⚠️ 服务器启动超时，窗口仍会打开但可能显示异常")

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
