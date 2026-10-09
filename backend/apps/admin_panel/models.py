"""行旅识景 TripScape
创建日期：2025-09-01

审计日志 + 敏感词。
"""

from django.conf import settings
from django.db import models


class AuditLog(models.Model):
    """后台/敏感操作审计（安全底线）。"""

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="操作者",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="audit_logs",
    )
    username = models.CharField(
        "操作者用户名快照", max_length=150, blank=True, default=""
    )
    action = models.CharField("动作", max_length=64, db_index=True)
    target = models.CharField("对象", max_length=128, blank=True, default="")
    detail = models.TextField("详情", blank=True, default="")
    level = models.CharField("级别", max_length=16, default="info")
    ip = models.CharField("来源 IP", max_length=64, blank=True, default="")
    request_id = models.CharField("请求 ID", max_length=32, blank=True, default="")
    created_at = models.DateTimeField("时间", auto_now_add=True, db_index=True)

    class Meta:
        db_table = "ts_audit_log"
        ordering = ["-created_at"]


class SensitiveWord(models.Model):
    """敏感词（管理端维护）。"""

    word = models.CharField("敏感词", max_length=64, unique=True)
    is_active = models.BooleanField("启用", default=True)
    created_at = models.DateTimeField("时间", auto_now_add=True)

    class Meta:
        db_table = "ts_sensitive_word"

    def __str__(self):
        return self.word
