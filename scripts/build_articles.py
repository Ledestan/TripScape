"""行旅识景 TripScape / 地标文章库工具
创建日期：2025-10-08

地标文章库（scripts/db/articles/*.md）的维护工具，完成:
    1. 校验数据库中每个启用地标都有对应文章文件
    2. 为缺失文章的地标生成底稿骨架（概述取 Landmark.intro，章节留空待补）

文章是问答管线的唯一知识源（知识库问答对表已删除）；
新增地标后运行本脚本补文章骨架，人工充实内容后重建问答索引。

依赖:
    Python: >=3.10
    需求文件: requirements.txt
    依赖库: 无额外依赖

用法（在项目根目录执行）:
    python scripts/build_articles.py              # 只补缺失的文章
    python scripts/build_articles.py --overwrite  # 覆盖重建全部骨架（慎用，会丢弃人工润色）

可选参数:
    --outdir <目录>    文章目录，默认 scripts/db/articles
    --overwrite        覆盖已存在的文章

输出:
    scripts/db/articles/<target_id>.md    每地标一篇章节式文章

注意:
    1. --overwrite 会覆盖人工润色内容，仅初始建库时使用。
    2. 文章增改后需运行 scripts/build_qa_index.py 重建问答索引。
"""

import argparse
import sys
import time
from pathlib import Path

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "backend"))

import os

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

import django

django.setup()

# 文章章节骨架（人工按此结构充实）
SECTION_SKELETON = ["基本参数", "历史沿革", "地理位置", "参观信息"]


class ArticleRenderer:
    """渲染地标文章骨架（概述取地标 intro，章节留待人工充实）。"""

    def render(self, lm) -> str:
        md = (
            f"---\n"
            f"target_id: {lm.target_id}\n"
            f"name: {lm.name}\n"
            f"region: {lm.region}\n"
            f"country: {lm.country}\n"
            f"updated: {time.strftime('%Y-%m-%d')}\n"
            f"---\n\n"
            f"# {lm.name}\n\n## 概述\n\n{lm.intro or '（待补充）'}\n"
        )
        for sec in SECTION_SKELETON:
            md += f"\n## {sec}\n\n（待补充）\n"
        return md


def _parse_args(argv=None):
    parser = argparse.ArgumentParser(
        prog="python scripts/build_articles.py",
        description="地标文章库维护工具（补缺骨架，幂等）。",
        epilog="示例：\n  python scripts/build_articles.py\n  python scripts/build_articles.py --overwrite\n",
    )
    parser.add_argument("--outdir", default=str(ROOT / "scripts" / "db" / "articles"), help="文章目录")
    parser.add_argument("--overwrite", action="store_true", help="覆盖已存在的文章（慎用）")
    return parser.parse_args(argv)


def main(argv=None):
    overall_start = time.time()
    args = _parse_args(argv)

    from apps.landmarks.models import Landmark

    outdir = Path(args.outdir)
    outdir.mkdir(parents=True, exist_ok=True)

    renderer = ArticleRenderer()
    created = skipped = missing = 0
    for lm in Landmark.objects.order_by("id"):
        out = outdir / f"{lm.target_id}.md"
        if out.exists() and not args.overwrite:
            skipped += 1
            continue
        out.write_text(renderer.render(lm), encoding="utf-8")
        created += 1
        if lm.target_id:
            missing += 0  # 计数占位

    # 无文章的地标（不应出现，列出提醒）
    for lm in Landmark.objects.filter(is_active=True):
        if not (outdir / f"{lm.target_id}.md").exists():
            print(f"  缺文章：{lm.name}（{lm.target_id}）")

    print(f"\n文章处理完成：新建 {created}，已存在跳过 {skipped}，目录 {outdir}")
    print(f"[耗时] {time.time() - overall_start:.2f} 秒")
    print("提示：文章为问答唯一知识源，增改后请运行 scripts/build_qa_index.py")


if __name__ == "__main__":
    main()
