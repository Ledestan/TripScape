"""
行旅识景 TripScape / 叙事应用配置
创建日期: 2025-11-24

注册叙事应用，提供:
    1. NarrativeConfig：应用名与默认主键类型

依赖:
    需求文件: requirements.txt
    依赖库:
        Django==5.2

用法:
    由 INSTALLED_APPS 以 "apps.narrative" 引用
"""

from django.apps import AppConfig


class NarrativeConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.narrative"
    verbose_name = "叙事层（TripScape 2.0）"
