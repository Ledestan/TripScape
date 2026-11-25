"""
行旅识景 TripScape / 叙事数据模型
创建日期: 2025-11-24

叙事层的四张表（2.0 本体，无特性开关），提供:
    1. NarrativeCard：叙事卡片（识别成功后的结构化对象，只读持久化）
    2. JournalCard：卡片收进手记（用户 × 卡片唯一）
    3. NarrativeFragment：匿名留在原地的叙事碎片
    4. FragmentPickup：单次拾取记录（碎片 × 用户唯一）

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

from django.conf import settings
from django.db import models

from apps.landmarks.models import Landmark


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
    photo = models.CharField("照片 URL（引用，不复制文件）", max_length=512, blank=True, default="")
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


class NarrativeFragment(models.Model):
    """叙事碎片（S3）：某用户把一张手账卡片匿名投递到某地标。

    匿名性：投递者只用于限额统计，不进入任何响应体（service 层负责剥离）。
    """

    card = models.ForeignKey(
        NarrativeCard,
        verbose_name="来源卡片",
        on_delete=models.CASCADE,
        related_name="fragments",
    )
    landmark = models.ForeignKey(
        Landmark,
        verbose_name="投递地标",
        on_delete=models.CASCADE,
        related_name="narrative_fragments",
    )
    delivered_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="投递者（仅用于限额，对外匿名）",
        on_delete=models.CASCADE,
        related_name="delivered_fragments",
    )
    created_at = models.DateTimeField("投递时间", auto_now_add=True, db_index=True)

    class Meta:
        db_table = "ts_narrative_fragment"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["landmark", "-created_at"]),
            models.Index(fields=["delivered_by", "landmark"]),
        ]

    def __str__(self):
        return f"fragment:{self.id}@{self.landmark_id}"


class FragmentPickup(models.Model):
    """碎片拾取记录（S3）：同一碎片对同一用户只能拾取一次。"""

    fragment = models.ForeignKey(
        NarrativeFragment,
        verbose_name="碎片",
        on_delete=models.CASCADE,
        related_name="pickups",
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="拾取者",
        on_delete=models.CASCADE,
        related_name="fragment_pickups",
    )
    picked_at = models.DateTimeField("拾取时间", auto_now_add=True)

    class Meta:
        db_table = "ts_narrative_fragment_pickup"
        unique_together = [("fragment", "user")]
        ordering = ["-picked_at"]

    def __str__(self):
        return f"pickup:{self.fragment_id}->{self.user_id}"


class LandmarkStory(models.Model):
    """地标故事（预设内容）：整体介绍 + 时间轴 + 分节材料，随种子数据一次写入。

    与"卡片"不同，这张表是**人工预设的长期内容**，不随用户操作变化；
    前端地标档案直接读它，不再每次请求去磁盘找 Markdown 文件。
    """

    landmark = models.OneToOneField(
        "landmarks.Landmark",
        verbose_name="地标",
        on_delete=models.CASCADE,
        related_name="story",
    )
    intro = models.TextField("整体介绍", help_text="摘编自文章库的综合介绍段落")
    timeline = models.JSONField(
        "时间轴",
        default=list,
        help_text='[{"year": 1889, "text": "..."}]，年份缺失时为 null',
    )
    sections = models.JSONField(
        "分节材料",
        default=list,
        help_text='[{"heading": "站在这里", "items": ["..."]}]',
    )
    source = models.CharField("来源", max_length=128, default="")
    updated_at = models.DateTimeField("更新时间", auto_now=True)

    class Meta:
        db_table = "ts_landmark_story"
        ordering = ["landmark_id"]

    def as_payload(self) -> dict:
        """对外结构：整体介绍 -> 时间轴 -> 分节材料（顺序即阅读顺序）。"""
        return {
            "landmarkId": self.landmark_id,
            "title": self.landmark.name,
            "intro": self.intro,
            "timeline": self.timeline or [],
            "sections": self.sections or [],
            "source": self.source,
            "updatedAt": self.updated_at.isoformat() if self.updated_at else None,
        }

    def __str__(self):
        return f"story:{self.landmark_id}"
