"""行旅识景 TripScape
创建日期：2025-09-01

站内通知：回复/审核/徽章/点赞/账号状态五类。
"""

from django.apps import AppConfig


class NotificationsConfig(AppConfig):
    name = "apps.notifications"
    label = "notifications"
    verbose_name = "通知"
