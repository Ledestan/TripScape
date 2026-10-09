"""行旅识景 TripScape
创建日期：2025-09-01

全局搜索：Meilisearch 索引配置与同步钩子。
"""

from django.apps import AppConfig


class SearchConfig(AppConfig):
    name = "apps.search"
    label = "search"
    verbose_name = "搜索"
