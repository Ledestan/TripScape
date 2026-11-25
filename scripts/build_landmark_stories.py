"""
行旅识景 TripScape / 地标故事生成脚本
创建日期: 2026-11-25

把仓库内文章库（runtime/index/qa_chunks.json，Wikipedia 摘编）按地标整理成
「一个地标一篇」的故事文档，完成:
    1. 读取 26 个地标的正文块（概述 / 历史沿革 / 基本参数 / 地理位置 / 参观信息 / 更多介绍）
    2. 按固定结构摘编成 Markdown（开篇、时间的刻度、站在这里、到访之前、出处）
    3. 写出 stories/<序号>-<中文名>.md，供前端故事视图直接读取

依赖:
    Python: >=3.10
    需求文件: requirements.txt
    依赖库:
        Django==5.2
    环境变量:
        DB_ENGINE    数据库引擎，默认 sqlite（MySQL 可达时用 MySQL）
        RUNTIME_DIR  运行产物目录，默认 ./runtime

用法（在项目根目录执行）:
    python scripts/build_landmark_stories.py [选项]

可选参数:
    --check    只比对现有 stories/ 与最新生成结果，不写文件
    --index    指文章库路径，默认 runtime/index/qa_chunks.json

示例:
    python scripts/build_landmark_stories.py
    python scripts/build_landmark_stories.py --check

输出:
    stories/*.md（26 篇）；终端打印每篇的段落数与耗时

注意:
    1. 只摘编文章库原句，不新增事实、不改写句意；缺章节时明确留白而不是补写。
    2. 遍历顺序固定（按 target_id 排序），保证同一份数据每次生成完全相同的内容。
    3. 联网百科（百度百科）对脚本请求返回 403，故本脚本只使用仓库内可核对语料。
"""

import argparse
import json
import os
import re
import sys
import time
from pathlib import Path

sys.dont_write_bytecode = True

ROOT = Path(__file__).resolve().parent.parent
STORIES = ROOT / "stories"
DEFAULT_INDEX = ROOT / "runtime" / "index" / "qa_chunks.json"

# 章节优先级：决定故事里的阅读顺序，缺的章节跳过而不是编造
SECTION_ORDER = ["概述", "前言", "更多介绍", "历史沿革", "地理位置", "基本参数", "参观信息", "百科补充"]

# 用来挑「时间的刻度」的年份句：四位年份 + 世纪写法
YEAR_PATTERN = re.compile(r"(\d{3,4})\s*年|(\d{1,2})\s*世纪")


def split_sentences(text: str) -> list[str]:
    """按中文句末标点切句，保留标点；空句丢弃。"""
    parts = re.split(r"(?<=[。！？；])", text.strip())
    return [part.strip() for part in parts if part and part.strip()]


def pick(chunks: list[dict], section: str, limit: int = 2) -> list[str]:
    """取某章节的前若干句（固定顺序，保证可复现）。"""
    sentences: list[str] = []
    for chunk in chunks:
        if chunk.get("section") != section:
            continue
        sentences.extend(split_sentences(chunk.get("text", "")))
        if len(sentences) >= limit:
            break
    return sentences[:limit]


def year_sentences(chunks: list[dict], limit: int = 5) -> list[str]:
    """从所有章节里挑出带年份的句子，作为时间线素材。"""
    found: list[str] = []
    for section in SECTION_ORDER:
        for sentence in pick(chunks, section, limit=20):
            if YEAR_PATTERN.search(sentence) and sentence not in found:
                found.append(sentence)
            if len(found) >= limit:
                return found
    return found


def join(sentences: list[str]) -> str:
    """把句子拼成自然段；句子自带标点，直接相连即可。"""
    return "".join(sentences).strip()


