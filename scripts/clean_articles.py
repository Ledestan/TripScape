"""
行旅识景 TripScape / 文章语料清洗
创建日期: 2026-11-26

清掉从百科摘编时残留的排版垃圾，让地标页与问答都读到"人话"，完成:
    1. 维基转换标记 {zh-hans:…;zh-hant:…;}- 只留中文主体
    2. 图片残留 thumb|说明|500px、孤立 px 尺寸、图注行
    3. 空括号、只含标点的括号、以标点开头的残破括号
    4. 悬空量词（"高度为，"这类丢数字的句子）与"，。"

依赖:
    Python: >=3.10
    依赖库: 无

用法（在项目根目录执行）:
    python scripts/clean_articles.py            # 就地清洗 backend/content/articles/*.md
    python scripts/clean_articles.py --dry      # 只报告会改动的行

注意:
    1. 只做删除与替换，不新增任何事实性文字。
    2. 清洗力度刻意保守：只删"明显是模板/图注"的片段，不整段删中文正文——
       第一版曾把 60% 语料删掉，重建索引后只剩 55 个块（原本 144）。
    3. 清洗后要重跑 build_qa_index.py 与 build_landmark_pages.py。
"""

import argparse
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ARTICLES = ROOT / "backend" / "content" / "articles"

RULES = [
    # 维基语言变体：{zh-hans:哈利法;zh-hant:哈里发;}- -> 哈利法
    (re.compile(r"\{zh-(?:hans|hant|cn|tw|sg):([^;{}]*);[^{}]*\}-"), r"\1"),
    # 词内连接标记：额菲-{}-尔士 -> 额菲尔士
    (re.compile(r"-\{\}-"), ""),
    # 图片残留：thumb|说明|500px 与行首 thumb|说明
    (re.compile(r"thumb\|[^|\n]*\|"), ""),
    (re.compile(r"(?m)^\s*thumb\|[^\n]*?(?=[\u4e00-\u9fff])"), ""),
    # 孤立尺寸：500px / 300 px
    (re.compile(r"\b\d{2,4}\s*px\s*"), ""),
    # 图注行：含图片文件名且几乎无中文
    (re.compile(r"(?m)^(?=[^\n]*\.(?:jpg|jpeg|png|svg|webp))(?=[^\u4e00-\u9fff]*$)[^\n]*\n?"), ""),
    # 残留 HTML 标签：<br>、</center>
    (re.compile(r"</?[a-zA-Z][^>]{0,20}>"), ""),
    # 模板与脚注：{{…}}、</ref>
    (re.compile(r"\{\{[^{}]*\}\}"), ""),
    (re.compile(r"</?ref[^>]*>"), ""),
    # 参数尾巴：}} 与括号里的参数（天坛（|abkai mukdehun}}））
    (re.compile(r"\}+"), ""),
    (re.compile(r"（\|[^）]*）"), ""),
    # 残破括号：以标点开头（（；：Körepakupai Vená，其中…））
    (re.compile(r"（\s*[；：，、][^）]*）"), ""),
    (re.compile(r"\(\s*[;:,][^)]*\)"), ""),
    # 空括号与只含标点的括号
    (re.compile(r"（\s*）"), ""),
    (re.compile(r"\(\s*\)"), ""),
    (re.compile(r"（[\s，、；：]*）"), ""),
    # 括号里只剩"语言名 + 标点"（泰姬陵（波斯语、；））
    (re.compile(r"（[^）]{0,6}[；、][^）]{0,4}）"), ""),
    # 悬空量词（丢数字的句子）
    (re.compile(r"(?:高度|长度|宽度|深度|跨度|面积|重量)为，"), ""),
    (re.compile(r"(?:长约|宽约|高约|深约|重约|直径约|海拔约)[，、]"), ""),
    # 破损标点
    (re.compile(r"，。"), "。"),
    (re.compile(r"；。"), "。"),
    (re.compile(r"[（(]\s*[，、]\s*"), "（"),
    # 图注粘连：吉萨金字塔群区地图 吉萨金字塔群是指… -> 去掉开头的图注
    (re.compile(r"(?m)^[^\n，。：；]{1,20}地图\s+"), ""),
    # 译注前缀：百度翻译的中文 罗马竞技场 -> 罗马竞技场
    (re.compile(r"百度翻译的中文\s*"), ""),
    # 行首 infobox 尾巴：只削掉开头 25 字内的非中文噪声
    (re.compile(r"(?m)^[ |}{]{1,25}(?=[\u4e00-\u9fff])"), ""),
    # 合并多余空格
    (re.compile(r"[ \t]{2,}"), " "),
]


def clean(text: str) -> str:
    """按规则表清洗一段文本，返回新文本。"""
    for pattern, replacement in RULES:
        text = pattern.sub(replacement, text)
    return text


def main() -> None:
    """遍历文章，就地清洗并统计。"""
    parser = argparse.ArgumentParser(description="清洗文章语料的排版残留")
    parser.add_argument("--dry", action="store_true", help="只报告，不写回")
    args = parser.parse_args()

    changed_files = 0
    changed_lines = 0
    for path in sorted(ARTICLES.glob("*.md")):
        original = path.read_text(encoding="utf-8")
        cleaned = clean(original)
        if cleaned == original:
            continue
        changed_files += 1
        for before, after in zip(original.splitlines(), cleaned.splitlines()):
            if before != after:
                changed_lines += 1
                if args.dry:
                    print(f"[{path.name}] {before[:80]}")
                    print(f"{' ' * (len(path.name) + 3)}-> {after[:80]}")
        if not args.dry:
            path.write_text(cleaned, encoding="utf-8")

    print(f"{'将改动' if args.dry else '已清洗'}：{changed_files} 个文件，{changed_lines} 行")


if __name__ == "__main__":
    main()
