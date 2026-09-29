"""
模块名称：地标图像识别服务

本模块由以下组件组成：
- FeatureExtractor       从图像中提取 SIFT-VLAD、HOG、轮廓、颜色矩、GLCM 特征
- SlidingWindowGenerator 生成多尺度随机滑动窗口
- LandmarkPredictor      加载模型，执行整图或贝叶斯多尺度预测
- ImageRecognizer        对外服务，融合数据库查询与地标识别

命令行用法（在项目根目录执行）：
    python -m app.services.image_recognizer <图片路径> [top_k] [选项]

位置参数：
    image           必填，待识别图片的文件路径
    top_k           可选，返回前 K 个候选结果，默认 3

可选参数：
    --no-bayes      关闭多尺度贝叶斯滑动窗口，改用整图预测
    --windows N     滑动窗口最大总数，默认 100
    --model-dir P   模型文件目录，默认 config.MODELS_DIR

示例：
    python -m app.services.image_recognizer test.jpg
    python -m app.services.image_recognizer test.jpg 5
    python -m app.services.image_recognizer test.jpg --no-bayes
    python -m app.services.image_recognizer test.jpg 3 --windows 200

注意：必须以模块方式运行（-m），否则 `app.core.*` 无法被导入。
"""

import argparse
import os
import pickle
import sys
import tempfile
import time
import warnings
from pathlib import Path

sys.dont_write_bytecode = True

import cv2
import numpy as np
from scipy.cluster.vq import vq
from skimage.feature import graycomatrix, graycoprops, hog
from sklearn.exceptions import InconsistentVersionWarning

from app.core.config import MODELS_DIR
from app.core.db import LandmarkDB

warnings.filterwarnings("ignore", category=InconsistentVersionWarning)


