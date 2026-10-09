"""行旅识景 TripScape
创建日期：2025-09-01

Django 后台的徽章配置

注册 Badge 模型。徽章数据日常由 seed_badges.sql + 管理后台维护。
"""

from apps.badges.models import Badge, UserBadge
from django.contrib import admin


@admin.register(Badge)
class BadgeAdmin(admin.ModelAdmin):
    list_display = ("code", "name", "category", "threshold", "icon", "is_active")
    list_filter = ("category", "is_active")


@admin.register(UserBadge)
class UserBadgeAdmin(admin.ModelAdmin):
    list_display = ("id", "user", "badge", "awarded_at")
    raw_id_fields = ("user", "badge")
