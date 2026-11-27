"""
行旅识景 TripScape / services/journal_service

手账服务：创建 / 更新 / 审核联动（敏感词、通知、足迹、搜索索引）。
"""

import logging
from datetime import date
from urllib.parse import urlparse

from apps.core import sensitive
from apps.journals.models import Journal
from django.utils import timezone
from services import notification_service as notify_service
from services.search_service import sync_journal_to_meili

logger = logging.getLogger("tripscape.journal")

MAX_IMAGES = 9
IMAGE_URL_MAX = 512
CONTENT_MAX = 20000


class ImageListError(ValueError):
    """图片列表不合法（API 层翻译成 422）。"""


def normalize_images(raw) -> list:
    """校验并归一化手账图片列表。

    安全口径：只接受字符串地址，只允许站内相对路径或 http(s) 绝对地址，
    数量与长度均设上限——否则任意 JSON（对象/超长列表/危险 scheme）
    会被原样写进 JSONField，前端渲染时崩或把用户导去外部站点。
    """
    if raw is None:
        return []
    if not isinstance(raw, list):
        raise ImageListError("图片列表必须是数组")
    if len(raw) > MAX_IMAGES:
        raise ImageListError(f"最多上传 {MAX_IMAGES} 张图片")

    out: list[str] = []
    for item in raw:
        if not isinstance(item, str):
            raise ImageListError("图片地址必须是字符串")
        url = item.strip()
        if not url:
            continue
        if len(url) > IMAGE_URL_MAX:
            raise ImageListError(f"图片地址最长 {IMAGE_URL_MAX} 字符")
        if url.startswith("/") and not url.startswith("//"):
            out.append(url)
            continue
        parsed = urlparse(url)
        if parsed.scheme in ("http", "https") and parsed.netloc:
            out.append(url)
            continue
        raise ImageListError("图片地址只支持站内路径或 http(s) 链接")
    return out


def normalize_content(raw) -> str:
    """正文归一化（去首尾空白 + 长度上限，防单条记录撑爆存储）。"""
    text = (raw or "").strip() if isinstance(raw, str) else ""
    return text[:CONTENT_MAX]


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
    canvas=None,
    is_draft: bool = False,
) -> tuple:
    """创建手账。

    敏感词命中 -> 直接拒绝。
    返回 (ok, journal_or_message)
    """
    title = (title or "").strip()
    content = normalize_content(content)
    try:
        images = normalize_images(images)
    except ImageListError as exc:
        return False, str(exc)
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
        canvas=canvas or {},
        visited_at=visited_at,
        # 草稿不公开，也不生成足迹/徽章/通知
        is_public=False if is_draft else is_public,
        status="draft" if is_draft else "approved",
    )
    if not is_draft:
        _post_create(journal)
    return True, journal


EDIT_FIELDS = ("title", "content", "images", "visited_at", "canvas")


def _json_safe_patch(patch: dict) -> dict:
    """把 patch 转为可存 JSONField 的形态（TS-05：date -> ISO 字符串）。"""
    out = dict(patch)
    if isinstance(out.get("visited_at"), date):
        out["visited_at"] = out["visited_at"].isoformat()
    return out


def _restore_patch_types(patch: dict) -> dict:
    """应用快照前把 ISO 日期字符串转回 date（配合 _json_safe_patch）。"""
    out = dict(patch)
    v = out.get("visited_at")
    if isinstance(v, str) and v:
        try:
            out["visited_at"] = date.fromisoformat(v[:10])
        except ValueError:
            out["visited_at"] = None
    return out


def update_journal(journal: Journal, data: dict) -> tuple:
    """更新手账（仅作者）。

    - 已通过（approved）：修改写入 pending_edit 快照，edit_pending=True；
      旧版继续公开展示，审核通过后替换，驳回则保留旧版。
    - 待审/已驳回：直接替换内容并回到 pending（旧版本就未公开）。

    字段语义（TS-06）：键存在即视为修改——visited_at=None 表示清空日期；
    键不存在表示未修改。API 层用 exclude_unset 区分。
    """
    patch = {k: data[k] for k in EDIT_FIELDS if k in data}
    if "is_public" in data and data["is_public"] is not None:
        patch["is_public"] = data["is_public"]

    # 字段归一化（防超长标题/正文落库报 DataError，防非法图片地址）
    if "title" in patch:
        patch["title"] = (patch["title"] or "").strip()[:128]
        if not patch["title"]:
            return False, "标题不能为空"
    if "content" in patch:
        patch["content"] = normalize_content(patch["content"])
    if "images" in patch:
        try:
            patch["images"] = normalize_images(patch["images"])
        except ImageListError as exc:
            return False, str(exc)

    # 敏感词检查（针对新内容）
    new_title = patch.get("title", journal.title)
    new_content = patch.get("content", journal.content)
    ok, hit = sensitive.check_text(f"{new_title} {new_content}")
    if not ok:
        return False, f"内容包含敏感词「{hit}」，请修改后发布"

    if journal.status == "draft":
        for field in EDIT_FIELDS:
            if field in patch:
                setattr(journal, field, patch[field])
        if "is_public" in patch and data.get("is_draft") is not True:
            journal.is_public = patch["is_public"]

        # 显式传 is_draft=False 才是"发布"；否则继续存草稿
        if data.get("is_draft") is False:
            journal.status = "approved"
            journal.is_public = (
                True if data.get("is_public") is None else bool(data.get("is_public"))
            )
            journal.save()
            _post_create(journal)
            return True, journal
        journal.save()
        return True, journal

    if journal.status == "approved":
        snapshot = dict(journal.pending_edit or {})
        snapshot.update(_json_safe_patch(patch))
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
    from services.footprint_service import (
        rebuild_user_footprints,
        refresh_footprint_for_journal,
    )

    if action == "approve":
        # 应用待审快照（二次编辑通过 -> 新版替换旧版）
        if journal.edit_pending and journal.pending_edit:
            snap = _restore_patch_types(dict(journal.pending_edit))
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
