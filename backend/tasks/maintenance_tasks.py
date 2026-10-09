"""行旅识景 TripScape
创建日期：2025-09-01

core 定时任务：runtime 目录清理。
"""

import logging
import time
from pathlib import Path

from celery import shared_task
from django.conf import settings

logger = logging.getLogger("tripscape.tasks")


@shared_task(name="tasks.maintenance_tasks.cleanup_runtime")
def cleanup_runtime(max_age_days: int = 7):
    """清理 runtime/tmp 与 runtime/uploads 中超过 max_age_days 的孤儿文件。"""
    removed = 0
    freed = 0
    now = time.time()
    cutoff = now - max_age_days * 86400
    for folder in (settings.RUNTIME_TMP_DIR,):
        folder = Path(folder)
        if not folder.exists():
            continue
        for f in folder.rglob("*"):
            if f.is_file() and f.stat().st_mtime < cutoff:
                size = f.stat().st_size
                try:
                    f.unlink()
                    removed += 1
                    freed += size
                except OSError:
                    pass
    logger.info(
        "runtime 清理完成：删除 %s 个文件，释放 %.1f MB", removed, freed / 1048576
    )
    return {"removed": removed, "freed_bytes": freed}
