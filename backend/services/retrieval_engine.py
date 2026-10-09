"""行旅识景 TripScape / 检索式识别引擎
创建日期：2025-10-08

以图检索替代分类：DINOv2 全局检索，完成:
    1. DINOv2 ViT-S/14 提取查询图全局特征（384 维）
    2. FAISS 索引检索 top-k 候选注册图
    3. 按地标去重取最优候选，输出地标名与置信度

依赖:
    Python: >=3.10
    依赖库:
        torch                        # DINOv2 推理（CPU 版即可）
        faiss-cpu>=1.14              # 向量检索（本地索引文件）
    权重（首次自动下载，之后走本地缓存）:
        DINOv2 vits14_reg  ~84MB   torch.hub: facebookresearch/dinov2

用法:
    from services.retrieval_engine import get_engine
    engine = get_engine()                  # 单例；索引不存在时返回 None
    results = engine.predict(image_bytes)  # [(target_id, 置信度), ...]

注意:
    1. 索引产物由 scripts/register_landmarks.py 构建，位于 runtime/index/；
       引擎只读不写，重建索引请运行该脚本。
    2. 新增地标 = 提供注册图后重跑注册脚本，无需训练任何模型。
"""

import json
import logging
import time
from pathlib import Path

import numpy as np

logger = logging.getLogger(__name__)

from django.conf import settings

# ======================================================================
# 特征提取
# ======================================================================
class DinoEmbedder:
    """DINOv2 ViT-S/14 全局特征提取器。

    输出 384 维 L2 归一化向量；输入统一缩放到 224x224（14 的 16 倍，
    patch 对齐），保证注册与查询的特征空间一致。
    """

    def __init__(self):
        import torch

        self.torch = torch
        self.model = torch.hub.load("facebookresearch/dinov2", "dinov2_vits14_reg")
        self.model.eval()
        self.device = "cuda" if torch.cuda.is_available() else "cpu"
        self.model = self.model.to(self.device)
        self._transform = None  # 官方预处理管线（embed 内惰性构建）

    def embed(self, image_bytes: bytes) -> np.ndarray:
        """
        参数：
            image_bytes : bytes，JPEG/PNG 原始字节

        返回：
            np.ndarray，shape (384,)，已 L2 归一化

        预处理用 DINOv2 官方 transform（Resize(256) + CenterCrop(224) +
        ImageNet 归一化）：手动 resize((224,224)) 会对非整数倍缩放
        产生振铃/边缘拉丝，且与训练分布不一致导致特征劣化。
        """
        import io

        from PIL import Image
        from torchvision import transforms

        if self._transform is None:
            # 官方预处理管线（惰性构建，进程内复用）
            self._transform = transforms.Compose([
                transforms.Resize(256, interpolation=transforms.InterpolationMode.BICUBIC),
                transforms.CenterCrop(224),
                transforms.ToTensor(),
                transforms.Normalize(mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225]),
            ])

        img = Image.open(io.BytesIO(image_bytes)).convert("RGB")
        x = self._transform(img).unsqueeze(0).to(self.device)
        with self.torch.no_grad():
            feat = self.model(x).squeeze(0)
        feat = feat / feat.norm()
        return feat.cpu().numpy().astype("float32")


# ======================================================================
# 检索引擎
# ======================================================================
class RetrievalEngine:
    """识别总控：特征 -> 检索 -> 去重 -> 输出。

    索引产物（只读）：
        runtime/index/landmarks.faiss      FAISS 向量索引
        runtime/index/landmarks.meta.json  注册图元数据（与索引行号对齐）
    """

    # 返回候选数（前端展示 top-3；多取一些用于按地标去重）
    TOP_K = 3

    def __init__(self):
        import faiss

        self.embedder = DinoEmbedder()

        # ---------- 产物路径集中管理 ----------
        idx_dir = Path(settings.BASE_DIR) / "runtime" / "index"
        self.paths = {
            "faiss": str(idx_dir / "landmarks.faiss"),
            "meta": str(idx_dir / "landmarks.meta.json"),
        }
        if not Path(self.paths["faiss"]).exists():
            raise FileNotFoundError(
                f"识别索引不存在: {self.paths['faiss']}，"
                f"请先运行 python scripts/register_landmarks.py"
            )

        self.index = faiss.read_index(self.paths["faiss"])
        self.meta = json.loads(Path(self.paths["meta"]).read_text(encoding="utf-8"))
        if self.index.ntotal != len(self.meta):
            raise RuntimeError(
                f"索引与元数据不一致（{self.index.ntotal} vs {len(self.meta)}），"
                f"请重新运行 scripts/register_landmarks.py 重建"
            )
        logger.info("检索索引就绪：%d 条注册向量", self.index.ntotal)

    # ------------------------------------------------------------------
    def predict(self, image_bytes: bytes, top_k: int = 3):
        """
        参数：
            image_bytes : bytes，查询图原始字节
            top_k : int，返回前 K 个候选

        返回：
            list of (target_id: str, confidence: float)，按置信度降序
        """
        t0 = time.time()

        # 1. 全局特征与 FAISS 检索（多取一些用于按地标去重）
        q = self.embedder.embed(image_bytes).reshape(1, -1)
        sims, ids = self.index.search(q, min(top_k * 5, self.index.ntotal))

        # 2. 按地标去重：同一地标只保留最高检索分
        best = {}
        for sim, idx in zip(sims[0], ids[0]):
            if idx < 0:  # FAISS 无效槽位，理论上小候选池时不出现
                continue
            m = self.meta[idx]
            tid = m["target_id"]
            if tid not in best or sim > best[tid]:
                best[tid] = float(sim)

        results = sorted(best.items(), key=lambda x: -x[1])[:top_k]
        logger.info("检索识别耗时 %.0fms", (time.time() - t0) * 1000)
        return results


# ======================================================================
# 进程级单例
# ======================================================================
_engine = None
_engine_error = None


def get_engine():
    """获取引擎单例；索引或依赖不可用时返回 None（调用方提示重建）。"""
    global _engine, _engine_error
    if _engine is None and _engine_error is None:
        try:
            _engine = RetrievalEngine()
        except Exception as exc:
            _engine_error = str(exc)
            logger.warning("检索引擎不可用：%s", exc)
    return _engine
