"""
行旅识景 TripScape / 地标页面预置内容

把「地标页要显示的一切」预生成成文件，避免打开地标时再去分词/建索引，提供:
    1. PAGES_DIR：backend/content/landmarks/<target_id>.json 的固定位置
    2. page_for：按地标读取页面文件（进程内缓存，按文件 mtime 失效）
    3. build_pages：从文章库与地标表一次性生成全部页面文件（幂等）

依赖:
    需求文件: requirements.txt
    依赖库:
        Django==5.2

用法:
    from services import landmark_pages
    landmark_pages.build_pages()               # 种子阶段调用
    page = landmark_pages.page_for(landmark)   # 接口阶段调用

注意:
    1. 打开地标只读这一个 JSON，不触发 jieba 分词与向量检索（那些只服务问答）。
    2. 文件缺失时返回 None，由调用方给 404 并提示重新生成，而不是现场分词。
    3. 生成顺序按 target_id 排序，保证同一份语料得到完全相同的文件。
"""

import json
import re
from datetime import datetime
from pathlib import Path

from django.conf import settings
from services.text_utils import extract_year, split_sentences

PAGES_DIR = Path(settings.BASE_DIR) / "backend" / "content" / "landmarks"
CORPUS_PATH = Path(settings.BASE_DIR) / "runtime" / "index" / "qa_chunks.json"

SECTION_ORDER = [
    "概述",
    "前言",
    "更多介绍",
    "历史沿革",
    "地理位置",
    "基本参数",
    "参观信息",
    "百科补充",
]
# 章节 -> 小标题：顺序即页面上的阅读顺序（intro 之后依次展开）
SECTION_TITLES = {
    "前言": "写在前面",
    "历史沿革": "走过的年代",
    "地理位置": "站在这里",
    "基本参数": "尺度与参数",
    "参观信息": "到访之前",
    "百科补充": "补记",
    "更多介绍": "再看一眼",
}
TIME_SECTIONS = ("历史沿革", "概述", "前言")
SOURCE_LABEL = "仓库文章库 runtime/index/qa_chunks.json（Wikipedia 摘编）"

# 进程内缓存：文件 mtime 未变就不重复读盘
_CACHE: dict[str, dict] = {}


def group_chunks(index_path: Path = CORPUS_PATH) -> dict[str, list[dict]]:
    """按 target_id 归组语料块；语料缺失给出可执行的修复提示。"""
    if not index_path.exists():
        raise FileNotFoundError(
            f"文章库不存在: {index_path}；请先运行 python scripts/build_qa_index.py"
        )
    chunks = json.loads(index_path.read_text(encoding="utf-8"))
    grouped: dict[str, list[dict]] = {}
    for chunk in chunks:
        grouped.setdefault(chunk["target_id"], []).append(chunk)
    return grouped


def _section_sentences(chunks: list[dict], section: str, limit: int = 20) -> list[str]:
    """取某章节的句子（固定顺序）。"""
    sentences: list[str] = []
    for chunk in chunks:
        if chunk.get("section") != section:
            continue
        sentences.extend(split_sentences(chunk.get("text", "")))
        if len(sentences) >= limit:
            break
    return sentences[:limit]


_PUNCT_RE = re.compile(r"[\s，。；：、（）()「」“”\"'·—…！？]|\\s")


def _bigrams(text: str) -> set[str]:
    """按标点切开后取二元字组，用于判断两句话是不是"同一个意思"。"""
    clean = _PUNCT_RE.sub("", text)
    return {clean[index : index + 2] for index in range(len(clean) - 1)}


def _jaccard(left: set[str], right: set[str]) -> float:
    """两个二元字组集合的 Jaccard 相似度（0–1）。"""
    if not left or not right:
        return 0.0
    return len(left & right) / len(left | right)


_NUMBER_RE = re.compile(r"\d{3,}")

# 以这些词开头的句子是上一句的续写（"以感谢建造时…"），放进时间轴会读成半句
_CONTINUATION_STARTS = (
    "以",
    "并",
    "而",
    "但",
    "同时",
    "因此",
    "所以",
    "于是",
    "其中",
    "此外",
    "另外",
    "同年",
    "随后",
    "此后",
)


def _key_numbers(text: str) -> set[str]:
    """关键数字：三位以上的数字（年份、高度、构件数），用于识别"同一段事实"。"""
    return set(_NUMBER_RE.findall(text))


