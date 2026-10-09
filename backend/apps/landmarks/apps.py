"""行旅识景 TripScape
创建日期：2025-09-01

地标与知识库：地球光点数据、百科、识别记录、收藏。
"""

from django.apps import AppConfig


class LandmarksConfig(AppConfig):
    name = "apps.landmarks"
    label = "landmarks"
    verbose_name = "地标"
