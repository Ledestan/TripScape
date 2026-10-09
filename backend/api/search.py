"""行旅识景 TripScape
创建日期：2025-09-01

搜索 API。

GET /api/search/
    ?q=关键词
    &kind=all|landmark|comment|journal|user
    &landmark_id=1&user_id=2          按地标/用户筛选
    &start=1700000000&end=1800000000  时间戳范围
    &sort=relevance|time|hot
"""


from apps.core.auth import login_required
from ninja import Router
from services import search_service

router = Router()


@router.get("/", summary="全局搜索（地标/评论/手账/用户）", auth=None)
def search(
    request,
    q: str = "",
    kind: str = "all",
    landmark_id: int = None,
    user_id: int = None,
    start: int = None,
    end: int = None,
    sort: str = "relevance",
    page: int = 1,
    page_size: int = 20,
):
    """全局搜索：地标/用户/手账（Meilisearch 降级 ORM）。"""
    result = search_service.global_search(
        query=q,
        kind=kind,
        landmark_id=landmark_id,
        user_id=user_id,
        start_ts=start,
        end_ts=end,
        sort=sort,
        page=page,
        page_size=min(page_size, 50),
    )
    return {
        "success": True,
        "data": result["items"],
        "source": result["source"],
        "meta": {"page": page},
    }
