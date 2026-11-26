"""
行旅识景 TripScape / services/comment_service
创建日期: 2025-09-01

评论服务：发评论（敏感词拦截）、回复通知、搜索索引。
"""

import logging
from apps.comments.models import Comment
from apps.core import sensitive
from services import notification_service as notify_service
from services.search_service import sync_comment_to_meili

logger = logging.getLogger("tripscape.comment")


def create_comment(
    user, landmark_id: int = None, content: str = "", parent_id=None, journal_id: int = None
) -> tuple:
    """发表评论。

    返回：
        (ok, comment 或错误信息)
    """
    from apps.journals.models import Journal
    from apps.landmarks.models import Landmark

    content = (content or "").strip()
    if not content:
        return False, "评论内容不能为空"
    if getattr(user, "is_muted", False):
        until = user.muted_until.strftime("%Y-%m-%d %H:%M")
        return False, f"你已被禁言至 {until}，暂时无法发表评论"

    if bool(landmark_id) == bool(journal_id):
        return False, "评论必须且只能挂在地标或手账上"

    lm = None
    journal = None
    if journal_id:
        journal = Journal.objects.filter(id=journal_id, deleted_at__isnull=True).first()
        if not journal:
            return False, "手账不存在"
        if not journal.is_public and journal.user_id != user.id:
            return False, "该手账未公开"
    else:
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
        # 同目标校验：回复必须落在同一个地标 / 同一篇手账下，
        # 防止 A 的评论树里出现 B 的内容
        if lm is not None and parent.landmark_id != lm.id:
            return False, "回复与原评论不属于同一地标"
        if journal is not None and parent.journal_id != journal.id:
            return False, "回复与原评论不属于同一手账"

    # 两级平铺：回复"回复"时，挂回顶层评论，同时记住被回复的人
    reply_to = None
    if parent is not None and parent.parent_id:
        reply_to = parent
        parent = parent.parent

    comment = Comment.objects.create(
        user=user,
        landmark=lm,
        journal=journal,
        parent=parent,
        reply_to=reply_to,
        content=content[:2000],
    )

    # 回复通知：优先通知被 @ 的那位，其次才是顶层作者
    target = reply_to or parent
    if target and target.user_id != user.id:
        try:
            notify_service.notify_reply(user, target, comment)
        except Exception as exc:
            logger.warning("回复通知失败：%s", exc)

    if comment.landmark_id:
        sync_comment_to_meili(comment)
    return True, comment
