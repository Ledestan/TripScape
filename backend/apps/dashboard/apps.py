"""
行旅识景 TripScape / apps/dashboard/apps

运营看板：按日聚合的用户/内容/识别统计。
"""

from django.apps import AppConfig


class DashboardConfig(AppConfig):
    name = "apps.dashboard"
    label = "dashboard"
    verbose_name = "看板"
