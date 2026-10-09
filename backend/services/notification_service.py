"""行旅识景 TripScape
创建日期：2025-09-01

通知服务。
"""

import logging

from apps.notifications.models import Notification

logger = logging.getLogger("tripscape.notify")


def push(user, type_: str, title: str, content: str = "", link: str = ""):
    """写一条站内通知。"""
    try:
        return Notification.objects.create(
            user=user,
            type=type_,
            title=title[:128],
            content=(content or "")[:512],
            link=(link or "")[:255],
        )
    except Exception as exc:
        logger.warning("通知写入失败：%s", exc)
        return None


def notify_reply(replier, parent_comment, new_comment):
    """A 回复了 B 的评论 -> 通知 B。"""
    if parent_comment.user_id == (new_comment.user_id or -1):
        return
    return push(
        user=parent_comment.user,
        type_="reply",
        title=f"{replier.nickname or replier.username} 回复了你的评论",
        content=new_comment.content[:200],
        link=f"/landmarks/{parent_comment.landmark_id}?tab=comments",
    )


def notify_journal_moderated(journal, approved: bool, reason: str = ""):
    """手账审核结果 -> 通知作者。"""
    if approved:
        return push(
            user=journal.user,
            type_="moderation",
            title=f"你的手账《{journal.title}》已通过审核",
            link=f"/journals/{journal.id}",
        )
    return push(
        user=journal.user,
        type_="moderation",
        title=f"你的手账《{journal.title}》未通过审核",
        content=f"理由：{reason or '内容不合适'}",
        link=f"/journal_edit/{journal.id}",
    )


def notify_badge(user, badge):
    """获得徽章 -> 通知。"""
    return push(
        user=user,
        type_="badge",
        title=f"恭喜获得徽章「{badge.name}」",
        content=badge.description or "",
        link="/profile",
    )
