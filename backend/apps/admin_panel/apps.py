"""
行旅识景 TripScape / apps/admin_panel/apps

审核中心数据：审计日志 + 敏感词（应用 label 为 audit）。
"""

from django.apps import AppConfig


class AdminPanelConfig(AppConfig):
    name = "apps.admin_panel"
    label = "audit"
    verbose_name = "审核中心"
