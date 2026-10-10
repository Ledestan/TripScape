"""行旅识景 TripScape
创建日期：2025-09-01

数据库初始化命令：迁移 + 地标/知识库/徽章/敏感词/账号种子（幂等）。

数据来源：
    - 地标 26 个：scripts/db/seed_landmarks.sql（target_id/名称/地区/国家/
      经纬度/百科介绍，新增地标只需在该文件追加一行，无需改代码）。
    - 徽章 10 枚：scripts/db/seed_badges.sql。
    - 敏感词基线：scripts/db/seed_sensitive_words.sql（运行期可在后台增删）。
    - 种子账号（admin/demo）：本文件 create_seed_accounts()。

用法：
    python backend/manage.py init_tripscape            # 全量初始化（幂等，可重复执行）
    python backend/manage.py init_tripscape --rebuild  # 清空业务表与用户后重建
"""

import re
from pathlib import Path

from apps.admin_panel.models import SensitiveWord
from apps.badges.models import Badge
from apps.landmarks.models import Landmark
from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.db import connection

BASE_DIR = Path(settings.BASE_DIR)



def _parse_sqlite_values(sql_path: Path):
    """解析 seed_knowledge_base.sql 的 INSERT 语句为行列表。

    该文件采用 sqlite 方言的多行 VALUES 写法（非 MySQL 可直接执行的脚本），
    这里取 VALUES 关键字之后的内容，按 SQL 字面量语法（单引号、'' 转义）切分元组。
    """
    text = sql_path.read_text(encoding="utf-8")
    # 去掉注释行
    lines = [ln for ln in text.splitlines() if not ln.strip().startswith("--")]
    text = "\n".join(lines)
    m = re.search(r"\bVALUES\b", text, re.I)
    if not m:
        return []
    values_part = text[m.end() :]

    rows = []
    buf, in_str = "", False
    row_parts = []
    i = 0
    n = len(values_part)
    while i < n:
        ch = values_part[i]
        if ch == "'" and not in_str:
            in_str = True
            buf += ch
            i += 1
            continue
        if ch == "'" and in_str:
            if i + 1 < n and values_part[i + 1] == "'":
                buf += "''"
                i += 2
                continue
            in_str = False
            buf += ch
            i += 1
            continue
        if in_str:
            buf += ch
            i += 1
            continue
        # 不在字符串内
        if ch == ",":
            row_parts.append(buf.strip())
            buf = ""
            i += 1
            continue
        if ch == "(":
            row_parts, buf = [], ""
            i += 1
            continue
        if ch == ")":
            row_parts.append(buf.strip())
            buf = ""
            rows.append([_literal(p) for p in row_parts if p != ""])
            row_parts = []
            i += 1
            continue
        buf += ch
        i += 1
    return rows


def _literal(p: str):
    """SQL 字面量 -> Python 值。"""
    p = p.strip()
    if p.startswith("'") and p.endswith("'") and len(p) >= 2:
        return p[1:-1].replace("''", "'")
    if p.upper() == "NULL":
        return None
    try:
        return int(p)
    except ValueError:
        return p


