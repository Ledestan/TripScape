"""行旅识景 TripScape
创建日期：2025-09-01

用户模型。

角色（scope 分区）：
- admin        全局管理员，可管理所有功能
- user         普通用户

数据分区说明：
- 全局数据（地标、知识库、徽章定义）：scope="global"
- 局部数据（区域地标）：scope=地标所属 region
- 用户个人数据（手账、评论、足迹、通知、收藏）：owner 字段归属用户
"""

from django.contrib.auth.models import AbstractUser
from django.db import models
from django.utils import timezone


class User(AbstractUser):
    ROLES = (
        ("user", "普通用户"),
        ("admin", "全局管理员"),
    )

    role = models.CharField(
        "角色", max_length=20, choices=ROLES, default="user", db_index=True
    )
    nickname = models.CharField("昵称", max_length=64, blank=True, default="")
    avatar = models.CharField("头像 URL", max_length=512, blank=True, default="")
    bio = models.CharField("个性签名", max_length=255, blank=True, default="")
    # 隐私：五个维度公开开关（默认公开足迹/手账/评论/收藏，徽章默认公开）
    public_footprints = models.BooleanField("公开足迹", default=True)
    public_journals = models.BooleanField("公开手账", default=True)
    public_comments = models.BooleanField("公开评论", default=True)
    public_favorites = models.BooleanField("公开收藏", default=True)
    public_badges = models.BooleanField("公开徽章", default=True)
    # 账号管理（管理员可用）
    banned = models.BooleanField("封禁（禁止登录）", default=False)
    banned_reason = models.CharField("封禁原因", max_length=255, blank=True, default="")
    muted_until = models.DateTimeField("禁言截止", null=True, blank=True)
    locked_until = models.DateTimeField(
        "限制登录截止（null=未限制）", null=True, blank=True
    )
    created_at = models.DateTimeField("注册时间", auto_now_add=True)

    class Meta:
        db_table = "ts_user"
        ordering = ["-id"]

    @property
    def display_name(self):
        return self.nickname or self.username

    @property
    def is_muted(self):
        return bool(self.muted_until and self.muted_until > timezone.now())

    @property
    def is_locked(self):
        """限制登录中：locked_until 为空串 ''/None 表示永久未解除由 is_active 控制；有时间则到期自动解锁。"""
        if self.locked_until is None:
            return False
        return self.locked_until > timezone.now()
