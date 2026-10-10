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
        parent = (
            Comment.objects.filter(
                id=parent_id,
                deleted_at__isnull=True,  # 已删父评论不可回复
            )
            .select_related("parent")
            .first()
        )
        if not parent:
            return False, "回复的评论不存在"
        # 跨地标校验（TS-14）：回复必须归属父评论所在地标，
        # 防止地标 A 的评论树里出现地标 B 的内容
        if parent.landmark_id != lm.id:
            return False, "回复与原评论不属于同一地标"
        # 深度限制（TS-15）：最多两级——三级及以上回复自动挂到
        # 顶级父评论下（扁平化），保证"发布成功的评论都能被读到"
        if parent.parent_id:
            parent = parent.parent

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
