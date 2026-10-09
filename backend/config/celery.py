"""行旅识景 TripScape
创建日期：2025-09-01

Celery 应用。

启动 worker：
    celery -A config worker --loglevel=info
启动 beat：
    celery -A config beat --loglevel=info
"""

import os
import sys

sys.dont_write_bytecode = True

from celery import Celery

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

app = Celery("tripscape")

app.config_from_object("django.conf:settings", namespace="CELERY")
# 任务集中存放在 tasks/ 包（不按 app 分散），显式列出保证注册
app.autodiscover_tasks(related_names=[])

# ----------------------------------------------------------------------
# Celery Beat 定时任务
# ----------------------------------------------------------------------
from celery.schedules import crontab

app.conf.beat_schedule = {
    # 定时清理：每天凌晨 3 点清理过期临时文件与孤儿上传
    "cleanup-runtime-daily": {
        "task": "tasks.maintenance_tasks.cleanup_runtime",
        "schedule": crontab(hour=3, minute=0),
    },
    # 运营统计：每小时刷新一次看板聚合
    "refresh-dashboard-hourly": {
        "task": "tasks.maintenance_tasks_dashboard.refresh_dashboard_stats",
        "schedule": crontab(minute=5),
    },
}

# 显式 import 任务模块，确保装饰器注册
import tasks.maintenance_tasks
import tasks.maintenance_tasks_dashboard
import tasks.recognition_tasks
