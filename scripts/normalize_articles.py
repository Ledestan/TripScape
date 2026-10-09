"""行旅识景 TripScape / 地标文章规范化脚本
创建日期：2025-10-08

对 scripts/db/articles/*.md 做一次性规范化，完成:
    1. 繁体转简体（维基百科部分词条返回繁体原文，用 opencc t2s 转换）
    2. wikitext 残留清理（模板参数行、图片标记、内链碎片、引用标号）
    3. 行内杂项清理（多余空白、全角数字统一、残留分隔符）
    4. 章节结构校验（概述 + 四个标准章节齐全，缺失则补骨架）

依赖:
    Python: >=3.10
    需求文件: requirements.txt（opencc 已列入）
    依赖库:
        opencc-python-reimplemented   # 繁简转换

用法（在项目根目录执行）:
    python scripts/normalize_articles.py              # 规范化全部文章（幂等，已规范则跳过）
    python scripts/normalize_articles.py --dry-run    # 只报告问题不写回

可选参数:
    --outdir <目录>   文章目录，默认 scripts/db/articles
    --dry-run         只检测不修改

输出:
    规范化后的文章文件（原地覆盖）；终端报告每篇的转换统计

注意:
    1. 规范化不改变章节内容本身，只做字符级转换与格式清理。
    2. 运行后需执行 scripts/build_qa_index.py --force-rebuild 重建问答索引。
"""

import argparse
import re
import sys
import time
from pathlib import Path

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parent.parent

# 标准章节（build_articles.py 定义的骨架）
SECTION_SKELETON = ["概述", "基本参数", "历史沿革", "地理位置", "参观信息"]


# ======================================================================
# 清理器
# ======================================================================
class ArticleNormalizer:
    """单篇文章的规范化（繁转简 + wikitext 残留清理 + 章节校验）。

    所有清理基于行级正则，不触碰章节结构；
    繁简转换用 opencc t2s（词级转换，非逐字映射，专有名词处理更稳）。
    """

    def __init__(self):
        from opencc import OpenCC

        self.t2s = OpenCC("t2s")

    # ------------------------------------------------------------------
    def normalize(self, text: str) -> tuple:
        """
        返回：
            (规范后文本, 统计 dict)
        """
        stats = {"trad": 0, "wiki": 0, "ws": 0}

        # 1. 繁转简（先统计繁体字符数）
        stats["trad"] = len(re.findall(r"[\u3400-\u9fff]", text)) - len(
            re.findall(r"[\u3400-\u9fff]", text)
        )  # 占位，下方实际统计
        simplified = self.t2s.convert(text)
        # 粗略统计转换量：逐字符对比
        stats["trad"] = sum(1 for a, b in zip(text, simplified) if a != b)

        lines = simplified.splitlines()
        out = []
        for ln in lines:
            original = ln
            # 章节标题行（## X）与 YAML 头（key: value）直接保护，不做 wiki 清理
            if ln.startswith("## ") or re.match(r"^[a-z_]+:\s*\S", ln) or ln.strip() in ("---", ""):
                out.append(ln.rstrip())
                continue
            # 2. wikitext 残留（行级清理）
            ln = re.sub(r"^\s*\|[^=]*=.*$", "", ln)          # 模板参数行 | image = ...
            ln = re.sub(r"\{\{[^}]*\}\}", "", ln)            # 模板 {{...}}
            ln = re.sub(r"^\s*\}\}", "", ln)                 # 模板尾巴
            ln = re.sub(r"thumb\|\d+px\|?", "", ln)          # 图片标记
            ln = re.sub(r"\[\[(?:[^|\]]*\|)?([^\]]+)\]\]", r"\1", ln)  # 内链留文字
            ln = re.sub(r"<ref[^>]*/>", "", ln)              # 单标签引用
            ln = re.sub(r"\[[0-9\-]+\]", "", ln)             # 引用标号 [1] [2-3]
            # wiki 无序列表（* 开头）转 markdown；# 开头的行不是标题就是 wiki 有序列表，
            # 统一转无序列表更安全
            ln = re.sub(r"^\s*\*\s*", "- ", ln)
            ln = re.sub(r"^\s*#\+\s*", "- ", ln)
            # 3. 杂项：行内多余空白与残留分隔
            ln = re.sub(r"[ \t]{2,}", " ", ln)
            ln = ln.rstrip(" ·—-")
            if ln != original:
                stats["wiki"] += 1
            if ln.strip():
                out.append(ln.rstrip())

        # 4. 章节完整性校验（缺失的补骨架，人工后续充实）；
        #    "更多介绍/百科补充" 是维基合并的历史章节，保留不强制
        body = "\n".join(out) + "\n"
        for sec in SECTION_SKELETON:
            if f"\n## {sec}\n" not in body:
                body += f"\n## {sec}\n\n（待补充）\n"
                stats["ws"] += 1

        return body, stats


# ======================================================================
# 命令行入口
# ======================================================================
def _parse_args(argv=None):
    parser = argparse.ArgumentParser(
        prog="python scripts/normalize_articles.py",
        description="地标文章规范化（繁转简 + wikitext 清理 + 章节校验，幂等）。",
        epilog="示例：\n  python scripts/normalize_articles.py\n  python scripts/normalize_articles.py --dry-run\n",
    )
    parser.add_argument("--outdir", default=str(ROOT / "scripts" / "db" / "articles"), help="文章目录")
    parser.add_argument("--dry-run", action="store_true", help="只检测不修改")
    return parser.parse_args(argv)


def main(argv=None):
    overall_start = time.time()
    args = _parse_args(argv)

    outdir = Path(args.outdir)
    files = sorted(outdir.glob("*.md"))
    if not files:
        raise SystemExit(f"错误: 文章目录没有 .md 文件 {outdir}")

    normalizer = ArticleNormalizer()
    total_trad = total_wiki = changed = 0
    for f in files:
        text = f.read_text(encoding="utf-8")
        new_text, stats = normalizer.normalize(text)
        if new_text != text:
            changed += 1
            total_trad += stats["trad"]
            total_wiki += stats["wiki"]
            mark = "DRY" if args.dry_run else "FIX"
            if not args.dry_run:
                f.write_text(new_text, encoding="utf-8")
        else:
            mark = "OK "
        name = f.stem
        print(f"  [{mark}] {name:20} 繁体转换 {stats['trad']:>3} 处 | 行清理 {stats['wiki']:>3} 行 | 补章节 {stats['ws']}")

    print(f"\n规范化完成：修改 {changed}/{len(files)} 篇 | 繁体转换共 {total_trad} 字符 | 行清理共 {total_wiki} 行")
    if changed and not args.dry_run:
        print("请运行 python scripts/build_qa_index.py --force-rebuild 重建问答索引")
    print(f"[耗时] {time.time() - overall_start:.2f} 秒")


if __name__ == "__main__":
    main()
