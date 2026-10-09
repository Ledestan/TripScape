"""行旅识景 TripScape
创建日期：2025-09-01

分享服务。
"""

import secrets

from apps.shares.models import ShareLink


def create_share_token(target_type: str, target_id: int, user=None) -> str:
    """为对象创建公开分享 token（已有则复用）。"""
    existing = ShareLink.objects.filter(
        target_type=target_type, target_id=target_id
    ).first()
    if existing:
        return existing.token
    token = secrets.token_urlsafe(16)[:20]
    ShareLink.objects.create(
        token=token, target_type=target_type, target_id=target_id, created_by=user
    )
    return token


def resolve(token: str):
    """token -> (target_type, target_id) 或 None。"""
    link = ShareLink.objects.filter(token=token).first()
    if not link:
        return None
    return link.target_type, link.target_id
