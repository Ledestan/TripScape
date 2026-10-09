"""行旅识景 TripScape
创建日期：2025-09-01

徽章服务：行为触发 -> 检查阈值 -> 发放 + 通知。
"""

import logging

from apps.badges.models import Badge, UserBadge
from apps.comments.models import Comment
from apps.journals.models import Footprint, Journal
from services import notification_service as notify_service

logger = logging.getLogger("tripscape.badge")


def _check_and_award(user, category: str, current: int):
    """检查某类别阈值徽章并发放。"""
    badges = Badge.objects.filter(
        category=category, is_active=True, threshold__lte=current
    )
    awarded = []
    for badge in badges:
        _, created = UserBadge.objects.get_or_create(user=user, badge=badge)
        if created:
            awarded.append(badge)
            try:
                notify_service.notify_badge(user, badge)
            except Exception:
                pass
    return awarded


def on_journal_created(user):
    """手账创建后：检查足迹类 + 手账类徽章。"""
    journal_count = Journal.objects.filter(user=user, status="approved").count()
    footprint_count = Footprint.objects.filter(user=user).count()
    awarded = _check_and_award(user, "journal", journal_count)
    awarded += _check_and_award(user, "footprint", footprint_count)
    return awarded


def on_comment_created(user):
    """评论发布后的徽章进度检查与发放。"""
    comment_count = Comment.objects.filter(user=user).count()
    return _check_and_award(user, "comment", comment_count)


def user_badges(user):
    """用户的徽章墙（含未获得的进度）。"""
    held = {
        ub.badge_id: ub
        for ub in UserBadge.objects.filter(user=user).select_related("badge")
    }
    stats = {
        "footprint": Footprint.objects.filter(user=user).count(),
        "comment": Comment.objects.filter(user=user).count(),
        "journal": Journal.objects.filter(user=user, status="approved").count(),
    }
    out = []
    for badge in Badge.objects.filter(is_active=True):
        ub = held.get(badge.id)
        stat = stats.get(badge.category, 0)
        out.append(
            {
                "code": badge.code,
                "name": badge.name,
                "description": badge.description,
                "category": badge.category,
                "icon": badge.icon,
                "threshold": badge.threshold,
                "owned": ub is not None,
                "awarded_at": ub.awarded_at.isoformat() if ub else None,
                "progress": (
                    min(1.0, stat / badge.threshold) if badge.threshold else 1.0
                ),
                "current": stat,
            }
        )
    return out
