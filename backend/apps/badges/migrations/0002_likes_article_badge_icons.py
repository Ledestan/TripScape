"""
行旅识景 TripScape / badges 迁移：图标从 emoji 改为 lucide 名称
创建日期: 2026-11-26

说明:
    1. 老数据里 icon 存的是 emoji，这里按 code 统一换成语义化名称（前端映射到 lucide 图标）。
    2. 字段长度 16 → 32，默认值 🏅 → award。
"""

from django.db import migrations, models

ICONS = {
    "first_footprint": "footprints",
    "footprint_5": "compass",
    "footprint_15": "map-pinned",
    "footprint_26": "map",
    "first_comment": "message-square",
    "comment_10": "messages-square",
    "comment_50": "trophy",
    "first_journal": "notebook-pen",
    "journal_5": "pen-line",
    "journal_20": "book-open",
}


def forwards(apps, schema_editor):
    """把已存在的徽章按 code 换成图标名。"""
    Badge = apps.get_model("badges", "Badge")
    for code, icon in ICONS.items():
        Badge.objects.filter(code=code).update(icon=icon)


def backwards(apps, schema_editor):
    """回滚不还原 emoji：图标名同样可读，保留即可。"""


class Migration(migrations.Migration):

    dependencies = [
        ("badges", "0001_initial"),
    ]

    operations = [
        migrations.RunPython(forwards, backwards),
        migrations.AlterField(
            model_name="badge",
            name="icon",
            field=models.CharField(
                default="award", max_length=32, verbose_name="图标（lucide 名称）"
            ),
        ),
    ]
