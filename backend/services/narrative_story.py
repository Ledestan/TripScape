"""
行旅识景 TripScape / 地标故事（预设内容）
创建日期: 2026-11-25

把文章库里的地标正文整理成「整体介绍 → 时间轴 → 分节材料」并预置进数据库，提供:
    1. build_payload：从 qa_chunks 语料组装一份故事结构
    2. refresh_stories：把 26 个地标的故事写入 ts_landmark_story（幂等）
    3. story_for_landmark：读取已预置的故事（纯数据库查询，不碰磁盘）

依赖:
    需求文件: requirements.txt
    依赖库:
        Django==5.2

用法:
    from services import narrative_story
    narrative_story.refresh_stories()                  # 种子阶段调用
    payload = narrative_story.story_for_landmark(lm)   # 接口阶段调用

注意:
    1. 内容只摘编文章库原句：不新增史实、不改写句意；年份取不到时写 null。
    2. 遍历前按 target_id 排序，保证同一份语料重复执行得到完全相同的结果。
    3. 缺语料的地标不写空故事，直接跳过并计数，由调用方打印。
"""

import json
import re
from pathlib import Path

from django.conf import settings

# 语料路径与章节阅读顺序（固定，保证可复现）
CORPUS_PATH = Path(settings.BASE_DIR) / "runtime" / "index" / "qa_chunks.json"
SECTION_ORDER = ["概述", "前言", "更多介绍", "历史沿革", "地理位置", "基本参数", "参观信息", "百科补充"]
YEAR_PATTERN = re.compile(r"(\d{3,4})\s*年")
SOURCE_LABEL = "仓库文章库 runtime/index/qa_chunks.json（Wikipedia 摘编）"

# 分节材料的固定小标题：站在现场能看见什么、到访之前要注意什么
SECTION_TITLES = {
    "地理位置": "站在这里",
    "基本参数": "尺度与参数",
    "参观信息": "到访之前",
    "百科补充": "补记",
}


def split_sentences(text: str) -> list[str]:
    """按中文句末标点切句，保留标点；空句丢弃。"""
    parts = re.split(r"(?<=[。！？；])", text.strip())
    return [part.strip() for part in parts if part and part.strip()]


def group_chunks(index_path: Path = CORPUS_PATH) -> dict[str, list[dict]]:
    """按 target_id 归组语料块；语料缺失直接报错并给出处理方法。"""
    if not index_path.exists():
        raise FileNotFoundError(
            f"文章库不存在: {index_path}；请先运行 python scripts/build_qa_index.py"
        )
    chunks = json.loads(index_path.read_text(encoding="utf-8"))
    grouped: dict[str, list[dict]] = {}
    for chunk in chunks:
        grouped.setdefault(chunk["target_id"], []).append(chunk)
    return grouped


def _sentences(chunks: list[dict], section: str, limit: int = 3) -> list[str]:
    """取某章节的前若干句（固定顺序）。"""
    collected: list[str] = []
    for chunk in chunks:
        if chunk.get("section") != section:
            continue
        collected.extend(split_sentences(chunk.get("text", "")))
        if len(collected) >= limit:
            break
    return collected[:limit]


def build_payload(landmark, chunks: list[dict]) -> dict:
    """组装一个地标的故事结构（只摘编原句，跨节去重）。"""
    seen: set[str] = set()

    def unique(sentences: list[str]) -> list[str]:
        kept: list[str] = []
        for sentence in sentences:
            if sentence and sentence not in seen:
                seen.add(sentence)
                kept.append(sentence)
        return kept

    intro_sentences = unique(_sentences(chunks, "概述", 2)) or unique(_sentences(chunks, "前言", 2))
    intro_sentences += unique(_sentences(chunks, "更多介绍", 2))
    intro = "".join(intro_sentences).strip()

    timeline: list[dict] = []
    seen_years: set[int] = set()
    for section in SECTION_ORDER:
        for sentence in _sentences(chunks, section, 20):
            match = YEAR_PATTERN.search(sentence)
            if not match or sentence in seen:
                continue
            year = int(match.group(1))
            if year in seen_years:
                continue
            seen_years.add(year)
            seen.add(sentence)
            timeline.append({"year": year, "text": sentence})
            if len(timeline) >= 5:
                break
        if len(timeline) >= 5:
            break
    timeline.sort(key=lambda item: item["year"])

    sections: list[dict] = []
    for section, heading in SECTION_TITLES.items():
        items = unique(_sentences(chunks, section, 2))
        if items:
            sections.append({"heading": heading, "items": items})

    return {
        "intro": intro,
        "timeline": timeline,
        "sections": sections,
        "source": SOURCE_LABEL,
        "title": getattr(landmark, "name", ""),
    }


def refresh_stories(verbose: bool = False) -> dict:
    """把语料重建成地标故事并写入数据库（幂等，返回统计）。"""
    from apps.landmarks.models import Landmark
    from apps.narrative.models import LandmarkStory

    grouped = group_chunks()
    created = updated = skipped = 0
    # 按 target_id 排序：同一份语料每次执行顺序一致
    for landmark in Landmark.objects.order_by("target_id"):
        chunks = grouped.get(landmark.target_id, [])
        if not chunks:
            skipped += 1
            continue
        payload = build_payload(landmark, chunks)
        _, is_created = LandmarkStory.objects.update_or_create(
            landmark=landmark,
            defaults={
                "intro": payload["intro"],
                "timeline": payload["timeline"],
                "sections": payload["sections"],
                "source": payload["source"],
            },
        )
        if is_created:
            created += 1
        else:
            updated += 1
        if verbose:
            print(f"故事已写入: {landmark.name}（{len(payload['timeline'])} 条时间轴）")

    return {"created": created, "updated": updated, "skipped": skipped}


def story_for_landmark(landmark):
    """读取已预置的故事；没有预置时返回 None（由接口层给 404）。"""
    from apps.narrative.models import LandmarkStory

    return LandmarkStory.objects.filter(landmark=landmark).first()
