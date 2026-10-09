"""行旅识景 TripScape
创建日期：2025-09-01

ASGI 入口（UvicornWorker 使用）。
"""

import os
import sys

sys.dont_write_bytecode = True

from django.core.asgi import get_asgi_application

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
os.environ.setdefault("DJANGO_DEPLOY", "prod")

application = get_asgi_application()
