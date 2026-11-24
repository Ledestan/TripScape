"""行旅识景 TripScape
创建日期：2025-11-24

叙事应用配置。
"""

from django.apps import AppConfig


class NarrativeConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.narrative"
    verbose_name = "叙事层（TripScape 2.0）"
