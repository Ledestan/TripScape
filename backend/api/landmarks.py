"""
行旅识景 TripScape / api/landmarks

地标 API。

GET    /api/landmarks/spots      3D 地球光点数据（含 image_url/intro 摘要）
GET    /api/landmarks/           列表（分页、region 筛选、排序）
GET    /api/landmarks/{id}       详情（百科图片 + 介绍）
POST   /api/landmarks/           新增（管理员）
PUT    /api/landmarks/{id}       修改（管理员）
DELETE /api/landmarks/{id}       删除（管理员）
POST   /api/landmarks/{id}/favorite    收藏 / 取消收藏
GET    /api/landmarks/{id}/comments    地标下的公开评论
"""

from apps.core.auth import (
    OptionalAuth,
    any_admin_required,
    is_any_admin,
    login_required,
)
from apps.core.views import paginate
from apps.landmarks.models import Landmark, UserFavorite
from apps.landmarks.validators import (
    IMAGE_URL_MAX,
    INTRO_MAX,
    NAME_MAX,
    SHORT_TEXT_MAX,
    clean_coordinates,
    clean_target_id,
)
from django.conf import settings
from django.db import IntegrityError
from ninja import File, Router, Schema
from ninja.errors import HttpError
from ninja.files import UploadedFile
from services.audit_service import write_audit
from services.search_service import sync_landmark_to_meili

router = Router()


class LandmarkIn(Schema):
    target_id: str
    name: str
    name_en: str = ""
    region: str = ""
    country: str = ""
    lat: float
    lon: float
    intro: str = ""
    image_url: str = ""


def _clean_landmark_payload(payload) -> dict:
    """地标字段校验与截断（非法输入一律 400，不让脏数据/DB 异常冒 500）。"""
    name = (payload.name or "").strip()
    if not name:
        raise HttpError(400, "地标名称不能为空")
    try:
        lat, lon = clean_coordinates(payload.lat, payload.lon)
    except ValueError as exc:
        raise HttpError(400, str(exc))
    return {
        "name": name[:NAME_MAX],
        "name_en": (payload.name_en or "").strip()[:NAME_MAX],
        "region": (payload.region or "").strip()[:SHORT_TEXT_MAX],
        "country": (payload.country or "").strip()[:SHORT_TEXT_MAX],
        "lat": lat,
        "lon": lon,
        "intro": (payload.intro or "")[:INTRO_MAX],
        "image_url": (payload.image_url or "").strip()[:IMAGE_URL_MAX],
    }


@router.get(
    "/spots", summary="地球光点数据（含热度/评论数/足迹状态）", auth=OptionalAuth()
)
def spots(request):
    """光点数据：个人模式附 visited，公共模式附热度（手账数/评论数/访客数）。"""
    from apps.comments.models import Comment
    from apps.journals.models import Footprint, Journal
    from django.db.models import Count

    lms = list(Landmark.objects.filter(is_active=True).order_by("id"))

    journal_counts = dict(
        Journal.objects.filter(
            is_public=True, status="approved", deleted_at__isnull=True
        )
        .values_list("landmark")
        .annotate(c=Count("id"))
    )
    comment_counts = dict(
        Comment.objects.filter(is_hidden=False, deleted_at__isnull=True)
        .values_list("landmark")
        .annotate(c=Count("id"))
    )
    # 公开热度：隐藏足迹不计（TS-16：与 footprints/public 同口径）
    visitor_counts = dict(
        Footprint.objects.filter(hidden=False)
        .values_list("landmark")
        .annotate(c=Count("user", distinct=True))
    )

    user = getattr(request, "auth", None)
    visited_ids = set()
    if user and getattr(user, "is_authenticated", False):
        visited_ids = set(
            Footprint.objects.filter(user=user).values_list("landmark_id", flat=True)
        )

    data = []
    for lm in lms:
        d = lm.as_dict()
        d["journal_count"] = journal_counts.get(lm.id, 0)
        d["comment_count"] = comment_counts.get(lm.id, 0)
        d["visitor_count"] = visitor_counts.get(lm.id, 0)
        d["visited"] = lm.id in visited_ids
        data.append(d)
    return {"success": True, "data": data}


@router.get("/", summary="地标列表", auth=OptionalAuth())
def list_landmarks(
    request, page: int = 1, page_size: int = 0, region: str = "", q: str = ""
):
    """地标列表（管理端）：支持 名称/地区/上下架 筛选与分页。"""
    page_size = page_size or settings.PAGE_SIZE
    qs = Landmark.objects.filter(is_active=True)
    if region:
        qs = qs.filter(region=region)
    if q:
        qs = qs.filter(name__icontains=q)
    qs = qs.order_by("-view_count", "id")
    items, meta = paginate(qs, page, page_size)
    return {"success": True, "data": [lm.as_dict() for lm in items], "meta": meta}


