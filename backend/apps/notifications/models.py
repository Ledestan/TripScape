"""行旅识景 TripScape
创建日期：2025-09-01

站内通知模型。

触发点：
- 评论被回复
- 手账被审核（通过 / 驳回）
"""

from django.conf import settings
from django.db import models


class Notification(models.Model):
    TYPES = (
        ("reply", "回复"),
        ("moderation", "审核"),
        ("badge", "徽章"),
        ("like", "点赞"),
        ("account", "账号"),
        ("system", "系统"),
    )

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="接收者",
        on_delete=models.CASCADE,
        related_name="notifications",
    )
    type = models.CharField(
        "类型", max_length=16, choices=TYPES, default="system", db_index=True
    )
    title = models.CharField("标题", max_length=128)
    content = models.CharField("内容", max_length=512, blank=True, default="")
    link = models.CharField("跳转链接", max_length=255, blank=True, default="")
    is_read = models.BooleanField("已读", default=False, db_index=True)
    created_at = models.DateTimeField("时间", auto_now_add=True, db_index=True)

    class Meta:
        db_table = "ts_notification"
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["user", "is_read", "-created_at"])]

    def as_dict(self):
        return {
            "id": self.id,
            "type": self.type,
            "title": self.title,
            "content": self.content,
            "link": self.link,
            "is_read": self.is_read,
            "created_at": self.created_at.isoformat(),
        }
