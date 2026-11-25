"""
行旅识景 TripScape / 叙事服务
创建日期: 2025-11-24

叙事层的业务实现（2.0 本体），提供:
    1. build_narrative_card / latest_card：卡片组装与读取
    2. _time_fragments / _rag_snippets / _geo：三个切面的取值与降级
    3. add_card_to_journal / journal_cards：卡片与手记的持久化
    4. deliver_fragment / pick_fragment / pick_fragment_by_id：碎片投递与单次拾取
    5. as_card / journal_payload / fragment_payload：对外序列化口径

依赖:
    需求文件: requirements.txt
    依赖库:
        Django==5.2
        仅 Django（页面内容全部来自预置文件，不在此处调用分词与向量检索）

用法:
    from services import narrative_service as narrative
    card = narrative.build_narrative_card(landmark, user=user, confidence=0.91)

注意:
    1. 文化内容只取仓库内真实数据：文章库句子与 ts_landmark.intro，不编造年份。
    2. 页面文件缺失时降级到 ts_landmark.intro，最末级兜底是明确的"尚无纪年史料登记"声明。
    3. 碎片对外不暴露投递者身份，库内保留为额度统计与自投排除。
"""

import logging
import re

from django.conf import settings

from apps.narrative.models import (
    FragmentPickup,
    JournalCard,
    NarrativeCard,
    NarrativeFragment,
)

logger = logging.getLogger(__name__)

# 时间碎片只在这些章节里找（文章库的固定章节名）
TIME_SECTIONS = ("历史沿革", "概述", "前言")

# 句子切分：中文句末标点 + 换行（与文章库的排版一致）
_SENT_SPLIT = re.compile(r"(?<=[。！？；])\s*|\n+")
# 纪年抽取：只认真实年份表达式，抽不到就 year=None（绝不补写）
_YEAR_RE = re.compile(r"(公元前)?\s*(\d{3,4})\s*年")
_MAX_FRAGMENTS_PER_LANDMARK = 3

# 检索片段按地标缓存（卡片高频创建，避免重复 encode）


class NarrativeError(Exception):
    """服务层业务错误（由 api 层翻译为 HttpError）。

    参数：
        message : str，面向用户的中文错误消息（含限额/唯一性说明）
        status  : int，建议的 HTTP 状态码
    """

    def __init__(self, message: str, status: int = 400):
        self.message = message
        self.status = status
        super().__init__(message)


# ======================================================================
# 文本工具
# ======================================================================
def _sentences(text: str):
    """切句并清理 markdown 残留（空句丢弃，保留句末标点）。"""
    out = []
    for part in _SENT_SPLIT.split(text or ""):
        s = re.sub(r"^[\s\-*·#|>]+", "", part or "").strip()
        s = re.sub(r"thumb\|\d+px\|?", "", s).strip()
        if len(s) >= 6 and not s.startswith(("|", "}}")):
            out.append(s)
    return out


def _extract_year(text: str):
    """抽取纪年（公元前转负数），抽不到返回 None。"""
    m = _YEAR_RE.search(text or "")
    if not m:
        return None
    year = int(m.group(2))
    return -year if m.group(1) else year


def _title(landmark) -> str:
    """卡片标题：地标名 + 归属地（有国家才拼接，不虚构称谓）。"""
    name = (landmark.name or landmark.target_id).strip()
    country = (landmark.country or "").strip()
    return f"{name}｜{country}" if country else name


def _geo(landmark) -> dict:
    """地理绑定：坐标直接取地标表（Decimal -> float）。"""
    return {
        "lat": float(landmark.lat),
        "lon": float(landmark.lon),
        "place": landmark.name,
        "country": landmark.country or "",
        "region": landmark.region or "",
    }


# ======================================================================
# S2：页面材料（预置文件，绝不在这里分词）
# ======================================================================
def _page(landmark):
    """读取预置的页面文件；没有就返回 None（由上层降级，不现场分词）。"""
    from services import landmark_pages

    return landmark_pages.page_for(landmark)


