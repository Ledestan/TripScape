"""
行旅识景 TripScape / services/like_service
创建日期: 2026-12-01

点赞统计与幂等切换，提供:
    1. like_stats：批量取点赞数 + 当前用户是否点过（列表接口一次查完，避免 N+1）
    2. set_like：显式目标状态（idempotent）或切换，供 /api/likes 使用

依赖:
    需求文件: requirements.txt
    依赖库: Django

用法:
    from services.like_service import like_stats, set_like
    counts, liked = like_stats("journal", [1, 2], viewer=user)

注意:
    1. Like 表对 (user, target_type, target_id) 有唯一约束：旧实现用
       "先查再建"在双击/并发下会撞唯一键报 500，这里统一用原子写法兜住。
    2. 前端需要"点了就是点、取消就是取消"的确定性语义：并发请求只带目标
       状态，不会像 toggle 那样互相抵消。
"""

import logging

from apps.comments.models_like import Like
from django.db import IntegrityError, transaction
from django.db.models import Count

logger = logging.getLogger("tripscape.like")


def normalize_ids(ids) -> list[int]:
    """把 ids 收敛成去重后的正整数数组。"""
    out = []
    for value in ids or []:
        try:
            number = int(value)
        except (TypeError, ValueError):
            continue
        if number > 0 and number not in out:
            out.append(number)
    return out


def like_stats(target_type: str, ids, viewer=None) -> tuple[dict, set]:
    """批量返回 (计数映射, 当前用户已点赞 id 集合)。"""
    id_list = normalize_ids(ids)
    if not id_list:
        return {}, set()

    counts = {
        row["target_id"]: row["total"]
        for row in Like.objects.filter(target_type=target_type, target_id__in=id_list)
        .values("target_id")
        .annotate(total=Count("id"))
    }
    liked = set()
    if viewer is not None and getattr(viewer, "is_authenticated", False):
        liked = set(
            Like.objects.filter(
                user=viewer, target_type=target_type, target_id__in=id_list
            ).values_list("target_id", flat=True)
        )
    return counts, liked


def set_like(user, target_type: str, target_id: int, liked=None) -> tuple[bool, int]:
    """设置/切换点赞状态。

    参数：
        liked : True=点赞 / False=取消 / None=切换（兼容旧前端）

    返回：
        (最终是否已点赞, 该目标当前点赞总数)
    """
    wanted = liked
    if wanted is None:
        exists = Like.objects.filter(
            user=user, target_type=target_type, target_id=target_id
        ).exists()
        wanted = not exists

    if wanted:
        try:
            with transaction.atomic():
                Like.objects.get_or_create(
                    user=user, target_type=target_type, target_id=target_id
                )
        except IntegrityError:
            # 并发下已被同一用户创建：结果一致，忽略
            pass
    else:
        Like.objects.filter(
            user=user, target_type=target_type, target_id=target_id
        ).delete()

    total = Like.objects.filter(target_type=target_type, target_id=target_id).count()
    return bool(wanted), total
