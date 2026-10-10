"""行旅识景 TripScape
创建日期：2025-09-01

开发环境覆盖：DEBUG 开启 + 允许所有 Host。

打包分发的桌面应用也走本配置（DJANGO_DEPLOY=dev），但必须关 DEBUG
（TS-12：异常响应不得向客户端暴露 Python 堆栈与内部路径）。
"""

import sys

# 源码运行：开发态开 DEBUG；PyInstaller 冻结（分发包）：强制关闭
DEBUG = not getattr(sys, "frozen", False)
ALLOWED_HOSTS = ["*"]
