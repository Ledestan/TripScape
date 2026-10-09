"""行旅识景 TripScape
创建日期：2025-09-01

Django 后台的手账配置

注册 Journal 模型。日常审核走管理后台浮窗。
"""

from apps.journals.models import Footprint, Journal, JournalImage
from django.contrib import admin


@admin.register(Journal)
class JournalAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "title",
        "user",
        "landmark",
        "visited_at",
        "is_public",
        "status",
        "created_at",
    )
    list_filter = ("status", "is_public")
    search_fields = ("title", "content")
    raw_id_fields = ("user", "landmark")


@admin.register(Footprint)
class FootprintAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "user",
        "landmark",
        "visits",
        "first_visited_at",
        "last_visited_at",
    )
    raw_id_fields = ("user", "landmark")


@admin.register(JournalImage)
class JournalImageAdmin(admin.ModelAdmin):
    list_display = ("id", "journal", "caption", "created_at")
    raw_id_fields = ("journal",)
