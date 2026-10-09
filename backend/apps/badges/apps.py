"""行旅识景 TripScape
创建日期：2025-09-01

成就徽章：定义与用户获得记录，阈值达成时由服务层发放。
"""

from django.apps import AppConfig


class BadgesConfig(AppConfig):
    name = "apps.badges"
    label = "badges"
    verbose_name = "徽章"
