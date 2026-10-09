"""行旅识景 TripScape
创建日期：2025-09-01

地标与知识库模型。

分区策略：
- Landmark 为全局数据（scope="global"）
- region 字段标记地标所属区域，供运营分区管理
- UserFavorite 收藏为用户个人数据
"""

from django.conf import settings
from django.db import models


class Landmark(models.Model):
    """世界地标（含经纬度，供 3D 地球光点渲染）。"""

    target_id = models.CharField("唯一标识", max_length=50, unique=True)
    name = models.CharField("中文名称", max_length=100)
    name_en = models.CharField("英文名称", max_length=100, blank=True, default="")
    region = models.CharField(
        "所属区域", max_length=64, blank=True, default="", db_index=True
    )
    country = models.CharField("国家/地区", max_length=64, blank=True, default="")
    lat = models.DecimalField("纬度", max_digits=9, decimal_places=6)
    lon = models.DecimalField("经度", max_digits=9, decimal_places=6)
    intro = models.TextField("百科介绍", blank=True, default="")
    image_url = models.CharField("百科图片", max_length=512, blank=True, default="")
    # 热度：浏览量（看板与搜索排序用）
    view_count = models.PositiveIntegerField("浏览量", default=0, db_index=True)
    is_active = models.BooleanField("是否启用", default=True)

    class Meta:
        db_table = "ts_landmark"
        ordering = ["id"]

    def __str__(self):
        return self.name

    def as_dict(self, with_intro=False):
        data = {
            "id": self.id,
            "target_id": self.target_id,
            "name": self.name,
            "name_en": self.name_en,
            "region": self.region,
            "country": self.country,
            "lat": float(self.lat),
            "lon": float(self.lon),
            "image_url": self.image_url,
            "view_count": self.view_count,
        }
        if with_intro:
            data["intro"] = self.intro
        return data


class RecognitionRecord(models.Model):
    """识别记录（用户个人数据 + 运营统计）。"""

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="用户",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="recognitions",
    )
    landmark = models.ForeignKey(
        Landmark,
        verbose_name="识别出的地标",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="recognitions",
    )
    image_url = models.CharField("识别图片", max_length=512, blank=True, default="")
    confidence = models.FloatField("置信度", default=0.0)
    elapsed_ms = models.IntegerField("耗时(ms)", default=0)
    created_at = models.DateTimeField("时间", auto_now_add=True, db_index=True)

    class Meta:
        db_table = "ts_recognition"
        ordering = ["-created_at"]


class UserFavorite(models.Model):
    """用户收藏地标（用户个人数据）。"""

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="用户",
        on_delete=models.CASCADE,
        related_name="favorite_landmarks",
    )
    landmark = models.ForeignKey(
        Landmark,
        verbose_name="地标",
        on_delete=models.CASCADE,
        related_name="favorited_by",
    )
    created_at = models.DateTimeField("收藏时间", auto_now_add=True)

    class Meta:
        db_table = "ts_favorite"
        unique_together = [("user", "landmark")]
        ordering = ["-created_at"]


class QAContext(models.Model):
    """问答会话上下文（按 session_id 分区，供追问补全主语）。"""

    session_id = models.CharField("会话 ID", max_length=64, db_index=True)
    question = models.TextField("问题")
    answer = models.TextField("答案", blank=True, default="")
    landmark_name = models.CharField(
        "涉及地标名", max_length=100, blank=True, default=""
    )
    created_at = models.DateTimeField("时间", auto_now_add=True)

    class Meta:
        db_table = "ts_qa_context"
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["session_id", "-created_at"])]
