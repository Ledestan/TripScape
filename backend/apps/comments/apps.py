"""行旅识景 TripScape
创建日期：2025-09-01

评论与举报：支持回复、隐藏、软删除；点赞模型在 models_like.py。
"""

from django.apps import AppConfig


class CommentsConfig(AppConfig):
    name = "apps.comments"
    label = "comments"
    verbose_name = "评论"
