"""
行旅识景 TripScape / comments 0005 拉平多层回复
创建日期: 2026-11-26

把历史上"回复的回复"（parent.parent 不为空）改成两级：
    reply_to = 原来的 parent（被回复的人）
    parent   = 顶层评论

注意:
    1. 只改 parent 链，不动内容与时间。
    2. 反向迁移无法还原 reply_to 的原始层级，最多把 reply_to 清空。
"""

from django.db import migrations


def flatten(apps, schema_editor):
    Comment = apps.get_model("comments", "Comment")
    pending = Comment.objects.exclude(parent__isnull=True).filter(
        parent__parent__isnull=False
    )
    for comment in pending.select_related("parent"):
        comment.reply_to_id = comment.parent_id
        comment.parent_id = comment.parent.parent_id
        comment.save(update_fields=["reply_to", "parent"])


def unflatten(apps, schema_editor):
    Comment = apps.get_model("comments", "Comment")
    Comment.objects.exclude(reply_to__isnull=True).update(reply_to=None)


class Migration(migrations.Migration):

    dependencies = [
        ("comments", "0004_comment_reply_to"),
    ]

    operations = [
        migrations.RunPython(flatten, unflatten),
    ]
