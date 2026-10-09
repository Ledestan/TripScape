"""行旅识景 TripScape
创建日期：2025-09-01

点赞模型（手账 / 评论通用）。
"""

from django.conf import settings
from django.db import models

TARGET_TYPES = (("journal", "手账"), ("comment", "评论"))


class Like(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="用户",
        on_delete=models.CASCADE,
        related_name="likes",
    )
    target_type = models.CharField("目标类型", max_length=16, choices=TARGET_TYPES)
    target_id = models.PositiveIntegerField("目标 ID")
    created_at = models.DateTimeField("时间", auto_now_add=True)

    class Meta:
        db_table = "ts_like"
        unique_together = [("user", "target_type", "target_id")]
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.user.username}->{self.target_type}:{self.target_id}"
