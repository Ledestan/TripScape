"""行旅识景 TripScape
创建日期：2025-09-01

看板定时任务。
"""

from celery import shared_task


@shared_task(name="tasks.maintenance_tasks_dashboard.refresh_dashboard_stats")
def refresh_dashboard_stats():
    from services import stats_service

    return stats_service.refresh_cache()