# ======================================================================
# 特征提取
# ======================================================================
class FeatureExtractor:
    """
    图像特征提取器。

    将 SIFT-VLAD、HOG、轮廓、颜色矩、GLCM 五类特征按固定顺序拼接为
    原始特征向量：[VLAD, HOG, 轮廓, 颜色矩, GLCM]。
    HOG 的高维部分由外部的 PCA 进一步降维。
    """

    def __init__(
        self,
        kmeans_model,
        vlad_max_kp=500,
        hog_target_size=256,
        profile_segments=20,
    ):
        """
        参数：
            kmeans_model : sklearn.cluster.KMeans
                已训练的 VLAD 码本（聚类中心）
            vlad_max_kp : int
                单张图片最多参与 VLAD 编码的关键点数量
            hog_target_size : int
                HOG 特征的目标图像边长
            profile_segments : int
                轮廓曲线的垂直分段数
        """
        self.kmeans = kmeans_model
        self.vlad_max_kp = vlad_max_kp
        self.hog_target_size = hog_target_size
        self.profile_segments = profile_segments
        self.vlad_dim = kmeans_model.n_clusters * 128

    def extract_sift_vlad(self, img):
        """
        提取 SIFT 关键点并计算 VLAD 向量。

        SIFT 对旋转、尺度、亮度变化具有鲁棒性；VLAD 将描述子分配到最近
        聚类中心并累加残差，形成紧凑的全局图像表示。

        返回：
            numpy.ndarray，维度 = 聚类数 × 128；无关键点时返回零向量
        """
        sift = cv2.SIFT_create()
        _, des = sift.detectAndCompute(img, None)

        if des is None or len(des) == 0:
            return np.zeros(self.vlad_dim, dtype=np.float32)

        if len(des) > self.vlad_max_kp:
            indices = np.random.choice(len(des), self.vlad_max_kp, replace=False)
            des = des[indices]

        labels, _ = vq(des, self.kmeans.cluster_centers_)
        k = self.kmeans.n_clusters
        d = des.shape[1]

        vlad = np.zeros((k, d), dtype=np.float32)
        residuals = des - self.kmeans.cluster_centers_[labels]
        np.add.at(vlad, labels, residuals)

        vlad = vlad.flatten()
        vlad = vlad / (np.linalg.norm(vlad) + 1e-8)
        return vlad

    def extract_spm_hog(self, img):
        """
        提取 HOG 特征，输入图像先经 Letterbox 等比例缩放 + 居中填充。

        返回：
            numpy.ndarray，原始高维 HOG 特征
        """
        target_size = self.hog_target_size
        h, w = img.shape[:2]
        scale = target_size / max(h, w)
        new_w = max(1, int(w * scale))
        new_h = max(1, int(h * scale))

        resized = cv2.resize(img, (new_w, new_h), interpolation=cv2.INTER_AREA)
        canvas = np.full((target_size, target_size, 3), 0, dtype=np.uint8)
        dx = (target_size - new_w) // 2
        dy = (target_size - new_h) // 2
        canvas[dy : dy + new_h, dx : dx + new_w] = resized

        gray = cv2.cvtColor(canvas, cv2.COLOR_BGR2GRAY)
        hog_feat = hog(
            gray,
            orientations=9,
            pixels_per_cell=(8, 8),
            cells_per_block=(2, 2),
            block_norm="L2-Hys",
            visualize=False,
        )
        return hog_feat

    def extract_profile(self, img):
        """
        提取轴向宽度轮廓曲线特征。

        将二值化前景沿垂直方向均匀分为若干水平段，统计每段的最大宽度，
        归一化后形成轮廓曲线。金字塔呈线性递增，天坛呈蘑菇状，塔类呈弧线收分。

        返回：
            numpy.ndarray，长度 = profile_segments，数值范围 [0, 1]
        """
        segments = self.profile_segments
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        _, thresh = cv2.threshold(gray, 30, 255, cv2.THRESH_BINARY)
        h, _ = thresh.shape
        split_points = np.linspace(0, h, segments + 1, dtype=int)

        widths = []
        for i in range(segments):
            roi = thresh[split_points[i] : split_points[i + 1], :]
            if roi.size == 0:
                widths.append(0)
                continue
            row_sums = np.sum(roi > 0, axis=1)
            widths.append(int(np.max(row_sums)) if np.max(row_sums) > 0 else 0)

        widths = np.array(widths, dtype=np.float32)
        if np.max(widths) > 0:
            widths = widths / np.max(widths)
        return widths

    def extract_color_moments(self, img):
        """
        在 Lab 颜色空间计算一阶、二阶、三阶颜色矩。

        返回：
            numpy.ndarray，长度 9（L/a/b 三个通道各 3 个矩）
        """
        lab = cv2.cvtColor(img, cv2.COLOR_BGR2LAB)
        moments = []
        for ch in range(3):
            channel = lab[:, :, ch].astype(np.float32)
            mean = np.mean(channel)
            std = np.std(channel)
            skew = np.mean((channel - mean) ** 3) / ((std + 1e-8) ** 3)
            moments.extend([mean, std, skew])
        return np.array(moments, dtype=np.float32)

    def extract_glcm(self, img):
        """
        基于灰度共生矩阵计算纹理统计量：能量、对比度、同质性、相关性。

        使用 0° 与 45° 两个方向的平均值，获得一定旋转不变性。

        返回：
            numpy.ndarray，长度 4
        """
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        gray = cv2.resize(gray, (128, 128), interpolation=cv2.INTER_AREA)

        glcm = graycomatrix(
            gray, distances=[1], angles=[0, np.pi / 4], levels=256, symmetric=True
        )
        props = ["energy", "contrast", "homogeneity", "correlation"]
        features = [graycoprops(glcm, prop).mean() for prop in props]
        return np.array(features, dtype=np.float32)

    def extract_raw_features(self, img):
        """
        提取完整原始特征向量（含未降维 HOG）。

        返回：
            numpy.ndarray，顺序为 [VLAD, HOG, 轮廓, 颜色矩, GLCM]
        """
        vlad = self.extract_sift_vlad(img)
        hog_feat = self.extract_spm_hog(img)
        profile = self.extract_profile(img)
        color = self.extract_color_moments(img)
        glcm = self.extract_glcm(img)
        feat = np.concatenate([vlad, hog_feat, profile, color, glcm])
        return feat.astype(np.float32)


