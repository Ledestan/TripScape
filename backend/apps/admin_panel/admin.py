"""
行旅识景 TripScape / apps/admin_panel/admin

Django 后台的审计/敏感词配置

注册 AuditLog 与 SensitiveWord，供运维在 /django-admin 排查。
"""

from apps.admin_panel.models import AuditLog, SensitiveWord
from django.contrib import admin


@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    list_display = ("id", "username", "action", "target", "level", "ip", "created_at")
    list_filter = ("level", "action")
    search_fields = ("username", "action", "target")
    raw_id_fields = ("user",)


@admin.register(SensitiveWord)
class SensitiveWordAdmin(admin.ModelAdmin):
    list_display = ("word", "is_active", "created_at")
    list_filter = ("is_active",)