class Command(BaseCommand):
    help = "迁移 + 导入 legacy 数据 + 种子（幂等）"

    def add_arguments(self, parser):
        parser.add_argument("--rebuild", action="store_true", help="清空业务表后重建")

    def handle(self, *args, **options):
        from django.core.management import call_command

        rebuild = options["rebuild"]

        self.stdout.write("1) 执行 Django migrations ...")
        call_command("migrate", interactive=False, verbosity=0)

        if rebuild:
            self.stdout.write("   清空业务表 ...")
            models = [Landmark, Badge, SensitiveWord]
            from apps.admin_panel.models import AuditLog
            from apps.badges.models import UserBadge
            from apps.comments.models import Comment, CommentReport
            from apps.comments.models_like import Like
            from apps.journals.models import Footprint, Journal, JournalImage
            from apps.landmarks.models import (QAContext, RecognitionRecord,
                                               UserFavorite)
            from apps.notifications.models import Notification
            from apps.shares.models import ShareLink

            for model in [
                AuditLog,
                ShareLink,
                Notification,
                UserBadge,
                CommentReport,
                Comment,
                Like,
                JournalImage,
                Journal,
                Footprint,
                RecognitionRecord,
                UserFavorite,
                QAContext,
                Landmark,
            ]:
                model.objects.all().delete()
            SensitiveWord.objects.all().delete()
            Badge.objects.all().delete()
            # 用户表：清掉所有旧账号（种子账号在后续步骤重建，保证干净环境）
            from apps.accounts.models import User

            User.objects.all().delete()

        # ---------------- 地标 ----------------
        # 数据来自 scripts/db/seed_landmarks.sql（新增地标在文件里加一行即可）。
        self.stdout.write("2) 导入地标（seed_landmarks.sql）...")
        lm_rows = _parse_sqlite_values(
            BASE_DIR / "scripts" / "db" / "seed_landmarks.sql"
        )
        created_lms = 0
        for row in lm_rows:
            # 行结构：(target_id, name, name_en, region, country, lat, lon, intro)
            if len(row) < 8:
                continue
            target_id, name, name_en, region, country, lat, lon, intro = row[:8]
            _, created = Landmark.objects.update_or_create(
                target_id=target_id,
                defaults={
                    "name": name,
                    "name_en": name_en or target_id,
                    "region": region,
                    "country": country,
                    "lat": lat,
                    "lon": lon,
                    "intro": intro,
                    "image_url": f"/lmimg/{target_id}.jpg",
                },
            )
            created_lms += int(created)
        self.stdout.write(
            f"   地标：新增 {created_lms}，共 {Landmark.objects.count()} 条"
        )


        # ---------------- 徽章种子 ----------------
        # 数据来自 scripts/db/seed_badges.sql（新增徽章在文件里加一行即可）。
        self.stdout.write("4) 写入徽章种子 ...")
        for code, name, category, threshold, icon, desc in _parse_sqlite_values(
            BASE_DIR / "scripts" / "db" / "seed_badges.sql"
        ):
            Badge.objects.update_or_create(
                code=code,
                defaults={
                    "name": name,
                    "category": category,
                    "threshold": threshold,
                    "icon": icon,
                    "description": desc,
                    "is_active": True,
                },
            )

        # ---------------- 敏感词种子 ----------------
        # 基线词表来自 scripts/db/seed_sensitive_words.sql，运行期可在后台增删。
        self.stdout.write("5) 写入敏感词种子 ...")
        for (word,) in _parse_sqlite_values(
            BASE_DIR / "scripts" / "db" / "seed_sensitive_words.sql"
        ):
            SensitiveWord.objects.get_or_create(word=word)

        # ---------------- 管理员账号 ----------------
        self.stdout.write("6) 创建种子账号 ...")
        User = get_user_model()
        if not User.objects.filter(username="admin").exists():
            User.objects.create_superuser(
                username="admin",
                password="admin123456",
                nickname="全局管理员",
                role="admin",
            )
            self.stdout.write("   全局管理员 admin / admin123456")
        if not User.objects.filter(username="demo").exists():
            User.objects.create_user(
                username="demo",
                password="demo123456",
                nickname="演示用户",
                role="user",
            )
            self.stdout.write("   演示用户 demo / demo123456")

        # ---------------- 百科图片 ----------------
        self.stdout.write("7) 挑选地标百科图片（data/valid 中取样）...")
        picked = 0
        valid_dir = BASE_DIR / "data" / "valid"
        if valid_dir.exists():
            import shutil

            static_dir = BASE_DIR / "frontend" / "public" / "landmarks"
            static_dir.mkdir(parents=True, exist_ok=True)
            for lm in Landmark.objects.exclude(target_id=""):
                src_dir = valid_dir / lm.target_id
                if not src_dir.exists():
                    continue
                images = sorted(
                    list(src_dir.glob("*.jpg")) + list(src_dir.glob("*.jpeg"))
                )
                if not images:
                    continue
                # 优先取中间一张作为百科图（避开特写/糊图）
                src = images[len(images) // 2]
                dst = static_dir / f"{lm.target_id}.jpg"
                if not dst.exists():
                    shutil.copyfile(src, dst)
                lm.image_url = f"/lmimg/{lm.target_id}.jpg"
                lm.save(update_fields=["image_url"])
                picked += 1
        self.stdout.write(f"   已为 {picked} 个地标挑选百科图片")

        self.stdout.write(self.style.SUCCESS("init_tripscape 完成。"))
