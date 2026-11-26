"""
行旅识景 TripScape / apps/comments/models
创建日期: 2025-09-01

地标评论模型（公开展示 + 举报 + 审核隐藏）。
"""

from apps.landmarks.models import Landmark
from django.conf import settings
from django.db import models


class Comment(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="评论者",
        on_delete=models.CASCADE,
        related_name="comments",
    )
    landmark = models.ForeignKey(
        Landmark,
        verbose_name="地标",
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name="comments",
    )
    journal = models.ForeignKey(
        "journals.Journal",
        verbose_name="手账",
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name="comments",
    )
    parent = models.ForeignKey(
        "self",
        verbose_name="所属顶层评论",
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name="replies",
    )
    reply_to = models.ForeignKey(
        "self",
        verbose_name="被回复的评论（用于 @ 提醒）",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="mentioned_in",
    )
    content = models.TextField("内容")
    is_hidden = models.BooleanField("是否隐藏", default=False, db_index=True)
    deleted_at = models.DateTimeField(
        "软删除时间（null=未删）", null=True, blank=True, db_index=True
    )
    created_at = models.DateTimeField("时间", auto_now_add=True, db_index=True)

    class Meta:
        db_table = "ts_comment"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["landmark", "-created_at"]),
            models.Index(fields=["journal", "-created_at"]),
        ]

    def as_dict(self):
        return {
            "id": self.id,
            "user": {
                "id": self.user_id,
                "username": self.user.username,
                "nickname": self.user.nickname or self.user.username,
                "avatar": self.user.avatar,
            },
            "landmark_id": self.landmark_id,
            "landmark_name": self.landmark.name if self.landmark_id else "",
            "journal_id": self.journal_id,
            "journal_title": self.journal.title if self.journal_id else "",
            "parent_id": self.parent_id,
            "reply_to_id": self.reply_to_id,
            "reply_to_nickname": (
                (self.reply_to.user.nickname or self.reply_to.user.username)
                if self.reply_to_id
                else ""
            ),
            "content": self.content,
            "created_at": self.created_at.isoformat(),
        }


class CommentReport(models.Model):
    """评论 / 手账举报（分类 + 处理状态）。"""

    TARGET_TYPES = (("comment", "评论"), ("journal", "手账"))
    REASONS = (
        ("spam", "垃圾广告"),
        ("abuse", "辱骂攻击"),
        ("porn", "色情低俗"),
        ("politics", "政治敏感"),
        ("falsehood", "虚假信息"),
        ("privacy", "侵犯隐私"),
        ("other", "其他"),
    )
    STATUS = (
        ("pending", "待处理"),
        ("resolved", "已下架"),
        ("dismissed", "仅标记"),
        ("rejected", "已驳回"),
    )

    reporter = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="举报人",
        on_delete=models.CASCADE,
        related_name="reports",
    )
    target_type = models.CharField("目标类型", max_length=16, choices=TARGET_TYPES)
    target_id = models.PositiveIntegerField("目标 ID")
    reason = models.CharField(
        "举报分类", max_length=20, choices=REASONS, default="other"
    )
    detail = models.CharField("补充说明", max_length=255, blank=True, default="")
    status = models.CharField(
        "处理状态", max_length=16, choices=STATUS, default="pending", db_index=True
    )
    handled_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="处理人",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="handled_reports",
    )
    resolution = models.CharField(
        "处理结果说明", max_length=255, blank=True, default=""
    )
    created_at = models.DateTimeField("时间", auto_now_add=True)
    handled_at = models.DateTimeField("处理时间", null=True, blank=True)

    class Meta:
        db_table = "ts_report"
        ordering = ["-created_at"]


from apps.comments.models_like import Like  # noqa: E402
