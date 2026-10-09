"""行旅识景 TripScape
创建日期：2025-09-01

Django 后台的用户管理配置

注册自定义 User 模型到 Django Admin：列表展示角色/封禁/禁言状态，字段分组含隐私开关与账号管理。仅运维排障用，日常管理走前台管理后台浮窗。
"""

from apps.accounts.models import User
from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    list_display = (
        "id",
        "username",
        "nickname",
        "role",
        "is_active",
        "banned",
        "is_muted",
        "created_at",
    )
    list_filter = ("role", "is_active", "banned")
    search_fields = ("username", "nickname")
    fieldsets = BaseUserAdmin.fieldsets + (
        (
            "TripScape",
            {
                "fields": (
                    "role",
                    "nickname",
                    "avatar",
                    "bio",
                    "public_footprints",
                    "public_journals",
                    "public_comments",
                    "public_favorites",
                    "public_badges",
                )
            },
        ),
        ("账号管理", {"fields": ("banned", "banned_reason", "muted_until")}),
    )
    add_fieldsets = BaseUserAdmin.add_fieldsets + (
        ("TripScape", {"fields": ("role", "nickname")}),
    )
