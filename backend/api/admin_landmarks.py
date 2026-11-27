"""
行旅识景 TripScape / api/admin_landmarks

地标管理区块（并入 admin.py 主路由）。

从 admin_landmarks.py 合并而来；路由路径与原先 /api/admin/landmarks/* 完全一致。

安全口径：
- 分页统一走 core.views.paginate（页码/页宽夹取，负页码不再 500、页宽有上限）
- target_id / 经纬度做合法性校验（target_id 参与磁盘文件名，必须防穿越）
"""

from api.admin import admin_required, router, write_audit
from apps.core.views import paginate
from apps.landmarks.models import Landmark
from apps.landmarks.validators import (
    IMAGE_URL_MAX,
    INTRO_MAX,
    NAME_MAX,
    SHORT_TEXT_MAX,
    clean_coordinates,
    clean_target_id,
)
from django.db import IntegrityError
from ninja import Schema
from ninja.errors import HttpError


class LandmarkIn(Schema):
    target_id: str = ""
    name: str
    name_en: str = ""
    region: str = ""
    country: str = ""
    lat: float
    lon: float
    intro: str = ""
    image_url: str = ""


class LandmarkUpdateIn(Schema):
    name: str = ""
    name_en: str = ""
    region: str = ""
    country: str = ""
    lat: float = None
    lon: float = None
    intro: str = ""
    image_url: str = ""


def _lm_dict(lm: Landmark, with_intro=False):
    """地标序列化（补充 is_active 字段）。"""
    d = lm.as_dict(with_intro=with_intro)
    d["is_active"] = lm.is_active
    return d


@router.get("/landmarks", summary="地标列表")
@admin_required
def list_landmarks(
    request,
    q: str = "",
    region: str = "",
    is_active: str = "",
    page: int = 1,
    page_size: int = 0,
):
    """地标列表（管理端）：支持 名称/地区/上下架 筛选与分页。"""
    qs = Landmark.objects.all().order_by("id")
    if q:
        from django.db.models import Q

        qs = qs.filter(
            Q(name__icontains=q) | Q(name_en__icontains=q) | Q(country__icontains=q)
        )
    if region:
        qs = qs.filter(region=region)
    if is_active == "true":
        qs = qs.filter(is_active=True)
    elif is_active == "false":
        qs = qs.filter(is_active=False)

    items, meta = paginate(qs, page, page_size or 50)
    return {
        "success": True,
        "data": [_lm_dict(lm, with_intro=True) for lm in items],
        "meta": meta,
    }


@router.post("/landmarks", summary="新增地标")
@admin_required
def create_landmark(request, payload: LandmarkIn):
    """新增地标（target_id 缺省由名称生成，重复即 400）。"""
    name = (payload.name or "").strip()
    if not name:
        raise HttpError(400, "名称不能为空")
    try:
        lat, lon = clean_coordinates(payload.lat, payload.lon)
    except ValueError as exc:
        raise HttpError(400, str(exc))
    fallback = name.lower().replace(" ", "_")
    try:
        tid = clean_target_id(payload.target_id, fallback=fallback)
    except ValueError as exc:
        raise HttpError(400, str(exc))
    if Landmark.objects.filter(target_id=tid).exists():
        raise HttpError(400, f"target_id「{tid}」已存在")
    try:
        lm = Landmark.objects.create(
            target_id=tid,
            name=name[:NAME_MAX],
            name_en=(payload.name_en or "").strip()[:NAME_MAX],
            region=(payload.region or "").strip()[:SHORT_TEXT_MAX],
            country=(payload.country or "").strip()[:SHORT_TEXT_MAX],
            lat=lat,
            lon=lon,
            intro=(payload.intro or "")[:INTRO_MAX],
            image_url=(payload.image_url or "").strip()[:IMAGE_URL_MAX],
        )
    except IntegrityError:
        raise HttpError(400, f"target_id「{tid}」已存在")
    write_audit(request, "landmark.create", f"landmark:{lm.id}", lm.name)
    return {"success": True, "data": _lm_dict(lm, with_intro=True)}


@router.put("/landmarks/{landmark_id}", summary="修改地标")
@admin_required
def update_landmark(request, landmark_id: int, payload: LandmarkUpdateIn):
    """修改地标字段（仅更新传入的非空字段；经纬度做区间校验）。"""
    lm = Landmark.objects.filter(id=landmark_id).first()
    if not lm:
        raise HttpError(404, "地标不存在")
    changed = []
    for field, value in (
        ("name", payload.name),
        ("name_en", payload.name_en),
        ("region", payload.region),
        ("country", payload.country),
        ("intro", payload.intro),
        ("image_url", payload.image_url),
    ):
        if value:
            limit = {
                "name": NAME_MAX,
                "name_en": NAME_MAX,
                "region": SHORT_TEXT_MAX,
                "country": SHORT_TEXT_MAX,
                "intro": INTRO_MAX,
                "image_url": IMAGE_URL_MAX,
            }[field]
            setattr(lm, field, value.strip()[:limit])
            changed.append(field)
    if payload.lat is not None or payload.lon is not None:
        try:
            lat, lon = clean_coordinates(
                payload.lat if payload.lat is not None else lm.lat,
                payload.lon if payload.lon is not None else lm.lon,
            )
        except ValueError as exc:
            raise HttpError(400, str(exc))
        lm.lat, lm.lon = lat, lon
        changed.extend(["lat", "lon"])
    try:
        lm.save()
    except IntegrityError:
        raise HttpError(400, "地标数据冲突（target_id 或名称重复）")
    write_audit(request, "landmark.update", f"landmark:{lm.id}", ",".join(changed))
    return {"success": True, "data": _lm_dict(lm, with_intro=True)}


@router.post("/landmarks/{landmark_id}/toggle", summary="上架/下架地标")
@admin_required
def toggle_landmark(request, landmark_id: int):
    """上架/下架地标（下架后地球与搜索不再展示）。"""
    lm = Landmark.objects.filter(id=landmark_id).first()
    if not lm:
        raise HttpError(404, "地标不存在")
    lm.is_active = not lm.is_active
    lm.save(update_fields=["is_active"])
    write_audit(request, "landmark.toggle", f"landmark:{lm.id}", str(lm.is_active))
    return {"success": True, "is_active": lm.is_active}
