"""行旅识景 TripScape
创建日期：2025-09-01

Meilisearch 全局搜索服务。

- 索引：landmarks / comments / journals / users 四类
- 灰度策略：Meilisearch 不可用时自动降级为 Django ORM icontains 查询
- 筛选：按地标 / 用户 / 时间 / 热度
"""

import logging

from django.conf import settings
from django.contrib.auth import get_user_model
from django.utils import timezone

logger = logging.getLogger("tripscape.search")

_client = None
_client_checked = False


def get_client():
    """获取 Meilisearch 客户端（懒加载，失败返回 None）。"""
    global _client, _client_checked
    if _client is None and not _client_checked:
        _client_checked = True
        try:
            import meilisearch

            _client = meilisearch.Client(settings.MEILI_HOST, settings.MEILI_MASTER_KEY)
            _client.health()
            logger.info("Meilisearch 已连接：%s", settings.MEILI_HOST)
        except Exception as exc:
            logger.warning("Meilisearch 不可用，搜索降级为 ORM：%s", exc)
            _client = None
    return _client


def _ensure_indexes(client):
    """确保四个索引存在并配置可过滤属性。"""
    configs = {
        "landmarks": {
            "searchableAttributes": [
                "name",
                "name_en",
                "target_id",
                "country",
                "region",
                "intro",
            ],
            "filterableAttributes": ["region", "country", "kind"],
            "sortableAttributes": ["view_count", "created_ts"],
        },
        "comments": {
            "searchableAttributes": [
                "content",
                "username",
                "nickname",
                "landmark_name",
            ],
            "filterableAttributes": ["landmark_id", "kind", "user_id"],
            "sortableAttributes": ["created_ts"],
        },
        "journals": {
            "searchableAttributes": [
                "title",
                "content",
                "username",
                "nickname",
                "landmark_name",
            ],
            "filterableAttributes": ["landmark_id", "kind", "user_id"],
            "sortableAttributes": ["created_ts"],
        },
        "users": {
            "searchableAttributes": ["username", "nickname", "bio"],
            "filterableAttributes": ["kind"],
            "sortableAttributes": ["created_ts"],
        },
    }
    for uid, cfg in configs.items():
        task = client.create_index(uid, {"primaryKey": "id"})
        client.wait_for_task(task.task_uid)
        client.index(uid).update_settings(cfg)


def rebuild_all():
    """全量重建所有索引（管理端/初始化命令调用）。"""
    client = get_client()
    if client is None:
        return {"meilisearch": "unavailable"}
    _ensure_indexes(client)

    from apps.comments.models import Comment
    from apps.journals.models import Journal
    from apps.landmarks.models import Landmark

    User = get_user_model()

    docs = []
    for lm in Landmark.objects.filter(is_active=True):
        docs.append(
            {
                "id": f"lm_{lm.id}",
                "kind": "landmark",
                "ref_id": lm.id,
                "name": lm.name,
                "name_en": lm.name_en,
                "target_id": lm.target_id,
                "country": lm.country,
                "region": lm.region,
                "intro": (lm.intro or "")[:1000],
                "image_url": lm.image_url,
                "lat": float(lm.lat),
                "lon": float(lm.lon),
                "view_count": lm.view_count,
                "created_ts": int(timezone.now().timestamp()),
            }
        )
    client.index("landmarks").add_documents(docs)

    docs = []
    for c in Comment.objects.filter(is_hidden=False).select_related("user", "landmark")[
        :2000
    ]:
        docs.append(
            {
                "id": f"cm_{c.id}",
                "kind": "comment",
                "ref_id": c.id,
                "content": c.content[:500],
                "landmark_id": c.landmark_id,
                "landmark_name": c.landmark.name if c.landmark_id else "",
                "user_id": c.user_id,
                "username": c.user.username,
                "nickname": c.user.nickname or c.user.username,
                "created_ts": int(c.created_at.timestamp()),
            }
        )
    client.index("comments").add_documents(docs)

    docs = []
    for j in Journal.objects.filter(is_public=True, status="approved").select_related(
        "user", "landmark"
    )[:2000]:
        docs.append(
            {
                "id": f"jn_{j.id}",
                "kind": "journal",
                "ref_id": j.id,
                "title": j.title,
                "content": (j.content or "")[:500],
                "landmark_id": j.landmark_id,
                "landmark_name": j.landmark.name,
                "user_id": j.user_id,
                "username": j.user.username,
                "nickname": j.user.nickname or j.user.username,
                "images": (j.images or [])[:1],
                "created_ts": int(j.created_at.timestamp()),
            }
        )
    client.index("journals").add_documents(docs)

    docs = []
    for u in User.objects.filter(is_active=True)[:2000]:
        docs.append(
            {
                "id": f"us_{u.id}",
                "kind": "user",
                "ref_id": u.id,
                "username": u.username,
                "nickname": u.nickname or u.username,
                "avatar": u.avatar,
                "bio": u.bio,
                "created_ts": int(u.created_at.timestamp()),
            }
        )
    client.index("users").add_documents(docs)
    return {"meilisearch": "rebuilt"}


