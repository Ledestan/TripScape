"""行旅识景 TripScape
创建日期：2025-09-01

Django Ninja API 聚合。

所有业务路由挂载到 /api：
    /api/auth/...        登录注册
    /api/admin/...       管理端（审核中心、用户、看板、全量导出等）
    /api/qa/...          问答（带上下文）
    /api/recognition/... 识别（异步任务 + 结果）
    /api/landmarks/...   地标（光点数据 / 详情 / 搜索）
    /api/comments/...    评论
    /api/journals/...    手账
    /api/footprints/...  足迹（从手账自动生成）
    /api/badges/...      徽章
    /api/notifications/.. 通知
    /api/search/...      全局搜索（Meilisearch）
    /api/shares/...      公开分享
    /api/routes/...      旅行路线
    /api/dashboard/...   运营看板
    /api/exports/...     数据导出
    /api/uploads/...     文件上传
    /api/docs            自动生成的 OpenAPI 文档
"""


from apps.core.auth import GlobalAuth
from ninja import NinjaAPI

api = NinjaAPI(
    title="TripScape API",
    description="行旅识景 · 世界著名地标智能识别平台",
    version="1.0.0",
    auth=GlobalAuth(),
)

from api.admin import router as audit_router
# admin_landmarks 的路由函数已直接挂在 admin router（/landmarks/*），无需单独挂载
from api.auth import router as accounts_router
from api.badges import router as badges_router
from api.comments import router as comments_router
from api.dashboard import router as dashboard_router
from api.footprints import router as footprint_router
from api.journals import router as journals_router
from api.landmarks import router as landmarks_router
from api.likes import router as likes_router
from api.notifications import router as notifications_router
from api.qa import router as qa_router
from api.recognition import router as recognition_router
from api.search import router as search_router
from api.shares import router as shares_router

api.add_router("/auth", accounts_router)
api.add_router("/admin", audit_router)
api.add_router("/badges", badges_router)
api.add_router("/comments", comments_router)
api.add_router("/dashboard", dashboard_router)
api.add_router("/journals", journals_router)
api.add_router("/likes", likes_router)
api.add_router("/landmarks", landmarks_router)
api.add_router("/notifications", notifications_router)
api.add_router("/search", search_router)
api.add_router("/shares", shares_router)


api.add_router("/qa", qa_router)
api.add_router("/recognition", recognition_router)
api.add_router("/footprints", footprint_router)
