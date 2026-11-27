"""
行旅识景 TripScape / config/settings/dev

开发环境覆盖：DEBUG 跟随 .env 的 DJANGO_DEBUG + 允许所有 Host。

- 源码运行：DEBUG 由 .env 决定（默认开启，便于本地调试）。
- PyInstaller 冻结（分发包）与 DISPLAY 演示：强制关闭 DEBUG
  （TS-12：异常响应不得向客户端暴露 Python 堆栈与内部路径）。
- 之前这里无条件 `DEBUG = not frozen`，导致 .env 里写的
  DJANGO_DEBUG=false 被覆盖：任何 500 都会回渲染 Django 调试页
  （含堆栈、局部变量与完整 settings），属于高危信息泄露。
"""

import sys

from apps.core.checks import resolve_debug

from .base import env

DEBUG = resolve_debug(
    env.bool("DJANGO_DEBUG", default=True), bool(getattr(sys, "frozen", False))
)
# Host 白名单跟随 .env（默认放开，便于局域网/桌面端直接访问）。
# 之前无条件 ["*"]，会把 .env 里的 DJANGO_ALLOWED_HOSTS 覆盖掉。
ALLOWED_HOSTS = env.list("DJANGO_ALLOWED_HOSTS", default=["*"])