# ======================================================================
# 滑动窗口
# ======================================================================
class SlidingWindowGenerator:
    """
    多尺度随机滑动窗口生成器。

    采样数量与尺度平方成反比，大尺度窗口采样少、小尺度窗口采样多。
    当某尺度可采样的位置总数少于分配数时，自动切换为密集采样。
    """

    def __init__(self, scale_ratios=None, max_windows_total=100):
        """
        参数：
            scale_ratios : list of float, optional
                各尺度相对于短边的比例，默认 [1.0, 0.7, 0.5, 0.3]
            max_windows_total : int, optional
                生成窗口的最大总数，默认 100
        """
        self.scale_ratios = scale_ratios or [1.0, 0.7, 0.5, 0.3]
        self.max_windows_total = max_windows_total

    def generate(self, img):
        """
        对一张图生成全部滑动窗口。

        参数：
            img : numpy.ndarray，BGR 图像

        返回：
            list of numpy.ndarray，所有滑动窗口
        """
        scale_ratios = self.scale_ratios
        max_windows_total = self.max_windows_total

        h, w = img.shape[:2]
        short_side = min(h, w)
        all_windows = []

        weights = [1.0 / (r * r) for r in scale_ratios]
        total_weight = sum(weights)

        samples_per_scale = []
        for wgt in weights:
            n = int(max_windows_total * (wgt / total_weight))
            samples_per_scale.append(max(1, n))

        while sum(samples_per_scale) < max_windows_total:
            max_idx = weights.index(max(weights))
            samples_per_scale[max_idx] += 1
        while sum(samples_per_scale) > max_windows_total:
            min_idx = weights.index(min(weights))
            if samples_per_scale[min_idx] > 1:
                samples_per_scale[min_idx] -= 1
            else:
                for i in sorted(range(len(weights)), key=lambda i: weights[i]):
                    if samples_per_scale[i] > 1:
                        samples_per_scale[i] -= 1
                        break

        for ratio, n_samples in zip(scale_ratios, samples_per_scale):
            win_size = max(int(short_side * ratio), 64)
            if win_size > h or win_size > w:
                continue

            max_x = w - win_size
            max_y = h - win_size

            if max_x == 0 and max_y == 0:
                all_windows.append(img)
                continue

            total_positions = (max_x + 1) * (max_y + 1)
            actual_samples = min(n_samples, total_positions)

            if actual_samples == total_positions:
                for y in range(max_y + 1):
                    for x in range(max_x + 1):
                        all_windows.append(img[y : y + win_size, x : x + win_size])
            else:
                for _ in range(actual_samples):
                    x = np.random.randint(0, max_x + 1)
                    y = np.random.randint(0, max_y + 1)
                    all_windows.append(img[y : y + win_size, x : x + win_size])

        return all_windows