def build_page(landmark, chunks: list[dict]) -> dict:
    """组装一个地标的页面数据（故事 + 卡片材料 + 展示元信息）。"""
    seen: set[str] = set()
    kept_bigrams: list[set[str]] = []
    kept_numbers: list[set[str]] = []

    def unique(items: list[str]) -> list[str]:
        """按"字面重复""字面高度相似""关键数字重合"三重去重。

        概述与更多介绍常常是同一段话的两种写法（都讲修建年份、高度、意义），
        只比字符串会把同一句话留两遍，读起来像是复制粘贴。
        这里用二元字组 Jaccard 相似度 + 关键数字集合判断：两句话共享两个以上
        三位以上数字（1889 年、330 米…）时视为同一段事实，只留先出现的那句。
        """
        kept: list[str] = []
        for item in items:
            if not item or item in seen:
                continue
            grams = _bigrams(item)
            if any(_jaccard(grams, other) > 0.5 for other in kept_bigrams):
                continue
            numbers = _key_numbers(item)
            if len(numbers) >= 2 and any(
                len(numbers & other) >= 2 for other in kept_numbers
            ):
                continue
            seen.add(item)
            kept_bigrams.append(grams)
            kept_numbers.append(numbers)
            kept.append(item)
        return kept

    # 整体介绍：概述（或前言）最多三句——三句足够说清"这是什么地方"，
    # 再多就会和下面的分节重复（同一段事实换个说法再说一遍）。
    # 只有句子太少（不足两句）时才借更多介绍 / 百科补充，避免开篇太空。
    intro_items = unique(
        _section_sentences(chunks, "概述", 3) or _section_sentences(chunks, "前言", 3)
    )
    # 概述常常只有一两句短句（"位于开罗近郊，包括三座金字塔。"就没了），
    # 少于 90 字时补更多介绍 / 百科补充，补到能独立成段为止（最多 5 句）
    if len("".join(intro_items)) < 90:
        intro_items += unique(_section_sentences(chunks, "更多介绍", 2))
    if len("".join(intro_items)) < 90:
        # 百科补充是"补记"小节的唯一来源：至少给它留两句（否则拆不出两节），
        # 最多借一句补开篇
        extra_pool = _section_sentences(chunks, "百科补充", 6)
        spare = max(0, len(extra_pool) - 2)
        if spare:
            intro_items += unique(extra_pool[:1])
    intro = "".join(intro_items[:5]).strip()

    # 时间轴：每个年份只取一句，升序；句子允许与整体介绍重复（时间锚点优先）
    # 优先选"句首能立住"的句子：以连词开头的是上一句的续写，放进时间轴会读成半句
    timeline: list[dict] = []
    seen_years: set[int] = set()
    continuations: list[dict] = []
    for section in SECTION_ORDER:
        for sentence in _section_sentences(chunks, section, 30):
            year = extract_year(sentence)
            if year is None or year in seen_years:
                continue
            seen_years.add(year)
            entry = {"year": year, "text": sentence}
            if sentence.startswith(_CONTINUATION_STARTS):
                continuations.append(entry)
            else:
                timeline.append(entry)
            if len(timeline) >= 6:
                break
        if len(timeline) >= 6:
            break
    # 时间轴不足两条时才用续写句补位（否则宁可从简）
    if len(timeline) < 2:
        timeline.extend(continuations[: 2 - len(timeline)])
    # 有年份的在前（升序），未记年的在后，保证 None 不参与比较
    timeline.sort(
        key=lambda item: (
            item["year"] is None,
            item["year"] if item["year"] is not None else 0,
        )
    )

    if not timeline:
        # 语料里确实没有年份：用两句未记年的材料撑起时间轴的阅读节奏，明确标注未记年
        for section in ("历史沿革", "概述", "更多介绍"):
            for sentence in _section_sentences(chunks, section, 6):
                if any(item["text"] == sentence for item in timeline):
                    continue
                timeline.append({"year": None, "text": sentence})
                if len(timeline) >= 2:
                    break
            if len(timeline) >= 2:
                break

    # 分节材料：按阅读顺序铺开，每节 2-3 句，让页面像一篇完整的介绍
    sections: list[dict] = []
    for section, heading in SECTION_TITLES.items():
        items = unique(_section_sentences(chunks, section, 3))
        if items:
            sections.append({"heading": heading, "items": items})

    # 语料很薄的地标（只有概述 + 百科补充）也要有段落结构：
    # 把最长的一节拆成两节，标题用中性的导航词，内容仍是原句
    if len(sections) < 2:
        richest = (
            max(sections, key=lambda item: len(item["items"])) if sections else None
        )
        if richest and len(richest["items"]) >= 2:
            tail = richest["items"][1:]
            richest["items"] = richest["items"][:1]
            sections.append({"heading": "再看一眼", "items": tail})

    # 卡片用的时间碎片：只在纪年类章节里挑，年份缺失不补写
    time_fragments: list[dict] = []
    for section in TIME_SECTIONS:
        for sentence in _section_sentences(chunks, section, 12):
            if sentence in {item["text"] for item in time_fragments}:
                continue
            time_fragments.append(
                {
                    "text": sentence,
                    "year": extract_year(sentence),
                    "section": section,
                    "targetId": landmark.target_id,
                    "source": SOURCE_LABEL,
                }
            )
            if len(time_fragments) >= 3:
                break
        if len(time_fragments) >= 3:
            break

    # 卡片用的文献摘录：从非纪年章节里取，不再走检索
    snippets: list[dict] = []
    for section in ("基本参数", "地理位置", "更多介绍", "参观信息", "百科补充"):
        for sentence in _section_sentences(chunks, section, 6):
            if any(item["text"] == sentence for item in snippets):
                continue
            snippets.append(
                {
                    "text": sentence[:240],
                    "section": section,
                    "targetId": landmark.target_id,
                    "score": None,
                    "source": f"preset:{section}",
                }
            )
            if len(snippets) >= 3:
                break
        if len(snippets) >= 3:
            break

    country = landmark.country or ""
    return {
        # 不写 landmarkId：数据库自增 id 会随重建变化，接口返回时用当前地标 id
        "landmark": landmark.name,
        "target_id": landmark.target_id,
        "title": f"{landmark.name}｜{country}" if country else landmark.name,
        "country": country,
        "region": landmark.region or "",
        "photo": landmark.image_url or "",
        "geo": {
            "lat": float(landmark.lat),
            "lon": float(landmark.lon),
            "place": landmark.name,
            "country": country,
            "region": landmark.region or "",
        },
        "intro": intro,
        "timeline": timeline,
        "sections": sections,
        "time_fragments": time_fragments,
        # snippets 只供识别卡片的文献字段使用；地标页不再展示摘录与出处
        "snippets": snippets,
        "built_at": datetime.now().isoformat(timespec="seconds"),
    }


