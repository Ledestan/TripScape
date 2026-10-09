"""行旅识景 TripScape
创建日期：2025-09-01

地标管理区块（并入 admin.py 主路由）。

从 admin_landmarks.py 合并而来；路由路径与原先 /api/admin/landmarks/* 完全一致。
"""


from apps.landmarks.models import Landmark
from ninja import Schema
from ninja.errors import HttpError

from api.admin import router, write_audit, admin_required


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
def list_landmarks(request, q: str = "", region: str = "", is_active: str = "", page: int = 1, page_size: int = 50):
    """地标列表（管理端）：支持 名称/地区/上下架 筛选与分页。"""
    qs = Landmark.objects.all().order_by("id")
    if q:
        from django.db.models import Q

        qs = qs.filter(Q(name__icontains=q) | Q(name_en__icontains=q) | Q(country__icontains=q))
    if region:
        qs = qs.filter(region=region)
    if is_active == "true":
        qs = qs.filter(is_active=True)
    elif is_active == "false":
        qs = qs.filter(is_active=False)
    total = qs.count()
    items = qs[(page - 1) * page_size : page * page_size]
    return {"success": True, "data": [_lm_dict(lm, with_intro=True) for lm in items], "meta": {"total": total, "page": page}}


@router.post("/landmarks", summary="新增地标")
@admin_required
def create_landmark(request, payload: LandmarkIn):
    """新增地标（target_id 缺省由名称生成，重复即 400）。"""
    if not payload.name.strip():
        raise HttpError(400, "名称不能为空")
    tid = payload.target_id.strip() or payload.name.strip().lower().replace(" ", "_")
    if Landmark.objects.filter(target_id=tid).exists():
        raise HttpError(400, f"target_id「{tid}」已存在")
    lm = Landmark.objects.create(
        target_id=tid[:50],
        name=payload.name.strip()[:100],
        name_en=payload.name_en.strip()[:100],
        region=payload.region.strip()[:64],
        country=payload.country.strip()[:64],
        lat=payload.lat,
        lon=payload.lon,
        intro=payload.intro,
        image_url=payload.image_url[:512],
    )
    write_audit(request, "landmark.create", f"landmark:{lm.id}", lm.name)
    return {"success": True, "data": _lm_dict(lm, with_intro=True)}


@router.put("/landmarks/{landmark_id}", summary="修改地标")
@admin_required
def update_landmark(request, landmark_id: int, payload: LandmarkUpdateIn):
    """修改地标字段（仅更新传入的非空字段）。"""
    lm = Landmark.objects.filter(id=landmark_id).first()
    if not lm:
        raise HttpError(404, "地标不存在")
    changed = []
    for f, v in (
        ("name", payload.name), ("name_en", payload.name_en), ("region", payload.region),
        ("country", payload.country), ("intro", payload.intro), ("image_url", payload.image_url),
    ):
        if v:
            setattr(lm, f, v)
            changed.append(f)
    if payload.lat is not None:
        lm.lat = payload.lat
        changed.append("lat")
    if payload.lon is not None:
        lm.lon = payload.lon
        changed.append("lon")
    lm.save()
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
