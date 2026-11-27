"""
行旅识景 TripScape / config/settings/__init__

配置入口：按 DJANGO_DEPLOY 选择 dev / prod，并导出 base 的公共配置。
"""

# 按 DJANGO_DEPLOY 选择环境配置；默认开发环境。
import os

from .base import *  # noqa: F401,F403

if os.environ.get("DJANGO_DEPLOY") == "prod":
    from .prod import *  # noqa: F401,F403
else:
    from .dev import *  # noqa: F401,F403
