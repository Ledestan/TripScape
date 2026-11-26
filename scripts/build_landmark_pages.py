"""
行旅识景 TripScape / 地标页面生成脚本
创建日期: 2026-11-25

把文章库内容一次性生成为「一个地标一个文件」的页面数据，完成:
    1. 读取 runtime/index/qa_chunks.json 与地标表
    2. 生成 content/landmarks/<target_id>.json（整体介绍 / 时间轴 / 分节材料 / 卡片材料）
    3. 打印生成与跳过数量

依赖:
    Python: >=3.10
    需求文件: requirements.txt
    依赖库:
        Django==5.2
    环境变量:
        DB_ENGINE    数据库引擎，默认 sqlite（MySQL 可达时用 MySQL）

用法（在项目根目录执行）:
    python scripts/build_landmark_pages.py [选项]

可选参数:
    --verbose    打印每个地标的生成情况
    --check      只校验文件是否存在，不重新生成

示例:
    python scripts/build_landmark_pages.py
    python scripts/build_landmark_pages.py --check

输出:
    content/landmarks/*.json（26 个）与终端统计

注意:
    1. 只摘编语料原句：不新增史实、不改写句意；年份取不到写 null。
    2. 页面文件是缓存：缺失时接口返回 404 并提示重新生成，不会现场分词。
    3. jieba / 向量检索只服务问答（/api/qa），与地标页无关。
"""

import argparse
import os
import sys
from pathlib import Path

sys.dont_write_bytecode = True

ROOT = Path(__file__).resolve().parent.parent


def load_django() -> None:
    """初始化 Django（脚本需要读地标表）。"""
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
    os.environ.setdefault("DJANGO_DEPLOY", "dev")
    sys.path.insert(0, str(ROOT / "backend"))
    import django

    django.setup()


def main() -> None:
    """按参数生成或校验页面文件。"""
    parser = argparse.ArgumentParser(
        description="生成地标页面文件（整体介绍 / 时间轴 / 分节材料）",
        epilog="示例: python scripts/build_landmark_pages.py --check",
    )
    parser.add_argument("--verbose", action="store_true", help="打印每个地标的生成情况")
    parser.add_argument("--check", action="store_true", help="只检查文件是否齐全")
    args = parser.parse_args()

    load_django()
    from services import landmark_pages

    if args.check:
        files = (
            sorted(landmark_pages.PAGES_DIR.glob("*.json"))
            if landmark_pages.PAGES_DIR.exists()
            else []
        )
        print(f"页面文件数量: {len(files)}")
        if not files:
            sys.exit(
                "错误: 还没有页面文件，请运行 python scripts/build_landmark_pages.py"
            )
        return

    try:
        stats = landmark_pages.build_pages(verbose=args.verbose)
    except FileNotFoundError as exc:
        sys.exit(f"错误: {exc}")
    print(
        f"页面已生成: {stats['written']} 篇"
        f" / 未变化 {stats['unchanged']} 篇 / 跳过 {stats['skipped']} 篇"
    )
    print(f"输出目录: {landmark_pages.PAGES_DIR}")


if __name__ == "__main__":
    main()
