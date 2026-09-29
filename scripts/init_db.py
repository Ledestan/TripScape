"""
模块名称：数据库初始化脚本

从 scripts/db/ 下的 SQL 文件重建 SQLite 数据库。

用法（从项目根目录执行）：
    python scripts/init_db.py
    python scripts/init_db.py --force-rebuild   # 删掉旧库重新建
"""

import argparse
import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.core.config import DB_PATH

SCRIPT_DIR = Path(__file__).resolve().parent
SQL_DIR = SCRIPT_DIR / "db"

# SQL 执行顺序
SQL_FILES = [
    "init_sqlite.sql",  # 建表
    "heritage_items.sql",  # 填地标数据
    "knowledge_base.sql",  # 填知识库数据
]


def init_database(force_rebuild=False):
    """
    执行 SQL 脚本，重建数据库。

    参数：
        force_rebuild : bool
            是否先删除已有数据库
    """
    if force_rebuild and DB_PATH.exists():
        DB_PATH.unlink()
        print(f"已删除旧数据库：{DB_PATH}")

    DB_PATH.parent.mkdir(parents=True, exist_ok=True)

    conn = sqlite3.connect(str(DB_PATH))
    try:
        for filename in SQL_FILES:
            sql_path = SQL_DIR / filename
            if not sql_path.exists():
                raise FileNotFoundError(f"SQL 文件不存在：{sql_path}")

            print(f"执行：{filename}")
            with open(sql_path, "r", encoding="utf-8") as f:
                sql = f.read()
            conn.executescript(sql)
        conn.commit()
        print(f"数据库初始化完成：{DB_PATH}")
    finally:
        conn.close()


def _parse_args():
    parser = argparse.ArgumentParser(
        prog="python scripts/init_db.py",
        description="从 SQL 文件重建 SQLite 数据库。",
    )
    parser.add_argument(
        "--force-rebuild",
        action="store_true",
        help="先删除已有数据库再重建",
    )
    return parser.parse_args()


if __name__ == "__main__":
    args = _parse_args()
    init_database(force_rebuild=args.force_rebuild)
