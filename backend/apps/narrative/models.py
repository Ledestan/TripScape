"""
行旅识景 TripScape / 叙事数据模型
创建日期: 2025-11-24

叙事层的四张表（2.0 本体，无特性开关），提供:
    1. NarrativeCard：叙事卡片（识别成功后的结构化对象，只读持久化）
    2. JournalCard：卡片收进手记（用户 × 卡片唯一）

依赖:
    需求文件: requirements.txt
    依赖库:
        Django==5.2

用法:
    from apps.narrative.models import NarrativeCard, JournalCard

注意:
    1. 卡片图片只存 URL 引用，不复制文件。
    2. 碎片不向使用者暴露投递者身份，匿名性由 service 层序列化保证。
"""

from apps.landmarks.models import Landmark
from django.conf import settings
from django.db import models


class NarrativeCard(models.Model):
    """叙事卡片：一次地标识别的结构化结果（SPEC §2 S2）。

    字段与 SPEC 固定字段集一一对应：
        id              -> self.id
        landmarkId      -> landmark_id
        photo           -> photo（原图 URL 引用）
        title           -> title
        geo             -> geo（lat/lon/place/country/region）
        timeFragments[] -> time_fragments（非空）
        ragSnippets[]   -> rag_snippets（非空）
        confidence      -> confidence（0–1）
        source          -> source（来源标签）
    """

    landmark = models.ForeignKey(
        Landmark,
        verbose_name="地标",
        on_delete=models.PROTECT,
        related_name="narrative_cards",
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="识别者",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="narrative_cards",
    )
    photo = models.CharField(
        "照片 URL（引用，不复制文件）", max_length=512, blank=True, default=""
    )
    title = models.CharField("卡片标题", max_length=128)
    geo = models.JSONField("地理坐标与归属", default=dict, blank=True)
    time_fragments = models.JSONField("时间碎片", default=list, blank=True)
    rag_snippets = models.JSONField("检索片段", default=list, blank=True)
    confidence = models.FloatField("识别置信度", default=0.0)
    source = models.CharField("来源标签", max_length=32, default="retrieval")
    created_at = models.DateTimeField("创建时间", auto_now_add=True, db_index=True)

    class Meta:
        db_table = "ts_narrative_card"
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["landmark", "-created_at"])]

    def __str__(self):
        return f"card:{self.id}·{self.title}"

    def as_card(self):
        """序列化为 SPEC §2 S2 的固定字段集（camelCase 与规格一致）。"""
        return {
            "id": self.id,
            "landmarkId": self.landmark_id,
            "photo": self.photo,
            "title": self.title,
            "geo": self.geo or {},
            "timeFragments": self.time_fragments or [],
            "ragSnippets": self.rag_snippets or [],
            "confidence": float(self.confidence),
            "source": self.source,
            "createdAt": self.created_at.isoformat(),
        }


class JournalCard(models.Model):
    """手账中的叙事卡片（S1）：只读，不可编辑（保留原始叙事快照）。"""

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="手账归属用户",
        on_delete=models.CASCADE,
        related_name="narrative_journal_cards",
    )
    card = models.ForeignKey(
        NarrativeCard,
        verbose_name="叙事卡片",
        on_delete=models.CASCADE,
        related_name="journal_entries",
    )
    added_at = models.DateTimeField("加入时间", auto_now_add=True, db_index=True)

    class Meta:
        db_table = "ts_narrative_journal_card"
        unique_together = [("user", "card")]
        ordering = ["-added_at"]

    def __str__(self):
        return f"{self.user_id}·card:{self.card_id}"
