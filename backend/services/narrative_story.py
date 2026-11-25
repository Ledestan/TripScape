"""
行旅识景 TripScape / 地标故事读取
创建日期: 2026-11-25

把 stories/ 下「一个地标一篇」的 Markdown 读出来，提供:
    1. story_for_landmark：按地标名找到对应故事并解析 front-matter
    2. 全部故事与地标名的映射（进程内缓存，按目录 mtime 失效）

依赖:
    需求文件: requirements.txt
    依赖库:
        Django==5.2

用法:
    from services import narrative_story
    payload = narrative_story.story_for_landmark(landmark)

注意:
    1. stories/ 由 scripts/build_landmark_stories.py 生成，缺失时返回 None，
       由调用方决定是降级还是报错，不在本模块编造内容。
    2. 文件名带两位序号（01-阿布辛贝神庙.md），地标名是唯一稳定键。
"""

import re
from pathlib import Path

from django.conf import settings

# 进程内缓存：目录 mtime 变化即失效，避免每次请求都扫目录
_CACHE: dict[str, object] = {"mtime": None, "stories": {}}


def stories_dir() -> Path:
    """故事目录固定在仓库根 stories/ 下（BASE_DIR 本身就是仓库根）。"""
    return Path(settings.BASE_DIR) / "stories"


def _parse(text: str) -> dict[str, object]:
    """解析 front-matter 与正文；front-matter 缺失时整篇当归正文。"""
    meta: dict[str, str] = {}
    body = text
    match = re.match(r"^---\n(.*?)\n---\n?(.*)$", text, re.S)
    if match:
        for line in match.group(1).splitlines():
            if ":" in line:
                key, value = line.split(":", 1)
                meta[key.strip()] = value.strip()
        body = match.group(2)
    return {"meta": meta, "markdown": body.strip(), "raw": text}


def _load() -> dict[str, dict[str, object]]:
    """扫描并缓存全部故事；目录不存在时返回空表。"""
    directory = stories_dir()
    if not directory.exists():
        return {}
    mtime = directory.stat().st_mtime
    if _CACHE["mtime"] == mtime:
        return _CACHE["stories"]  # 目录未变，直接用上次解析结果

    stories: dict[str, dict[str, object]] = {}
    # 排序后遍历，保证同一份目录得到同样的映射
    for path in sorted(directory.glob("*.md")):
        parsed = _parse(path.read_text(encoding="utf-8"))
        name = str(parsed["meta"].get("landmark") or path.stem.split("-", 1)[-1])
        parsed["filename"] = path.name
        stories[name] = parsed
    _CACHE["mtime"] = mtime
    _CACHE["stories"] = stories
    return stories


def story_for_landmark(landmark) -> dict[str, object] | None:
    """按地标名取故事；没有对应故事时返回 None。"""
    return _load().get(getattr(landmark, "name", ""))
