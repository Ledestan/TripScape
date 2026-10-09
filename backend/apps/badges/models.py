"""行旅识景 TripScape
创建日期：2025-09-01

成就徽章。

规则（种子数据在 init_tripscape 命令中创建）：
- 打卡类：首次足迹 / 5 个地标 / 15 个地标 / 26 个地标（全图鉴）
- 评论类：首条评论 / 10 条 / 50 条
- 手账类：首篇手账 / 5 篇 / 20 篇
"""

from django.conf import settings
from django.db import models


class Badge(models.Model):
    CATEGORIES = (
        ("footprint", "足迹"),
        ("comment", "评论"),
        ("journal", "手账"),
    )

    code = models.CharField("唯一编码", max_length=64, unique=True)
    name = models.CharField("名称", max_length=64)
    description = models.CharField("描述", max_length=255, blank=True, default="")
    category = models.CharField(
        "类别", max_length=16, choices=CATEGORIES, db_index=True
    )
    threshold = models.PositiveIntegerField("达成阈值", default=1)
    icon = models.CharField("图标（emoji）", max_length=16, default="🏅")
    is_active = models.BooleanField("启用", default=True)

    class Meta:
        db_table = "ts_badge"
        ordering = ["category", "threshold"]

    def __str__(self):
        return f"{self.name}({self.code})"


class UserBadge(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="用户",
        on_delete=models.CASCADE,
        related_name="badges",
    )
    badge = models.ForeignKey(
        Badge,
        verbose_name="徽章",
        on_delete=models.CASCADE,
        related_name="holders",
    )
    awarded_at = models.DateTimeField("获得时间", auto_now_add=True)

    class Meta:
        db_table = "ts_user_badge"
        unique_together = [("user", "badge")]
        ordering = ["-awarded_at"]
