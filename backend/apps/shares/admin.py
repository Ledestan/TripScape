"""
行旅识景 TripScape / apps/shares/admin

分享链接后台：注册分享记录，便于排查失效或越权链接。
"""

from apps.shares.models import ShareLink
from django.contrib import admin


@admin.register(ShareLink)
class ShareLinkAdmin(admin.ModelAdmin):
    list_display = ("token", "target_type", "target_id", "created_by", "created_at")
