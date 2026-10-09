"""行旅识景 TripScape
创建日期：2025-09-01
"""

from apps.shares.models import ShareLink
from django.contrib import admin


@admin.register(ShareLink)
class ShareLinkAdmin(admin.ModelAdmin):
    list_display = ("token", "target_type", "target_id", "created_by", "created_at")