# ----------------------------------------------------------------------
# 单对象增量同步
# ----------------------------------------------------------------------
def sync_landmark_to_meili(lm):
    """地标变更后同步到 Meilisearch（不可用时静默跳过）。"""
    client = get_client()
    if client is None:
        return
    client.index("landmarks").add_documents(
        [
            {
                "id": f"lm_{lm.id}",
                "kind": "landmark",
                "ref_id": lm.id,
                "name": lm.name,
                "name_en": lm.name_en,
                "target_id": lm.target_id,
                "country": lm.country,
                "region": lm.region,
                "intro": (lm.intro or "")[:1000],
                "image_url": lm.image_url,
                "lat": float(lm.lat),
                "lon": float(lm.lon),
                "view_count": lm.view_count,
                "created_ts": int(timezone.now().timestamp()),
            }
        ]
    )


def sync_comment_to_meili(c):
    """评论变更后同步到 Meilisearch。"""
    client = get_client()
    if client is None:
        return
    client.index("comments").add_documents(
        [
            {
                "id": f"cm_{c.id}",
                "kind": "comment",
                "ref_id": c.id,
                "content": c.content[:500],
                "landmark_id": c.landmark_id,
                "landmark_name": c.landmark.name if c.landmark_id else "",
                "user_id": c.user_id,
                "username": c.user.username,
                "nickname": c.user.nickname or c.user.username,
                "created_ts": int(c.created_at.timestamp()),
            }
        ]
    )


def sync_journal_to_meili(j):
    """手账变更后同步到 Meilisearch。"""
    client = get_client()
    if client is None:
        return
    if not (j.is_public and j.status == "approved"):
        remove_from_meili("journal", j.id)
        return
    client.index("journals").add_documents(
        [
            {
                "id": f"jn_{j.id}",
                "kind": "journal",
                "ref_id": j.id,
                "title": j.title,
                "content": (j.content or "")[:500],
                "landmark_id": j.landmark_id,
                "landmark_name": j.landmark.name,
                "user_id": j.user_id,
                "username": j.user.username,
                "nickname": j.user.nickname or j.user.username,
                "images": (j.images or [])[:1],
                "created_ts": int(j.created_at.timestamp()),
            }
        ]
    )


def remove_from_meili(kind: str, ref_id: int):
    """从 Meilisearch 删除指定文档。"""
    client = get_client()
    if client is None:
        return
    prefix = {"landmark": "lm", "comment": "cm", "journal": "jn", "user": "us"}.get(
        kind
    )
    if not prefix:
        return
    index_map = {
        "landmark": "landmarks",
        "comment": "comments",
        "journal": "journals",
        "user": "users",
    }
    client.index(index_map[kind]).delete_document(f"{prefix}_{ref_id}")