# ======================================================================
# 地标预测
# ======================================================================
class LandmarkPredictor:
    """
    地标识别预测器。

    加载模型后，对图像执行整图预测或多尺度贝叶斯滑动窗口预测。
    多尺度模式下，对不同尺度的窗口概率取平均后加权求和，再归一化为最终概率。
    """

    def __init__(self, model_dir=MODELS_DIR):
        """
        参数：
            model_dir : str 或 pathlib.Path
                模型文件存放目录，默认 config.MODELS_DIR
        """
        self.model_dir = str(model_dir)
        self.vlad_max_kp = 500
        self.hog_target_size = 256
        self.profile_segments = 20

        print("正在加载模型...")
        self.encoder = self._load_pickle("label_encoder.pkl")
        self.kmeans = self._load_pickle("kmeans_vlad.pkl")
        self.pca = self._load_pickle("pca_hog.pkl")
        self.scaler = self._load_pickle("scaler.pkl")
        self.model = self._load_pickle("lr_model.pkl")

        self.vlad_dim = self.kmeans.n_clusters * 128
        self.hog_dim = self.pca.n_features_in_

        self.extractor = FeatureExtractor(
            self.kmeans,
            vlad_max_kp=self.vlad_max_kp,
            hog_target_size=self.hog_target_size,
            profile_segments=self.profile_segments,
        )
        self.window_generator = SlidingWindowGenerator()

        print("模型加载完成。")

    # ------------------------------------------------------------------
    # 内部工具
    # ------------------------------------------------------------------
    def _load_pickle(self, filename):
        """从 model_dir 加载 pickle 文件。"""
        path = os.path.join(self.model_dir, filename)
        if not os.path.exists(path):
            raise FileNotFoundError(f"模型文件不存在: {path}")
        with open(path, "rb") as f:
            return pickle.load(f)

    def _transform_features(self, raw_feat):
        """
        对原始特征做 PCA 降维并重新拼接。

        输入顺序：[VLAD, HOG, 轮廓, 颜色, GLCM]
        输出顺序：[VLAD, PCA-HOG, 轮廓, 颜色, GLCM]
        """
        vlad = raw_feat[: self.vlad_dim]

        hog_start = self.vlad_dim
        hog_end = hog_start + self.hog_dim
        hog_raw = raw_feat[hog_start:hog_end]

        profile_start = hog_end
        profile_end = profile_start + self.profile_segments
        profile = raw_feat[profile_start:profile_end]

        color_start = profile_end
        color_end = color_start + 9
        color = raw_feat[color_start:color_end]

        glcm_start = color_end
        glcm_end = glcm_start + 4
        glcm = raw_feat[glcm_start:glcm_end]

        hog_pca = self.pca.transform(hog_raw.reshape(1, -1)).flatten()
        return np.concatenate([vlad, hog_pca, profile, color, glcm])

    def _predict_proba_single(self, img):
        """对单张图返回全部类别的概率分布。"""
        raw = self.extractor.extract_raw_features(img)
        final = self._transform_features(raw)
        feat_scaled = self.scaler.transform(final.reshape(1, -1))

        if hasattr(self.model, "predict_proba"):
            return self.model.predict_proba(feat_scaled)[0]

        scores = self.model.decision_function(feat_scaled)[0]
        exp_scores = np.exp(scores - np.max(scores))
        return exp_scores / np.sum(exp_scores)

    def _topk_from_probas(self, probas, top_k):
        """从概率分布中取出 Top-K 标签及置信度。"""
        top_indices = np.argsort(probas)[::-1][:top_k]
        return [(self.encoder.classes_[idx], float(probas[idx])) for idx in top_indices]

    # ------------------------------------------------------------------
    # 对外预测
    # ------------------------------------------------------------------
    def predict(
        self,
        img_path,
        top_k=3,
        use_bayes=True,
        scale_ratios=None,
        max_windows_total=100,
    ):
        """
        对图片进行地标识别。

        参数：
            img_path : str
                图片路径
            top_k : int
                返回前 K 个结果，默认 3
            use_bayes : bool
                是否启用多尺度贝叶斯滑动窗口，默认 True
            scale_ratios : list of float, optional
                各尺度比例，默认 [1.0, 0.7, 0.5, 0.3]
            max_windows_total : int
                滑动窗口最大总数，默认 100

        返回：
            list of (str, float)，按置信度降序
        """
        img = cv2.imread(img_path)
        if img is None:
            raise ValueError(f"无法读取图片: {img_path}")

        if not use_bayes:
            return self._topk_from_probas(self._predict_proba_single(img), top_k)

        return self._predict_bayes(img, top_k, scale_ratios, max_windows_total)

    def _predict_bayes(self, img, top_k, scale_ratios, max_windows_total):
        """
        多尺度贝叶斯滑动窗口预测。

        流程：生成多尺度窗口 → 按尺寸分组 → 每组内平均类别概率 →
        按尺度加权取对数 → 求和归一化为最终概率 → 取 Top-K。

        参数：
            img : numpy.ndarray，BGR 图像
            top_k : int，返回前 K 个结果
            scale_ratios : list of float，各尺度比例
            max_windows_total : int，滑动窗口最大总数

        返回：
            list of (str, float)，按置信度降序
        """
        self.window_generator.scale_ratios = scale_ratios or [1.0, 0.7, 0.5, 0.3]
        self.window_generator.max_windows_total = max_windows_total

        windows = self.window_generator.generate(img)
        if not windows:
            return self._topk_from_probas(self._predict_proba_single(img), top_k)

        # 按窗口尺寸分组（向下取整到 10 的倍数）
        scale_groups = {}
        for win in windows:
            key = round(win.shape[0] / 10) * 10
            scale_groups.setdefault(key, []).append(win)

        ratios = self.window_generator.scale_ratios
        max_ratio = max(ratios)
        scale_weights = {r: (r / max_ratio) for r in ratios}

        log_evidences = []
        short_side = min(img.shape[:2])

        for group_key, group_windows in scale_groups.items():
            ratio_est = group_key / short_side
            closest_ratio = min(scale_weights.keys(), key=lambda r: abs(r - ratio_est))
            weight = scale_weights.get(closest_ratio, 1.0)

            group_prob_sum = None
            for win in group_windows:
                prob = self._predict_proba_single(win)
                group_prob_sum = (
                    prob if group_prob_sum is None else group_prob_sum + prob
                )

            group_prob_avg = group_prob_sum / len(group_windows)
            group_prob_avg = np.clip(group_prob_avg, 1e-12, 1.0)
            log_evidences.append(np.log(group_prob_avg) * weight)

        total_log = np.sum(log_evidences, axis=0)
        max_log = np.max(total_log)
        exp_log = np.exp(total_log - max_log)
        final_probas = exp_log / np.sum(exp_log)

        return self._topk_from_probas(final_probas, top_k)


