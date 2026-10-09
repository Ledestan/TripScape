"""行旅识景 TripScape
创建日期：2025-09-01

公共基础：Token 认证、角色装饰器、限流、敏感词、请求日志中间件、init_tripscape 命令。
"""

from django.apps import AppConfig


class CoreConfig(AppConfig):
    name = "apps.core"
    label = "core"
    verbose_name = "公共基础"
