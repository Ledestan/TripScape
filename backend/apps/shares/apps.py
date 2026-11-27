"""
行旅识景 TripScape / apps/shares/apps

公开分享：免登录的手账分享链接。
"""

from django.apps import AppConfig


class SharesConfig(AppConfig):
    name = "apps.shares"
    label = "shares"
    verbose_name = "分享"
