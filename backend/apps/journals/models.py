"""行旅识景 TripScape
创建日期：2025-09-01

手账模型 —— 替代手动打卡的核心功能。

- 用户编辑图片 + 文字记录旅行
- 手账保存后自动生成 / 累计足迹（Footprint）
- 公开手账可生成分享链接（shares 应用）
- 审核状态：pending / approved / rejected（管理员在审核中心处理）
"""

from apps.landmarks.models import Landmark
from django.conf import settings
from django.db import models


class Journal(models.Model):
    STATUS = (
        ("pending", "待审核"),
        ("approved", "已通过"),
        ("rejected", "已驳回"),
    )

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="作者",
        on_delete=models.CASCADE,
        related_name="journals",
    )
    landmark = models.ForeignKey(
        Landmark,
        verbose_name="地标",
        on_delete=models.PROTECT,
        related_name="journals",
    )
    title = models.CharField("标题", max_length=128)
    content = models.TextField("正文", blank=True, default="")
    images = models.JSONField("图片 URL 列表", default=list, blank=True)
    visited_at = models.DateField("旅行日期", null=True, blank=True)
    is_public = models.BooleanField("是否公开", default=True)
    status = models.CharField(
        "审核状态", max_length=16, choices=STATUS, default="approved", db_index=True
    )
    reject_reason = models.CharField("驳回理由", max_length=255, blank=True, default="")
    deleted_at = models.DateTimeField(
        "软删除时间（null=未删）", null=True, blank=True, db_index=True
    )
    # 二次编辑：已公开手账的修改先进快照，审核通过后替换正文（旧版持续展示）
    edit_pending = models.BooleanField("有修改待审核", default=False, db_index=True)
    pending_edit = models.JSONField("待审修改快照", null=True, blank=True)
    created_at = models.DateTimeField("创建时间", auto_now_add=True)
    updated_at = models.DateTimeField("更新时间", auto_now=True)

    class Meta:
        db_table = "ts_journal"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["user", "-created_at"]),
            models.Index(fields=["landmark", "-created_at"]),
        ]

    def __str__(self):
        return f"{self.user.username}·{self.title}"

    def as_dict(self, with_content=False, viewer=None):
        """序列化手账。

        参数：
            with_content : bool，是否含正文（详情场景）
            viewer : User 或 None，查看者身份决定待审核草稿的可见性——
                     仅作者本人与任意管理员可见（TS-02：公开响应
                     不得泄露 pending_edit）
        """
        can_see_pending = viewer is not None and (
            viewer.id == self.user_id or getattr(viewer, "role", "") == "admin"
        )
        data = {
            "id": self.id,
            "user": {
                "id": self.user_id,
                "username": self.user.username,
                "nickname": self.user.nickname or self.user.username,
                "avatar": self.user.avatar,
            },
            "landmark": {
                "id": self.landmark_id,
                "name": self.landmark.name,
                "target_id": self.landmark.target_id,
                "region": self.landmark.region,
                "lat": float(self.landmark.lat),
                "lon": float(self.landmark.lon),
                "image_url": self.landmark.image_url,
            },
            "title": self.title,
            "images": self.images or [],
            "visited_at": self.visited_at.isoformat() if self.visited_at else None,
            "is_public": self.is_public,
            "status": self.status,
            "edit_pending": self.edit_pending if can_see_pending else False,
            "pending_edit": self.pending_edit if (self.edit_pending and can_see_pending) else None,
            "created_at": self.created_at.isoformat(),
        }
        if with_content:
            data["content"] = self.content
        return data


class Footprint(models.Model):
    """足迹 —— 从已通过手账自动聚合（user × landmark 唯一）。"""

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="用户",
        on_delete=models.CASCADE,
        related_name="footprints",
    )
    landmark = models.ForeignKey(
        Landmark,
        verbose_name="地标",
        on_delete=models.CASCADE,
        related_name="footprints",
    )
    visits = models.PositiveIntegerField("到访次数", default=1)
    hidden = models.BooleanField(
        "是否隐藏（用户自行控制）", default=False, db_index=True
    )
    first_visited_at = models.DateTimeField("首次到访", auto_now_add=True)
    last_visited_at = models.DateTimeField("最近到访", auto_now=True)

    class Meta:
        db_table = "ts_footprint"
        unique_together = [("user", "landmark")]
        ordering = ["-last_visited_at"]

    def __str__(self):
        return f"{self.user.username}@{self.landmark.name}"


class JournalImage(models.Model):
    """手账图片（多图支持，URL 指向 MinIO / 本地 uploads）。"""

    journal = models.ForeignKey(
        Journal,
        verbose_name="手账",
        on_delete=models.CASCADE,
        related_name="journal_images",
    )
    image_url = models.CharField("图片 URL", max_length=512)
    caption = models.CharField("图片说明", max_length=255, blank=True, default="")
    created_at = models.DateTimeField("上传时间", auto_now_add=True)

    class Meta:
        db_table = "ts_journal_image"
        ordering = ["id"]