def build_story(landmark: dict, chunks: list[dict]) -> str:
    """按固定结构生成一篇故事（只摘编原句，章节缺失时明确留白）。"""
    name = landmark["name"]
    country = landmark.get("country") or ""
    region = landmark.get("region") or ""

    # 同一句话在开篇与时间线里重复出现会让摘编读起来像机器拼贴，这里全局去重
    seen: set[str] = set()

    def unique(sentences: list[str]) -> list[str]:
        kept: list[str] = []
        for sentence in sentences:
            if sentence and sentence not in seen:
                seen.add(sentence)
                kept.append(sentence)
        return kept

    opening = join(unique(pick(chunks, "概述", 2))) or join(unique(pick(chunks, "前言", 2)))
    more = join(unique(pick(chunks, "更多介绍", 2)))

    years: list[str] = []
    seen_years: set[str] = set()
    for sentence in year_sentences(chunks, 12):
        match = YEAR_PATTERN.search(sentence)
        if not match or sentence in seen:
            continue
        key = match.group(0)
        if key in seen_years:
            continue
        seen_years.add(key)
        seen.add(sentence)
        years.append(sentence)
        if len(years) >= 5:
            break

    place = join(unique(pick(chunks, "地理位置", 1)))
    params = join(unique(pick(chunks, "基本参数", 1)))
    visit = join(unique(pick(chunks, "参观信息", 2)))

    lines: list[str] = []
    lines.append("---")
    lines.append(f"landmark: {name}")
    lines.append(f"target_id: {landmark['target_id']}")
    lines.append(f"country: {country}")
    lines.append(f"region: {region}")
    lines.append(f"lat: {landmark.get('lat')}")
    lines.append(f"lon: {landmark.get('lon')}")
    lines.append("source: 仓库文章库 runtime/index/qa_chunks.json（Wikipedia 摘编）")
    lines.append("---")
    lines.append("")
    lines.append(f"# {name}{('｜' + country) if country else ''}")
    lines.append("")
    if opening:
        lines.append(opening)
        lines.append("")
    lines.append(
        f"这一页只做一件事：把关于{name}的材料按「它是谁、时间怎么走、站在现场看见什么」"
        "三段排好，句子全部来自仓库里的文章摘编。"
    )
    lines.append("")
    if more:
        lines.append(more)
        lines.append("")

    if years:
        lines.append("## 时间的刻度")
        lines.append("")
        for sentence in years:
            lines.append(f"- {sentence}")
        lines.append("")

    if place or params:
        lines.append("## 站在这里")
        lines.append("")
        if place:
            lines.append(place)
            lines.append("")
        if params and params != place:
            lines.append(params)
            lines.append("")

    if visit:
        lines.append("## 到访之前")
        lines.append("")
        lines.append(visit)
        lines.append("")

    used = [s for s in SECTION_ORDER if pick(chunks, s, 1)]
    lines.append("## 出处")
    lines.append("")
    lines.append("本页文字摘自仓库文章库的以下章节，按句挑编，未改写句意：")
    lines.append("")
    for section in used:
        lines.append(f"- {section}")
    lines.append("")
    lines.append("> 文化内容的最终解释权归人：这里只做摘编与排版，不做历史解释。")
    lines.append("")
    return "\n".join(lines)


def load_landmarks() -> list[dict]:
    """从数据库读地标（含坐标与国家），按 id 排序保证输出稳定。"""
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
    os.environ.setdefault("DJANGO_DEPLOY", "dev")
    sys.path.insert(0, str(ROOT / "backend"))
    import django

    django.setup()
    from apps.landmarks.models import Landmark

    rows = []
    for landmark in Landmark.objects.all().order_by("id"):
        rows.append(
            {
                "name": landmark.name,
                "target_id": landmark.target_id,
                "country": landmark.country or "",
                "region": landmark.region or "",
                "lat": landmark.lat,
                "lon": landmark.lon,
            }
        )
    return rows


def group_chunks(index_path: Path) -> dict[str, list[dict]]:
    """按 target_id 归组正文块；文件缺失直接报错并提示处理方法。"""
    if not index_path.exists():
        raise SystemExit(
            f"错误: 文章库不存在 {index_path}；请先运行 python scripts/build_qa_index.py 生成"
        )
    chunks = json.loads(index_path.read_text(encoding="utf-8"))
    grouped: dict[str, list[dict]] = {}
    for chunk in chunks:
        grouped.setdefault(chunk["target_id"], []).append(chunk)
    return grouped


def scan_existing() -> dict[str, str]:
    """读出现有故事文件，用于 --check 比对。"""
    if not STORIES.exists():
        return {}
    return {path.name: path.read_text(encoding="utf-8") for path in sorted(STORIES.glob("*.md"))}


def main() -> None:
    """生成或校验 26 篇地标故事。"""
    parser = argparse.ArgumentParser(
        description="生成每个地标一篇的 Markdown 故事（只摘编文章库原句）",
        epilog="示例: python scripts/build_landmark_stories.py --check",
    )
    parser.add_argument("--check", action="store_true", help="只比对，不写文件")
    parser.add_argument("--index", default=str(DEFAULT_INDEX), help=f"文章库路径，默认 {DEFAULT_INDEX}")
    args = parser.parse_args()

    started = time.time()
    print("========== 读取语料 ==========")
    grouped = group_chunks(Path(args.index))
    landmarks = load_landmarks()
    print(f"地标数: {len(landmarks)}，文章块: {sum(len(v) for v in grouped.values())}")

    STORIES.mkdir(parents=True, exist_ok=True)
    existing = scan_existing()
    written = 0
    stale: list[str] = []

    print("\n========== 生成故事 ==========")
    for order, landmark in enumerate(landmarks, start=1):
        chunks = grouped.get(landmark["target_id"], [])
        story = build_story(landmark, chunks)
        filename = f"{order:02d}-{landmark['name']}.md"
        target = STORIES / filename
        if args.check:
            current = existing.get(filename, "")
            if current != story:
                stale.append(filename)
            continue
        target.write_text(story, encoding="utf-8")
        written += 1
        print(f"[{order}/{len(landmarks)}] {filename} · 章节块 {len(chunks)} 个")

    if args.check:
        if stale:
            print("以下故事与语料不一致：" + "、".join(stale))
            sys.exit("请重新运行本脚本生成最新故事")
        print("全部故事与语料一致")
    else:
        removed = [name for name in existing if name not in {f"{i:02d}-{l['name']}.md" for i, l in enumerate(landmarks, 1)}]
        for name in removed:
            (STORIES / name).unlink()
            print(f"已删除过期故事: {name}")

    print("\n" + "=" * 50)
    print(f"写入 {written} 篇，耗时 {time.time() - started:.2f} 秒")


if __name__ == "__main__":
    main()