@router.get("/{landmark_id}", summary="地标详情（浏览量+1）", auth=OptionalAuth())
def landmark_detail(request, landmark_id: int):
    """地标详情：百科介绍 + 计数（评论/手账/访客/点赞） + 我的收藏态。

    计数在这里一并返回，前端详情窗才不会出现"评论 0 / 手账 0"的假数据
    （之前前端拿不到 comment_count / journal_count，只能显示 0）。
    """
    from apps.comments.models import Comment
    from apps.journals.models import Footprint, Journal
    from django.db.models import F
    from services.like_service import like_stats

    lm = Landmark.objects.filter(id=landmark_id).first()
    if not lm:
        raise HttpError(404, "地标不存在")
    # 已下架地标只对管理员可见（下架 = 地球/搜索/详情都不再对外展示）
    viewer = getattr(request, "auth", None)
    if not lm.is_active and not is_any_admin(viewer):
        raise HttpError(404, "地标不存在")
    Landmark.objects.filter(id=lm.id).update(view_count=F("view_count") + 1)

    data = lm.as_dict(with_intro=True)
    data["comment_count"] = Comment.objects.filter(
        landmark=lm, is_hidden=False, deleted_at__isnull=True
    ).count()
    data["journal_count"] = Journal.objects.filter(
        landmark=lm, is_public=True, status="approved", deleted_at__isnull=True
    ).count()
    data["visitor_count"] = (
        Footprint.objects.filter(landmark=lm, hidden=False)
        .values("user_id")
        .distinct()
        .count()
    )
    counts, liked = like_stats("article", [lm.id], viewer=viewer)
    data["like_count"] = counts.get(lm.id, 0)
    data["liked"] = lm.id in liked
    data["favorited"] = bool(
        getattr(viewer, "is_authenticated", False)
        and UserFavorite.objects.filter(user=viewer, landmark=lm).exists()
    )
    return {"success": True, "data": data}


@router.post("/", summary="新增地标（管理员）")
@any_admin_required
def create_landmark(request, payload: LandmarkIn):
    """新增地标（target_id 缺省由名称生成，重复即 400）。"""
    try:
        target_id = clean_target_id(payload.target_id)
    except ValueError as exc:
        raise HttpError(400, str(exc))
    fields = _clean_landmark_payload(payload)
    if Landmark.objects.filter(target_id=target_id).exists():
        raise HttpError(400, "target_id 已存在")
    try:
        lm = Landmark.objects.create(target_id=target_id, **fields)
    except IntegrityError:
        raise HttpError(400, "target_id 已存在")
    sync_landmark_to_meili(lm)
    write_audit(request, "landmark.create", f"landmark:{lm.id}", lm.name)
    return {"success": True, "data": lm.as_dict()}


@router.put("/{landmark_id}", summary="修改地标（管理员）")
@any_admin_required
def update_landmark(request, landmark_id: int, payload: LandmarkIn):
    """修改地标字段（管理员；target_id 唯一性冲突返回 400）。"""
    lm = Landmark.objects.filter(id=landmark_id).first()
    if not lm:
        raise HttpError(404, "地标不存在")
    try:
        target_id = clean_target_id(payload.target_id)
    except ValueError as exc:
        raise HttpError(400, str(exc))
    fields = _clean_landmark_payload(payload)
    if Landmark.objects.filter(target_id=target_id).exclude(id=lm.id).exists():
        raise HttpError(400, "target_id 已存在")
    for field, value in fields.items():
        setattr(lm, field, value)
    lm.target_id = target_id
    try:
        lm.save()
    except IntegrityError:
        raise HttpError(400, "target_id 已存在")
    sync_landmark_to_meili(lm)
    write_audit(request, "landmark.update", f"landmark:{lm.id}", lm.name)
    return {"success": True, "data": lm.as_dict()}


@router.delete("/{landmark_id}", summary="删除地标（管理员）")
@any_admin_required
def delete_landmark(request, landmark_id: int):
    """删除地标（管理员；被评论/手账引用时拒绝，返回 400 而不是 500）。"""
    from django.db.models import ProtectedError

    lm = Landmark.objects.filter(id=landmark_id).first()
    if not lm:
        raise HttpError(404, "地标不存在")
    name = lm.name
    try:
        lm.delete()
    except ProtectedError:
        raise HttpError(400, "该地标已被手账引用，不能删除（请先处理关联手账）")
    try:
        from services.search_service import remove_from_meili

        remove_from_meili("landmark", landmark_id)
    except Exception:
        pass
    write_audit(request, "landmark.delete", f"landmark:{landmark_id}", name)
    return {"success": True}


@router.post("/{landmark_id}/favorite", summary="收藏 / 取消收藏（可显式指定目标状态）")
@login_required
def toggle_favorite(request, landmark_id: int, favorited: bool = None):
    """收藏/取消收藏地标。

    favorited 显式给出时为幂等置位（双击/重试不会把收藏状态来回翻转）；
    不传时保持旧的切换语义。
    """
    from django.db import IntegrityError, transaction

    lm = Landmark.objects.filter(id=landmark_id).first()
    if not lm:
        raise HttpError(404, "地标不存在")

    wanted = favorited
    if wanted is None:
        wanted = not UserFavorite.objects.filter(
            user=request.auth, landmark=lm
        ).exists()

    if wanted:
        try:
            with transaction.atomic():
                UserFavorite.objects.get_or_create(user=request.auth, landmark=lm)
        except IntegrityError:
            pass
    else:
        UserFavorite.objects.filter(user=request.auth, landmark=lm).delete()
    return {"success": True, "favorited": bool(wanted)}


@router.post("/{landmark_id}/image", summary="上传地标百科图片（管理员）")
@any_admin_required
def upload_landmark_image(request, landmark_id: int, image: UploadedFile = File(...)):
    """上传地标百科图片。"""
    from services import file_service

    lm = Landmark.objects.filter(id=landmark_id).first()
    if not lm:
        raise HttpError(404, "地标不存在")
    url = file_service.save_upload(image, namespace="landmarks", owner=request.auth)
    lm.image_url = url
    lm.save(update_fields=["image_url"])
    write_audit(request, "landmark.upload_image", f"landmark:{lm.id}", url)
    return {"success": True, "image_url": url}
