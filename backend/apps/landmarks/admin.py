"""行旅识景 TripScape
创建日期：2025-09-01

Django 后台的地标配配置

注册 Landmark 模型。地标数据由 seed_landmarks.sql + 管理后台维护。
"""

from apps.landmarks.models import (Landmark, QAContext,
                                   RecognitionRecord, UserFavorite)
from django.contrib import admin


@admin.register(Landmark)
class LandmarkAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "target_id",
        "name",
        "region",
        "country",
        "view_count",
        "is_active",
    )
    list_filter = ("region", "is_active")
    search_fields = ("name", "target_id", "name_en")


@admin.register(RecognitionRecord)
class RecognitionAdmin(admin.ModelAdmin):
    list_display = ("id", "user", "landmark", "confidence", "elapsed_ms", "created_at")
    list_filter = ("landmark",)
    date_hierarchy = "created_at"


@admin.register(UserFavorite)
class FavoriteAdmin(admin.ModelAdmin):
    list_display = ("id", "user", "landmark", "created_at")


@admin.register(QAContext)
class QAContextAdmin(admin.ModelAdmin):
    list_display = ("id", "session_id", "question", "landmark_name", "created_at")
    list_filter = ("landmark_name",)
