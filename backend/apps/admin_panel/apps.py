"""行旅识景 TripScape
创建日期：2025-09-01

审核中心数据：审计日志 + 敏感词（应用 label 为 audit）。
"""

from django.apps import AppConfig


class AdminPanelConfig(AppConfig):
    name = "apps.admin_panel"
    label = "audit"
    verbose_name = "审核中心"
