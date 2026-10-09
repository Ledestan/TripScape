"""行旅识景 TripScape
创建日期：2025-09-01

公开分享 API（免登录）。

GET /api/shares/{token}   通过 token 查看公开手账
"""


from apps.journals.models import Journal
from ninja import Router
from ninja.errors import HttpError
from services import share_service

router = Router()


@router.get("/{token}", summary="公开分享内容（免登录）", auth=None)
def get_share(request, token: str):
    """免登录查看分享的手账（按 token）。"""
    resolved = share_service.resolve(token)
    if not resolved:
        raise HttpError(404, "分享链接不存在或已失效")
    target_type, target_id = resolved
    if target_type == "journal":
        j = (
            Journal.objects.filter(id=target_id)
            .select_related("landmark", "user")
            .first()
        )
        if not j or not j.is_public or j.status != "approved":
            raise HttpError(404, "分享内容已不可见")
        return {
            "success": True,
            "type": "journal",
            "data": j.as_dict(with_content=True),
        }
    raise HttpError(400, "不支持的分享类型")
