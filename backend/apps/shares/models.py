"""行旅识景 TripScape
创建日期：2025-09-01

公开分享：token -> 目标对象。

不登录也能看（shares API 的 detail 接口 auth=None）。
"""

import secrets

from django.conf import settings
from django.db import models


class ShareLink(models.Model):
    TARGET_TYPES = (("journal", "手账"),)

    token = models.CharField("分享 token", max_length=32, unique=True)
    target_type = models.CharField("目标类型", max_length=16, choices=TARGET_TYPES)
    target_id = models.PositiveIntegerField("目标 ID")
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="创建者",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="share_links",
    )
    created_at = models.DateTimeField("时间", auto_now_add=True)
    expires_at = models.DateTimeField("过期时间", null=True, blank=True)

    class Meta:
        db_table = "ts_share_link"
        ordering = ["-created_at"]
