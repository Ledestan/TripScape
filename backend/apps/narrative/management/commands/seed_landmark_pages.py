"""
行旅识景 TripScape / 地标页面预置命令

把文章语料一次性生成为地标页面文件（backend/content/landmarks/*.json），完成:
    1. 触发 services.landmark_pages.build_pages（幂等覆盖）
    2. 打印生成/跳过数量，便于确认语料覆盖情况

依赖:
    需求文件: requirements.txt
    依赖库:
        Django==5.2

用法（在项目根目录执行）:
    python backend/manage.py seed_landmark_pages

输出:
    终端统计：生成 N 篇 / 跳过 N 篇

注意:
    1. 需要先运行 scripts/build_qa_index.py 生成 runtime/index/qa_chunks.json。
    2. 生成的是纯文本 JSON，打开地标时直接读文件，不会再触发分词。
"""

import sys

sys.dont_write_bytecode = True

from django.core.management.base import BaseCommand
from services import landmark_pages


class Command(BaseCommand):
    """生成地标页面文件（幂等）。"""

    help = (
        "把文章语料生成为地标页面文件（backend/content/landmarks/*.json），可重复执行"
    )

    def add_arguments(self, parser):
        """提供 --verbose 查看逐条生成日志。"""
        parser.add_argument(
            "--verbose", action="store_true", help="打印每个地标的生成情况"
        )

    def handle(self, *args, **options):
        """执行生成并输出统计。"""
        try:
            stats = landmark_pages.build_pages(verbose=options["verbose"])
        except FileNotFoundError as exc:
            self.stderr.write(self.style.ERROR(str(exc)))
            return
        self.stdout.write(
            self.style.SUCCESS(
                f"地标页面已生成：{stats['written']} 篇"
                f" / 未变化 {stats['unchanged']} 篇 / 跳过 {stats['skipped']} 篇"
            )
        )
