"""
行旅识景 TripScape / 地标故事预置命令
创建日期: 2026-11-25

把文章语料重建为地标故事并写入 ts_landmark_story，完成:
    1. 触发 services.narrative_story.refresh_stories（幂等 upsert）
    2. 打印新增/更新/跳过数量，便于确认语料覆盖情况

依赖:
    需求文件: requirements.txt
    依赖库:
        Django==5.2

用法（在项目根目录执行）:
    python backend/manage.py seed_stories

输出:
    终端统计：新增 N 篇 / 更新 N 篇 / 跳过 N 篇

注意:
    1. 需要先运行 scripts/build_qa_index.py 生成 runtime/index/qa_chunks.json。
    2. 重复执行安全：同一地标只会更新，不会产生重复记录。
"""

from django.core.management.base import BaseCommand

from services import narrative_story


class Command(BaseCommand):
    """重建并写入地标故事（幂等）。"""

    help = "把文章语料重建为地标故事（ts_landmark_story），可重复执行"

    def add_arguments(self, parser):
        """提供 --verbose 查看逐条写入日志。"""
        parser.add_argument("--verbose", action="store_true", help="打印每个地标的写入情况")

    def handle(self, *args, **options):
        """执行重建并输出统计。"""
        try:
            stats = narrative_story.refresh_stories(verbose=options["verbose"])
        except FileNotFoundError as exc:
            self.stderr.write(self.style.ERROR(str(exc)))
            return
        self.stdout.write(
            self.style.SUCCESS(
                f"地标故事已重建：新增 {stats['created']} 篇 / 更新 {stats['updated']} 篇"
                f" / 跳过 {stats['skipped']} 篇"
            )
        )
