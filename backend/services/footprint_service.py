"""行旅识景 TripScape
创建日期：2025-09-01

手账与足迹服务。

统计口径（TS-16，全项目统一）：
    有效手账 = status="approved" 且 deleted_at 为空；
    visits   = 有效手账条数（同一地标多篇手账按篇计）；
    visitors = 去重用户数；隐藏足迹只影响展示，不计入公开热度。
"""

import logging

from apps.journals.models import Footprint, Journal
from apps.landmarks.models import Landmark
from django.db.models import Count, F, Sum

logger = logging.getLogger("tripscape.journal")


def _valid_journals_qs(user=None):
    """有效手账查询集（已通过 + 未软删）。"""
    qs = Journal.objects.filter(status="approved", deleted_at__isnull=True)
    if user is not None:
        qs = qs.filter(user=user)
    return qs


def rebuild_user_footprints(user) -> int:
    """根据用户全部有效手账重建足迹表（排除软删，TS-16）。

    返回：
        足迹条数
    """
    agg = (
        _valid_journals_qs(user)
        .values("landmark_id")
        .annotate(total=Count("id"))
    )
    # 保留用户手动 hidden 状态重建
    old_hidden = set(
        Footprint.objects.filter(user=user, hidden=True).values_list(
            "landmark_id", flat=True
        )
    )
    Footprint.objects.filter(user=user).delete()
    objs = [
        Footprint(
            user=user,
            landmark_id=row["landmark_id"],
            visits=row["total"],
            hidden=row["landmark_id"] in old_hidden,
        )
        for row in agg
    ]
    Footprint.objects.bulk_create(objs, ignore_conflicts=True)
    return len(objs)


def refresh_footprint_for_journal(journal: Journal):
    """单个手账保存/审核通过后增量更新足迹。"""
    if journal.status != "approved" or journal.deleted_at:
        return
    fp, created = Footprint.objects.get_or_create(
        user=journal.user, landmark=journal.landmark
    )
    if not created:
        fp.visits = F("visits") + 1
        fp.save(update_fields=["visits", "last_visited_at"])


def get_user_footprints(user) -> list:
    """个人主页足迹列表（本人视角：含隐藏项，标记 hidden 供前端展示）。"""
    fps = (
        Footprint.objects.filter(user=user)
        .select_related("landmark")
        .order_by("-last_visited_at")
    )
    return [
        {
            "landmark_id": fp.landmark_id,
            "name": fp.landmark.name,
            "target_id": fp.landmark.target_id,
            "lat": float(fp.landmark.lat),
            "lon": float(fp.landmark.lon),
            "visits": fp.visits,
            "hidden": fp.hidden,
            "first_visited_at": fp.first_visited_at.isoformat(),
            "last_visited_at": fp.last_visited_at.isoformat(),
        }
        for fp in fps
    ]


def get_public_heat() -> list:
    """全球足迹热度（地球光点热度渲染用；隐藏足迹不计入）。

    visits 汇总用 Sum(visits)（同一用户多篇计多次），
    visitors 用 Count(distinct user)——TS-16 修复 Count(id) 口径错误。
    """
    heat = (
        Footprint.objects.filter(hidden=False)
        .values("landmark_id")
        .annotate(users=Count("user", distinct=True), visits_total=Sum("visits"))
    )
    landmark_map = {lm.id: lm for lm in Landmark.objects.all()}
    out = []
    for row in heat:
        lm = landmark_map.get(row["landmark_id"])
        if not lm:
            continue
        out.append(
            {
                "landmark_id": lm.id,
                "name": lm.name,
                "lat": float(lm.lat),
                "lon": float(lm.lon),
                "visitors": row["users"],
                "visits": row["visits_total"] or 0,
            }
        )
    out.sort(key=lambda x: x["visitors"], reverse=True)
    return out
