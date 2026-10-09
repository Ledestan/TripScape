"""行旅识景 TripScape
创建日期：2025-09-01

Django 后台的评论/举报配置

注册 Comment 与 CommentReport（按状态/分类筛选）。日常审核走管理后台。
"""

from apps.comments.models import Comment, CommentReport
from django.contrib import admin


@admin.register(Comment)
class CommentAdmin(admin.ModelAdmin):
    list_display = ("id", "user", "landmark", "parent", "is_hidden", "created_at")
    list_filter = ("is_hidden",)
    search_fields = ("content",)
    raw_id_fields = ("user", "landmark", "parent")


@admin.register(CommentReport)
class ReportAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "reporter",
        "target_type",
        "target_id",
        "reason",
        "status",
        "created_at",
        "handled_at",
    )
    list_filter = ("target_type", "status", "reason")
    raw_id_fields = ("reporter", "handled_by")
