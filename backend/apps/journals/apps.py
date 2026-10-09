"""行旅识景 TripScape
创建日期：2025-09-01

旅行手账与足迹：手账保存后自动聚合足迹；二次编辑先进快照审核。
"""

from django.apps import AppConfig


class JournalsConfig(AppConfig):
    name = "apps.journals"
    label = "journals"
    verbose_name = "手账"