def build_pages(verbose: bool = False) -> dict:
    """生成全部地标页面文件（幂等，返回统计）。"""
    from apps.landmarks.models import Landmark

    grouped = group_chunks()
    PAGES_DIR.mkdir(parents=True, exist_ok=True)
    written = skipped = unchanged = 0
    # 排序后遍历：同一份语料每次生成顺序一致
    from apps.landmarks.validators import is_valid_target_id

    for landmark in Landmark.objects.order_by("target_id"):
        if not is_valid_target_id(landmark.target_id):
            # 非法 target_id 不落盘（既防穿越，也避免生成不可读文件）
            skipped += 1
            continue
        chunks = grouped.get(landmark.target_id, [])
        if not chunks:
            skipped += 1
            continue
        page = build_page(landmark, chunks)
        target = PAGES_DIR / f"{landmark.target_id}.json"

        # 内容没变就不落盘：避免每次生成只刷新 built_at，制造无意义的 diff
        if target.exists():
            previous = json.loads(target.read_text(encoding="utf-8"))
            if {**previous, "built_at": None} == {**page, "built_at": None}:
                unchanged += 1
                continue

        target.write_text(
            json.dumps(page, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        written += 1
        if verbose:
            print(f"页面已生成: {target.name}（{len(page['timeline'])} 条时间轴）")
    return {"written": written, "unchanged": unchanged, "skipped": skipped}


def _page_path(landmark) -> Path | None:
    """页面文件路径（含目录穿越防护）。

    target_id 直接拼进文件名，必须校验字符集并确认解析后仍落在 PAGES_DIR 内；
    否则把 target_id 设成 "../../runtime/index/qa_chunks" 就能通过故事接口
    读到目录外的 JSON。
    """
    from apps.landmarks.validators import is_valid_target_id

    target_id = str(getattr(landmark, "target_id", "") or "")
    if not is_valid_target_id(target_id):
        return None
    base = PAGES_DIR.resolve()
    candidate = (base / f"{target_id}.json").resolve()
    if candidate.parent != base:
        return None
    return candidate


def page_for(landmark) -> dict | None:
    """读取地标页面文件（按 mtime 缓存）；没有文件/内容非法返回 None。"""
    target = _page_path(landmark)
    if target is None or not target.is_file():
        return None
    mtime = target.stat().st_mtime
    cached = _CACHE.get(str(target))
    if cached and cached.get("mtime") == mtime:
        return cached["data"]
    try:
        data = json.loads(target.read_text(encoding="utf-8"))
    except (ValueError, OSError):
        return None
    if not isinstance(data, dict):
        return None
    _CACHE[str(target)] = {"mtime": mtime, "data": data}
    return data


def story_payload(landmark) -> dict | None:
    """给故事接口用的结构：整体介绍 -> 时间轴 -> 分节材料。"""
    page = page_for(landmark)
    if page is None:
        return None
    return {
        "landmarkId": landmark.id,
        "title": page.get("landmark") or landmark.name,
        "intro": page.get("intro", ""),
        "timeline": page.get("timeline", []),
        "sections": page.get("sections", []),
        "updatedAt": page.get("built_at"),
    }