# ----------------------------------------------------------------------
# 搜索入口
# ----------------------------------------------------------------------
def global_search(
    query: str,
    kind: str = "all",
    landmark_id: int = None,
    user_id: int = None,
    start_ts: int = None,
    end_ts: int = None,
    sort: str = "relevance",
    page: int = 1,
    page_size: int = 20,
):
    """全局搜索。

    参数：
        query       关键词
        kind        all / landmark / comment / journal / user
        landmark_id 按地标筛选
        user_id     按用户筛选
        start_ts/end_ts  时间戳范围筛选
        sort        relevance / time / hot
    """
    if get_client() is not None:
        return _search_meili(
            query, kind, landmark_id, user_id, start_ts, end_ts, sort, page, page_size
        )
    return _search_orm(
        query, kind, landmark_id, user_id, start_ts, end_ts, sort, page, page_size
    )


def _search_meili(
    query, kind, landmark_id, user_id, start_ts, end_ts, sort, page, page_size
):
    client = get_client()
    kind_index = {
        "landmark": "landmarks",
        "comment": "comments",
        "journal": "journals",
        "user": "users",
    }
    kinds = [kind] if kind in kind_index else list(kind_index)
    results = []
    for k in kinds:
        idx = client.index(kind_index[k])
        opts = {"limit": page * page_size, "offset": 0}
        filters = []
        if landmark_id and k in ("comment", "journal"):
            filters.append(f"landmark_id = {landmark_id}")
        if user_id and k in ("comment", "journal"):
            filters.append(f"user_id = {user_id}")
        if start_ts:
            filters.append(f"created_ts >= {start_ts}")
        if end_ts:
            filters.append(f"created_ts <= {end_ts}")
        if filters:
            opts["filter"] = " AND ".join(filters)
        if sort == "time":
            opts["sort"] = ["created_ts:desc"]
        elif sort == "hot" and k == "landmark":
            opts["sort"] = ["view_count:desc"]
        res = idx.search(query or "", opts)
        for hit in res.get("hits", [])[(page - 1) * page_size : page * page_size]:
            results.append(_hit_to_item(hit))
    total = sum(res.get("estimatedTotalHits", 0) for _ in [0])  # 近似
    return {
        "items": results,
        "source": "meilisearch",
        "page": page,
        "page_size": page_size,
    }


