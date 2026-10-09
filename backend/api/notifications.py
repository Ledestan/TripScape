"""行旅识景 TripScape
创建日期：2025-09-01

通知 API。

GET   /api/notifications/         我的通知列表
GET   /api/notifications/unread   未读数
POST  /api/notifications/{id}/read    标记已读
POST  /api/notifications/read-all     全部已读
"""


from apps.core.auth import login_required
from apps.core.views import paginate
from apps.notifications.models import Notification
from django.conf import settings
from ninja import Router
from ninja.errors import HttpError

router = Router()


@router.get("/", summary="我的通知")
@login_required
def list_notifications(request, page: int = 1, page_size: int = 0):
    """我的通知列表（分页，按类型筛选）。"""
    page_size = page_size or settings.PAGE_SIZE
    qs = Notification.objects.filter(user=request.auth)
    items, meta = paginate(qs, page, page_size)
    return {"success": True, "data": [n.as_dict() for n in items], "meta": meta}


@router.get("/unread", summary="未读通知数")
@login_required
def unread_count(request):
    """未读通知数（前端角标轮询）。"""
    return {
        "success": True,
        "count": Notification.objects.filter(user=request.auth, is_read=False).count(),
    }


@router.post("/{notification_id}/read", summary="标记已读")
@login_required
def mark_read(request, notification_id: int):
    """标记单条通知已读。"""
    n = Notification.objects.filter(id=notification_id, user=request.auth).first()
    if not n:
        raise HttpError(404, "通知不存在")
    n.is_read = True
    n.save(update_fields=["is_read"])
    return {"success": True}


@router.post("/read-all", summary="全部已读")
@login_required
def mark_all_read(request):
    """全部标记已读。"""
    Notification.objects.filter(user=request.auth, is_read=False).update(is_read=True)
    return {"success": True}
