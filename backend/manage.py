#!/usr/bin/env python
"""行旅识景 TripScape
创建日期：2025-09-01

Django 管理入口（backend/）。

用法（在仓库根目录执行）：
    python backend/manage.py migrate
    python backend/manage.py init_tripscape
    python backend/manage.py runserver
"""


"""Django 管理入口

所有 manage.py 子命令的统一入口：runserver / migrate / makemigrations / init_tripscape / celery 相关。执行时全局禁用 __pycache__。
"""

import os
import sys
from pathlib import Path

sys.dont_write_bytecode = True
os.environ["PYTHONDONTWRITEBYTECODE"] = "1"

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))


def main():
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
    from django.core.management import execute_from_command_line

    execute_from_command_line(sys.argv)


if __name__ == "__main__":
    main()