def _search_orm(
    query, kind, landmark_id, user_id, start_ts, end_ts, sort, page, page_size
):
    """ORM 降级搜索。"""
    from apps.comments.models import Comment
    from apps.journals.models import Journal
    from apps.landmarks.models import Landmark

    User = get_user_model()
    items = []
    offset = (page - 1) * page_size  # 翻页偏移（TS-10：修复每页重复第一页）

    def ts(dt):
        """时间戳字段提取（Meilisearch 文档用）。"""
        return int(dt.timestamp()) if dt else 0

    def in_range(dt):
        """判断日期是否在检索区间内。"""
        t = ts(dt)
        if start_ts and t < start_ts:
            return False
        if end_ts and t > end_ts:
            return False
        return True

    if kind in ("all", "landmark"):
        qs = Landmark.objects.filter(is_active=True)
        if query:
            qs = qs.filter(name__icontains=query) | Landmark.objects.filter(
                name_en__icontains=query, is_active=True
            )
        qs = qs.order_by("-view_count" if sort == "hot" else "id")
        for lm in qs[offset : offset + page_size]:
            items.append(
                {
                    "kind": "landmark",
                    "id": lm.id,
                    "title": lm.name,
                    "subtitle": lm.country or lm.region,
                    "image_url": lm.image_url,
                    "extra": f"热度 {lm.view_count}",
                    "created_ts": 0,
                    "link": f"/landmarks/{lm.id}",
                }
            )

    if kind in ("all", "comment"):
        qs = Comment.objects.filter(is_hidden=False).select_related("user", "landmark")
        if query:
            qs = qs.filter(content__icontains=query)
        if landmark_id:
            qs = qs.filter(landmark_id=landmark_id)
        if user_id:
            qs = qs.filter(user_id=user_id)
        qs = qs.order_by(
            "-created_at" if sort in ("time", "relevance") else "-created_at"
        )
        for c in qs[offset : offset + page_size]:
            if not in_range(c.created_at):
                continue
            items.append(
                {
                    "kind": "comment",
                    "id": c.id,
                    "title": c.content[:60],
                    "subtitle": f"{c.user.nickname or c.user.username} @ {c.landmark.name}",
                    "image_url": c.user.avatar,
                    "extra": "",
                    "created_ts": ts(c.created_at),
                    "link": f"/landmarks/{c.landmark_id}?tab=comments",
                }
            )

    if kind in ("all", "journal"):
        qs = Journal.objects.filter(
            is_public=True, status="approved", deleted_at__isnull=True
        ).select_related(
            "user", "landmark"
        )
        if query:
            qs = qs.filter(title__icontains=query) | Journal.objects.filter(
                content__icontains=query, is_public=True, status="approved"
            )
        if landmark_id:
            qs = qs.filter(landmark_id=landmark_id)
        if user_id:
            qs = qs.filter(user_id=user_id)
        qs = qs.order_by("-created_at")
        for j in qs[offset : offset + page_size]:
            if not in_range(j.created_at):
                continue
            items.append(
                {
                    "kind": "journal",
                    "id": j.id,
                    "title": j.title,
                    "subtitle": f"{j.user.nickname or j.user.username} @ {j.landmark.name}",
                    "image_url": (j.images or [""])[0],
                    "extra": "",
                    "created_ts": ts(j.created_at),
                    "link": f"/journals/{j.id}",
                }
            )

    if kind in ("all", "user"):
        qs = User.objects.filter(is_active=True, banned=False)
        if query:
            qs = User.objects.filter(
                is_active=True, banned=False, username__icontains=query
            ) | User.objects.filter(
                is_active=True, banned=False, nickname__icontains=query
            )
        for u in qs[offset : offset + page_size]:
            items.append(
                {
                    "kind": "user",
                    "id": u.id,
                    "title": u.nickname or u.username,
                    "subtitle": u.username,
                    "image_url": u.avatar,
                    "extra": u.bio[:60],
                    "created_ts": ts(u.created_at),
                    "link": f"/users/{u.id}",
                }
            )

    if sort == "time":
        items.sort(key=lambda x: x.get("created_ts", 0), reverse=True)

    return {"items": items, "source": "orm", "page": page, "page_size": page_size}


def _hit_to_item(hit):
    kind = hit.get("kind", "")
    if kind == "landmark":
        return {
            "kind": "landmark",
            "id": hit["ref_id"],
            "title": hit.get("name", ""),
            "subtitle": hit.get("country", ""),
            "image_url": hit.get("image_url", ""),
            "extra": f"热度 {hit.get('view_count', 0)}",
            "created_ts": hit.get("created_ts", 0),
            "link": f"/landmarks/{hit['ref_id']}",
        }
    if kind == "comment":
        return {
            "kind": "comment",
            "id": hit["ref_id"],
            "title": hit.get("content", "")[:60],
            "subtitle": f"{hit.get('nickname', '')} @ {hit.get('landmark_name', '')}",
            "image_url": "",
            "extra": "",
            "created_ts": hit.get("created_ts", 0),
            "link": f"/landmarks/{hit.get('landmark_id')}?tab=comments",
        }
    if kind == "journal":
        return {
            "kind": "journal",
            "id": hit["ref_id"],
            "title": hit.get("title", ""),
            "subtitle": f"{hit.get('nickname', '')} @ {hit.get('landmark_name', '')}",
            "image_url": (hit.get("images") or [""])[0],
            "extra": "",
            "created_ts": hit.get("created_ts", 0),
            "link": f"/journals/{hit['ref_id']}",
        }
    if kind == "user":
        return {
            "kind": "user",
            "id": hit["ref_id"],
            "title": hit.get("nickname", ""),
            "subtitle": hit.get("username", ""),
            "image_url": hit.get("avatar", ""),
            "extra": (hit.get("bio") or "")[:60],
            "created_ts": hit.get("created_ts", 0),
            "link": f"/users/{hit['ref_id']}",
        }
    return hit


def healthy() -> bool:
    """依赖健康检查（供 /readyz 探针）。"""
    return get_client() is not None
