"""行旅识景 TripScape
创建日期：2025-09-01
"""

# 按 DJANGO_DEPLOY 选择环境配置；默认开发环境。
import os

from .base import *  # noqa: F401,F403

if os.environ.get("DJANGO_DEPLOY") == "prod":
    from .prod import *  # noqa: F401,F403
else:
    from .dev import *  # noqa: F401,F403
