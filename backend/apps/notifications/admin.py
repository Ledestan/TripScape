"""行旅识景 TripScape
创建日期：2025-09-01
"""

from apps.notifications.models import Notification
from django.contrib import admin


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ("id", "user", "type", "title", "is_read", "created_at")
    list_filter = ("type", "is_read")
    search_fields = ("title", "content")
    raw_id_fields = ("user",)
