"""行旅识景 TripScape
创建日期：2025-09-01

评论服务：发评论（敏感词拦截）、回复通知、搜索索引。
"""

import logging

from apps.comments.models import Comment
from apps.core import sensitive
from services import notification_service as notify_service
from services.search_service import sync_comment_to_meili

logger = logging.getLogger("tripscape.comment")


def create_comment(user, landmark_id: int, content: str, parent_id=None) -> tuple:
    """发表评论。

    返回：
        (ok, comment 或错误信息)
    """
    from apps.landmarks.models import Landmark

    content = (content or "").strip()
    if not content:
        return False, "评论内容不能为空"
    if getattr(user, "is_muted", False):
        until = user.muted_until.strftime("%Y-%m-%d %H:%M")
        return False, f"你已被禁言至 {until}，暂时无法发表评论"
    lm = Landmark.objects.filter(id=landmark_id).first()
    if not lm:
        return False, "地标不存在"

    ok, hit = sensitive.check_text(content)
    if not ok:
        return False, f"评论包含敏感词「{hit}」，请修改后发布"

    parent = None
    if parent_id:
        parent = Comment.objects.filter(id=parent_id).first()
        if not parent:
            return False, "回复的评论不存在"

    comment = Comment.objects.create(
        user=user, landmark=lm, parent=parent, content=content[:2000]
    )

    # 回复通知
    if parent and parent.user_id != user.id:
        try:
            notify_service.notify_reply(user, parent, comment)
        except Exception as exc:
            logger.warning("回复通知失败：%s", exc)

    sync_comment_to_meili(comment)
    return True, comment