def _time_fragments(landmark) -> list:
    """时间碎片：直接取预置文件，按年份升序、无年份置后。

    返回：
        list of dict：{text, year, section, targetId, source}
    """
    page = _page(landmark)
    picked = list(page.get("time_fragments", [])) if page else []

    dated = sorted([f for f in picked if f.get("year") is not None], key=lambda f: f["year"])
    undated = [f for f in picked if f.get("year") is None]
    fragments = (dated + undated)[:_MAX_FRAGMENTS_PER_LANDMARK]

    if not fragments:
        # 降级：地标简介的真实句子（年份缺失即 None，不补写）
        for sent in _sentences(landmark.intro or "")[:2]:
            fragments.append(
                {
                    "text": sent,
                    "year": _extract_year(sent),
                    "section": "intro",
                    "targetId": landmark.target_id,
                    "source": "db:ts_landmark.intro",
                }
            )
    if not fragments:
        # 最终兜底：只有名称与归属，零文化内容编造
        fragments.append(
            {
                "text": f"{landmark.name}（尚无纪年史料登记）",
                "year": None,
                "section": "landmark",
                "targetId": landmark.target_id,
                "source": "db:ts_landmark",
            }
        )
    return fragments


# ======================================================================
# S2：文献摘录（预置文件，不走向量检索）
# ======================================================================
def _rag_snippets(landmark, top_k: int = 3) -> list:
    """文献摘录：取预置文件里的段落；缺失时降级到地标简介。

    返回：
        list of dict：{text, section, targetId, score, source}
    """
    page = _page(landmark)
    snippets = list(page.get("snippets", []))[:top_k] if page else []

    if not snippets:
        for sent in _sentences(landmark.intro or "")[:top_k]:
            snippets.append(
                {
                    "text": sent[:240],
                    "section": "intro",
                    "targetId": landmark.target_id,
                    "score": None,
                    "source": "db:ts_landmark.intro",
                }
            )
    if not snippets:
        snippets.append(
            {
                "text": f"{landmark.name}",
                "section": "landmark",
                "targetId": landmark.target_id,
                "score": None,
                "source": "db:ts_landmark",
            }
        )
    return snippets


# ======================================================================
# S2：卡片组装
# ======================================================================
def build_narrative_card(landmark, *, user=None, photo: str = "", confidence: float = 0.0, source: str = "retrieval"):
    """组装并持久化一张叙事卡片（SPEC §2 S2 固定字段集）。

    参数：
        landmark   : Landmark，识别出的地标
        user       : User 或 None，识别者（匿名识别允许为空）
        photo      : str，原图 URL（空则回退地标百科图，始终只存引用）
        confidence : float，识别置信度（0–1）
        source     : str，来源标签（retrieval / landmark / ...）

    返回：
        NarrativeCard
    """
    author = user if (user is not None and getattr(user, "is_authenticated", False)) else None
    return NarrativeCard.objects.create(
        landmark=landmark,
        user=author,
        photo=(photo or landmark.image_url or "")[:512],
        title=_title(landmark)[:128],
        geo=_geo(landmark),
        time_fragments=_time_fragments(landmark),
        rag_snippets=_rag_snippets(landmark),
        confidence=max(0.0, min(1.0, float(confidence))),
        source=(source or "retrieval")[:32],
    )


def latest_card(landmark) -> NarrativeCard:
    """取该地标最新卡片；没有则现建一张（来源 landmark，置信度 0.0）。"""
    card = NarrativeCard.objects.filter(landmark=landmark).order_by("-created_at", "-id").first()
    if card is None:
        card = build_narrative_card(landmark, confidence=0.0, source="landmark")
    return card


# ======================================================================
# S1：手账（只读持久化）
# ======================================================================
def add_card_to_journal(user, card_id: int) -> dict:
    """把卡片加入手账（幂等；只读——不提供编辑/覆盖接口）。"""
    card = NarrativeCard.objects.filter(id=card_id).first()
    if card is None:
        raise NarrativeError("叙事卡片不存在", 404)
    entry, created = JournalCard.objects.get_or_create(user=user, card=card)
    return {"created": created, "entry": journal_payload(entry)}


def journal_payload(entry: JournalCard) -> dict:
    """手账条目序列化（卡片为只读快照，附加入时间）。"""
    return {
        "card": entry.card.as_card(),
        "addedAt": entry.added_at.isoformat(),
    }


