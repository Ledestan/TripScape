"""行旅识景 TripScape
创建日期：2025-09-01

手账服务：创建 / 更新 / 审核联动（敏感词、通知、足迹、搜索索引）。
"""

import logging

from apps.core import sensitive
from apps.journals.models import Journal
from django.utils import timezone
from services import notification_service as notify_service
from services.search_service import sync_journal_to_meili

logger = logging.getLogger("tripscape.journal")


def _check_sensitive(text: str):
    return sensitive.check_text(text)


def create_journal(
    user,
    landmark_id: int,
    title: str,
    content: str,
    images=None,
    visited_at=None,
    is_public: bool = True,
) -> tuple:
    """创建手账。

    敏感词命中 -> 直接拒绝。
    返回 (ok, journal_or_message)
    """
    title = (title or "").strip()
    content = (content or "").strip()
    if not title:
        return False, "标题不能为空"
    if getattr(user, "is_muted", False):
        until = user.muted_until.strftime("%Y-%m-%d %H:%M")
        return False, f"你已被禁言至 {until}，暂时无法发布手账"
    from apps.landmarks.models import Landmark

    lm = Landmark.objects.filter(id=landmark_id).first()
    if not lm:
        return False, "地标不存在"

    ok, hit = _check_sensitive(f"{title} {content}")
    if not ok:
        return False, f"内容包含敏感词「{hit}」，请修改后发布"

    journal = Journal.objects.create(
        user=user,
        landmark=lm,
        title=title[:128],
        content=content,
        images=images or [],
        visited_at=visited_at,
        is_public=is_public,
        status="approved",  # 无敏感词直接通过；命中敏感词已在上方拒绝
    )
    _post_create(journal)
    return True, journal


EDIT_FIELDS = ("title", "content", "images", "visited_at")


def update_journal(journal: Journal, data: dict) -> tuple:
    """更新手账（仅作者）。

    - 已通过（approved）：修改写入 pending_edit 快照，edit_pending=True；
      旧版继续公开展示，审核通过后替换，驳回则保留旧版。
    - 待审/已驳回：直接替换内容并回到 pending（旧版本就未公开）。
    """
    patch = {k: data[k] for k in EDIT_FIELDS if k in data and data[k] is not None}
    if "is_public" in data and data["is_public"] is not None:
        patch["is_public"] = data["is_public"]

    # 敏感词检查（针对新内容）
    new_title = patch.get("title", journal.title)
    new_content = patch.get("content", journal.content)
    ok, hit = sensitive.check_text(f"{new_title} {new_content}")
    if not ok:
        return False, f"内容包含敏感词「{hit}」，请修改后发布"

    if journal.status == "approved":
        snapshot = dict(journal.pending_edit or {})
        snapshot.update(patch)
        journal.pending_edit = snapshot
        journal.edit_pending = True
        # is_public 允许作者直接切换（不影响正文审核）
        if "is_public" in patch:
            journal.is_public = patch.pop("is_public")
        journal.save(update_fields=["pending_edit", "edit_pending", "is_public"])
        return True, journal

    # pending / rejected：直接替换，进入待审核
    for field in EDIT_FIELDS:
        if field in patch:
            setattr(journal, field, patch[field])
    if "is_public" in patch:
        journal.is_public = patch["is_public"]
    journal.edit_pending = False
    journal.pending_edit = None
    journal.status = "pending"
    journal.reject_reason = ""
    journal.save()
    sync_journal_to_meili(journal)
    return True, journal


def moderate(journal: Journal, action: str, moderator, reason: str = ""):
    """审核动作：approve / reject / hide / restore / delete。"""
    from services.footprint_service import (rebuild_user_footprints,
                                            refresh_footprint_for_journal)

    if action == "approve":
        # 应用待审快照（二次编辑通过 -> 新版替换旧版）
        if journal.edit_pending and journal.pending_edit:
            snap = dict(journal.pending_edit)
            snap.pop("is_public", None)
            for field in EDIT_FIELDS:
                if field in snap:
                    setattr(journal, field, snap[field])
            journal.pending_edit = None
            journal.edit_pending = False
            journal.save(
                update_fields=[
                    "title",
                    "content",
                    "images",
                    "visited_at",
                    "pending_edit",
                    "edit_pending",
                    "status",
                    "reject_reason",
                ]
            )
            sync_journal_to_meili(journal)
        else:
            journal.status = "approved"
            journal.reject_reason = ""
            journal.save(update_fields=["status", "reject_reason"])
        rebuild_user_footprints(journal.user)
        notify_service.notify_journal_moderated(journal, approved=True)
    elif action == "reject":
        if journal.edit_pending:
            # 二次编辑被驳回：丢弃新版，旧版继续展示
            journal.pending_edit = None
            journal.edit_pending = False
            journal.save(update_fields=["pending_edit", "edit_pending"])
            notify_service.notify_journal_moderated(
                journal, approved=False, reason=reason or "修改未通过审核，已保留原版本"
            )
        else:
            journal.status = "rejected"
            journal.reject_reason = reason[:255]
            journal.save(update_fields=["status", "reject_reason"])
            rebuild_user_footprints(journal.user)
            notify_service.notify_journal_moderated(
                journal, approved=False, reason=reason
            )
    elif action == "hide":
        journal.is_public = False
        journal.save(update_fields=["is_public"])
    elif action == "restore":
        journal.is_public = True
        journal.save(update_fields=["is_public"])
    elif action == "delete":
        user = journal.user
        journal.delete()
        rebuild_user_footprints(user)
    else:
        raise ValueError(f"未知审核动作：{action}")


def _post_create(journal: Journal):
    from services.footprint_service import refresh_footprint_for_journal

    refresh_footprint_for_journal(journal)
    sync_journal_to_meili(journal)
