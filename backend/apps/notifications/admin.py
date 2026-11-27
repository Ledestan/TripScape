"""
行旅识景 TripScape / apps/notifications/admin

通知后台：注册通知模型，支持按类型与已读状态检索。
"""

from apps.notifications.models import Notification
from django.contrib import admin


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ("id", "user", "type", "title", "is_read", "created_at")
    list_filter = ("type", "is_read")
    search_fields = ("title", "content")
    raw_id_fields = ("user",)