def journal_cards(user):
    """我的手账卡片（按加入时间倒序，刷新后从库中取回）。"""
    qs = (
        JournalCard.objects.filter(user=user)
        .select_related("card")
        .order_by("-added_at", "-id")
    )
    return [journal_payload(e) for e in qs]


# ======================================================================
# S3：碎片投递与拾取
# ======================================================================
def fragment_limit() -> int:
    """单用户单地标投递上限（SPEC §2 S3：最多 3 条）。"""
    return int(getattr(settings, "NARRATIVE_MAX_FRAGMENTS_PER_LANDMARK", 3))


def deliver_fragment(user, card_id: int, landmark_id: int) -> dict:
    """把手账卡片匿名投递到地标（同用户同地标上限 fragment_limit()）。"""
    card = NarrativeCard.objects.filter(id=card_id).first()
    if card is None:
        raise NarrativeError("叙事卡片不存在", 404)
    from apps.landmarks.models import Landmark

    landmark = Landmark.objects.filter(id=landmark_id).first()
    if landmark is None:
        raise NarrativeError("地标不存在", 404)
    if not JournalCard.objects.filter(user=user, card=card).exists():
        raise NarrativeError("只能投递手账中的叙事卡片", 403)

    limit = fragment_limit()
    used = NarrativeFragment.objects.filter(delivered_by=user, landmark=landmark).count()
    if used >= limit:
        raise NarrativeError(
            f"同一地标最多投递 {limit} 条叙事碎片，你已投递 {used} 条", 409
        )

    frag = NarrativeFragment.objects.create(card=card, landmark=landmark, delivered_by=user)
    logger.info("叙事碎片投递：fragment=%s landmark=%s", frag.id, landmark.id)
    return {
        "fragmentId": frag.id,
        "landmarkId": landmark.id,
        "deliveredCount": used + 1,
        "remaining": limit - used - 1,
    }


def _unpicked_queryset(user, landmark_id: int):
    """该地标下"非本人投递、且本人未拾取"的碎片。"""
    picked = FragmentPickup.objects.filter(user=user).values_list("fragment_id", flat=True)
    return (
        NarrativeFragment.objects.filter(landmark_id=landmark_id)
        .exclude(delivered_by=user)
        .exclude(id__in=picked)
        .select_related("card")
        .order_by("created_at", "id")
    )


def pick_fragment(user, landmark_id: int) -> dict:
    """拾取一条未被自己拾取过的碎片（无可用碎片则 404）。"""
    frag = _unpicked_queryset(user, landmark_id).first()
    if frag is None:
        raise NarrativeError("该地标暂无可拾取的叙事碎片", 404)
    FragmentPickup.objects.create(fragment=frag, user=user)
    return fragment_payload(frag)


def pick_fragment_by_id(user, fragment_id: int) -> dict:
    """按 ID 拾取碎片；同一碎片对同一用户第二次拾取被拒绝（409）。"""
    frag = NarrativeFragment.objects.filter(id=fragment_id).select_related("card").first()
    if frag is None:
        raise NarrativeError("叙事碎片不存在", 404)
    if FragmentPickup.objects.filter(fragment=frag, user=user).exists():
        raise NarrativeError("该碎片已被你拾取过，不能重复拾取", 409)
    FragmentPickup.objects.create(fragment=frag, user=user)
    return fragment_payload(frag)


def fragment_payload(frag: NarrativeFragment) -> dict:
    """碎片序列化：含来源卡片摘要，绝不含投递者身份（匿名性）。"""
    card = frag.card
    snippets = card.rag_snippets or []
    return {
        "id": frag.id,
        "landmarkId": frag.landmark_id,
        "createdAt": frag.created_at.isoformat(),
        "anonymous": True,
        "sourceCard": {
            "id": card.id,
            "title": card.title,
            "photo": card.photo,
            "landmarkId": card.landmark_id,
            "confidence": float(card.confidence),
            "snippet": (snippets[0].get("text", "") if snippets else "")[:120],
        },
    }


def pickup_count(user) -> int:
    """我的拾取总数（界面提示用）。"""
    return FragmentPickup.objects.filter(user=user).count()
