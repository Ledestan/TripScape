"""行旅识景 TripScape
创建日期：2025-09-01

运营看板数据服务。
"""

import logging
from datetime import timedelta

from apps.comments.models import Comment
from apps.journals.models import Journal
from apps.landmarks.models import Landmark, RecognitionRecord
from django.contrib.auth import get_user_model
from django.db.models import Count
from django.utils import timezone

logger = logging.getLogger("tripscape.dashboard")


def build_stats(days: int = 30) -> dict:
    """聚合看板数据。

    返回：
        totals      用户数 / 地标数 / 评论数 / 手账数 / 识别次数
        trends      近 N 天每日的识别 / 评论 / 手账 / 新用户曲线
        hot_landmarks  地标热度 Top10（view_count + 手账数）
    """
    User = get_user_model()
    now = timezone.now()
    since = now - timedelta(days=days)

    totals = {
        "users": User.objects.filter(is_active=True).count(),
        "landmarks": Landmark.objects.filter(is_active=True).count(),
        "comments": Comment.objects.filter(is_hidden=False).count(),
        "journals": Journal.objects.filter(status="approved").count(),
        "recognitions": RecognitionRecord.objects.count(),
    }

    # 近 N 天趋势（按天聚合）
    def daily(qs, date_field="created_at"):
        """按日聚合统计（看板趋势用）。"""
        out = {}
        for row in qs.filter(**{f"{date_field}__gte": since}).values_list(
            date_field, flat=True
        ):
            day = row.date().isoformat()
            out[day] = out.get(day, 0) + 1
        return out

    trend_recog = daily(RecognitionRecord.objects.all())
    trend_comment = daily(Comment.objects.all())
    trend_journal = daily(Journal.objects.all())
    trend_user = daily(User.objects.filter(is_active=True))

    days_list = []
    for i in range(days):
        day = (now - timedelta(days=days - 1 - i)).date().isoformat()
        days_list.append(
            {
                "date": day,
                "recognitions": trend_recog.get(day, 0),
                "comments": trend_comment.get(day, 0),
                "journals": trend_journal.get(day, 0),
                "new_users": trend_user.get(day, 0),
            }
        )

    hot = (
        Journal.objects.filter(is_public=True, status="approved")
        .values("landmark_id", "landmark__name")
        .annotate(journal_count=Count("id"))
        .order_by("-journal_count")[:10]
    )
    view_map = {lm.id: lm for lm in Landmark.objects.all()}
    hot_landmarks = []
    for row in hot:
        lm = view_map.get(row["landmark_id"])
        if not lm:
            continue
        hot_landmarks.append(
            {
                "id": lm.id,
                "name": lm.name,
                "journals": row["journal_count"],
                "view_count": lm.view_count,
            }
        )

    return {"totals": totals, "trends": days_list, "hot_landmarks": hot_landmarks}


def refresh_cache():
    """定时任务入口：预聚合（当前直接实时查询，量大后可换缓存表）。"""
    return build_stats(days=30)
