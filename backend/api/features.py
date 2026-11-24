"""行旅识景 TripScape
创建日期：2025-11-24

特性开关发现接口（TripScape 2.0）。

GET /api/features   返回当前进程的特性开关状态

存在理由：前端需要**运行期**读取 `tripScape2` 开关，而不是把它编译进
dist——否则"默认关闭"的分发包与"开关打开"的验证包会变成两份产物。
开关本身由 settings.TRIPSCAPE2_ENABLED（环境变量）决定，默认 False。
"""

from django.conf import settings
from ninja import Router

router = Router()


@router.get("/features", summary="前端特性开关状态", auth=None)
def features(request):
    """返回特性开关（只暴露布尔值，不含任何配置细节）。"""
    return {
        "tripScape2": bool(getattr(settings, "TRIPSCAPE2_ENABLED", False)),
        "version": "2.0.0",
    }