# ======================================================================
# 对外服务
# ======================================================================
class ImageRecognizer:
    """
    图像识别器：融合数据库查询与地标识别。

    识别成功后返回地标名称、置信度等信息。
    """

    def __init__(self, model_dir=MODELS_DIR):
        """
        参数：
            model_dir : str 或 pathlib.Path
                模型文件存放目录，默认 config.MODELS_DIR
        """
        self.db = LandmarkDB()
        self.model_dir = str(model_dir)

        self.target_info = {}
        self._load_heritage_info()

        try:
            self.predictor = LandmarkPredictor(model_dir=self.model_dir)
            print("ImageRecognizer: 模型加载成功。")
        except Exception as e:
            print(f"ImageRecognizer: 模型加载失败: {e}")
            self.predictor = None

    def _load_heritage_info(self):
        """从数据库加载地标信息，键为小写 target_id，值仅包含 name。"""
        rows = self.db.get_heritage_info()
        if rows:
            for row in rows:
                self.target_info[row["target_id"].lower()] = {"name": row["name"]}

    def recognize(self, image_data):
        """
        识别主函数。

        参数：
            image_data : bytes
                图片二进制数据

        返回：
            dict，包含 success / target_id / name / confidence /
            confidence_percent / annotated_image 等字段
        """
        if self.predictor is None:
            return {"success": False, "message": "模型未加载，请检查模型文件是否存在。"}

        try:
            nparr = np.frombuffer(image_data, np.uint8)
            img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
            if img is None:
                return {"success": False, "message": "无法解析图片"}

            with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as tmp:
                tmp_path = tmp.name
                cv2.imwrite(tmp_path, img)

            try:
                results = self.predictor.predict(tmp_path, top_k=1, use_bayes=True)
            finally:
                try:
                    os.unlink(tmp_path)
                except OSError:
                    pass

            if not results:
                return {"success": False, "message": "未能识别出地标"}

            pred_label, confidence = results[0]
            target_id = pred_label.lower()

            info = self.target_info.get(target_id)
            if not info:
                return {"success": False, "message": f"未找到地标信息: {target_id}"}

            return {
                "success": True,
                "target_id": target_id,
                "name": info["name"],
                "confidence": float(confidence),
                "confidence_percent": f"{confidence * 100:.1f}%",
                "annotated_image": None,
            }

        except Exception as e:
            return {"success": False, "message": f"识别出错: {str(e)}"}


# ======================================================================
# 命令行入口
# ======================================================================
def _parse_args(argv=None):
    parser = argparse.ArgumentParser(
        prog="python -m app.services.image_recognizer",
        description="地标图像识别命令行工具。",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "示例：\n"
            "  python -m app.services.image_recognizer test.jpg\n"
            "  python -m app.services.image_recognizer test.jpg 5\n"
            "  python -m app.services.image_recognizer test.jpg --no-bayes\n"
            "  python -m app.services.image_recognizer test.jpg 3 --windows 200\n"
        ),
    )
    parser.add_argument("image", help="待识别图片的路径")
    parser.add_argument(
        "top_k",
        nargs="?",
        type=int,
        default=3,
        help="返回前 K 个候选结果，默认 3",
    )
    parser.add_argument(
        "--no-bayes",
        action="store_true",
        help="关闭多尺度贝叶斯滑动窗口，改用整图预测",
    )
    parser.add_argument(
        "--windows",
        type=int,
        default=100,
        help="滑动窗口最大总数，默认 100",
    )
    parser.add_argument(
        "--model-dir",
        default=str(MODELS_DIR),
        help="模型文件目录，默认 config.MODELS_DIR",
    )
    return parser.parse_args(argv)


def main(argv=None):
    args = _parse_args(argv)

    predictor = LandmarkPredictor(model_dir=args.model_dir)

    start_time = time.time()
    results = predictor.predict(
        args.image,
        top_k=args.top_k,
        use_bayes=not args.no_bayes,
        max_windows_total=args.windows,
    )
    elapsed = time.time() - start_time

    print(f"\n预测结果 (Top-{args.top_k})：")
    for label, conf in results:
        print(f"- {label}: {conf:.4f}")
    print(f"模式: {'贝叶斯多尺度滑动窗口' if not args.no_bayes else '整图'}")
    if not args.no_bayes:
        print(f"窗口总数: {args.windows}")
    print(f"推理耗时: {elapsed:.3f} 秒")


if __name__ == "__main__":
    main()
