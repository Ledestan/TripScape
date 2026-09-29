"""
模块名称：地标识别模型训练脚本

本脚本从 data/train 与 data/valid 加载数据集，完成：
    1. 标签编码（LabelEncoder）
    2. VLAD 码本训练（MiniBatchKMeans）
    3. 训练集 / 验证集特征提取（VLAD + HOG + 轮廓 + 颜色矩 + GLCM）
    4. HOG 特征 PCA 降维
    5. 特征拼接、标准化（StandardScaler）
    6. 逻辑回归分类器训练与验证
    7. 模型文件输出到 models/

特征提取直接复用 app.services.image_recognizer.FeatureExtractor，
确保训练和推理阶段使用完全一致的特征管线。

用法（在项目根目录执行）：
    python scripts/train.py [选项]

可选参数：
    --train-dir P       训练集目录，默认 config.DATA_DIR / "train"
    --valid-dir P       验证集目录，默认 config.DATA_DIR / "valid"
    --model-dir P       模型输出目录，默认 config.MODELS_DIR
    --cache-dir P       特征缓存目录，默认 config.CACHE_DIR
    --n-clusters N      VLAD 码本聚类数，默认 64
    --pca-components N  HOG 降维后的主成分数，默认 512
    --force-rebuild     忽略缓存与已有模型，全部重新训练

示例：
    python scripts/train.py
    python scripts/train.py --force-rebuild
    python scripts/train.py --n-clusters 128 --pca-components 256
"""

import argparse
import os
import pickle
import sys
import time
import warnings
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import cv2
import numpy as np
from sklearn.cluster import MiniBatchKMeans
from sklearn.decomposition import PCA
from sklearn.exceptions import InconsistentVersionWarning
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, classification_report
from sklearn.preprocessing import LabelEncoder, StandardScaler

from app.core.config import DATA_DIR, MODELS_DIR
from app.services.image_recognizer import FeatureExtractor

CACHE_DIR = Path(__file__).resolve().parent.parent / "cache"

warnings.filterwarnings("ignore", category=InconsistentVersionWarning)


# ======================================================================
# 数据加载
# ======================================================================
class DataLoader:
    """
    从目录结构加载图片路径与类别标签。

    目录结构要求：
        data_dir/类别名/*.jpg（或 .jpeg / .png）

    类别按名称排序，保证多次运行结果可复现。
    """

    SUPPORTED_EXTS = (".jpg", ".jpeg", ".png")

    def __init__(self, data_dir):
        """
        参数：
            data_dir : str 或 pathlib.Path
                数据集根目录
        """
        self.data_dir = Path(data_dir)

    def load(self):
        """
        加载数据集。

        返回：
            (image_paths, label_names)
            - image_paths : list of str
            - label_names : list of str，与路径一一对应
        """
        if not self.data_dir.exists():
            raise FileNotFoundError(f"目录不存在: {self.data_dir}")

        image_paths = []
        label_names = []
        classes = sorted(
            d for d in os.listdir(self.data_dir) if os.path.isdir(self.data_dir / d)
        )

        for class_name in classes:
            class_dir = self.data_dir / class_name
            count = 0
            for file_name in os.listdir(class_dir):
                if file_name.lower().endswith(self.SUPPORTED_EXTS):
                    image_paths.append(str(class_dir / file_name))
                    label_names.append(class_name)
                    count += 1
            print(f"- {class_name}: {count}")

        print(f"从 {self.data_dir} 加载了 {len(image_paths)} 张图片")
        if not image_paths:
            raise ValueError(f"{self.data_dir} 下没有找到任何图片")
        return image_paths, label_names


# ======================================================================
# 标签编码
# ======================================================================
class LabelEncoderManager:
    """
    管理 LabelEncoder 的加载与训练。

    若模型目录已存在编码器，则直接加载并对验证集做 transform；
    否则在训练集上 fit，并校验验证集没有出现未见类别。
    """

    def load_or_train(self, train_names, val_names, model_path):
        """
        参数：
            train_names : list of str
            val_names : list of str
            model_path : str，编码器保存路径

        返回：
            (encoder, train_labels, val_labels)
        """
        if os.path.exists(model_path):
            print("\n========== 加载标签编码器 ==========")
            with open(model_path, "rb") as f:
                encoder = pickle.load(f)
            print(f"类别数: {len(encoder.classes_)}")
            print(f"类别列表: {list(encoder.classes_)}")
            train_labels = encoder.transform(train_names)
            val_labels = encoder.transform(val_names)
            return encoder, train_labels, val_labels

        print("\n========== 训练标签编码器 ==========")
        t_start = time.time()
        encoder = LabelEncoder()
        train_labels = encoder.fit_transform(train_names)

        try:
            val_labels = encoder.transform(val_names)
        except ValueError as e:
            raise ValueError("验证集中存在训练集未包含的类别，请检查数据") from e

        with open(model_path, "wb") as f:
            pickle.dump(encoder, f)

        print(f"训练集类别数: {len(encoder.classes_)}")
        print(f"类别列表: {list(encoder.classes_)}")
        print(
            f"类别映射: "
            f"{dict(zip(encoder.classes_, encoder.transform(encoder.classes_)))}"
        )
        print(f"[耗时] 标签编码: {time.time() - t_start:.2f} 秒")
        return encoder, train_labels, val_labels


# ======================================================================
# VLAD 码本
# ======================================================================
class VLADCodebookTrainer:
    """
    训练或加载 VLAD 码本。

    使用 MiniBatchKMeans 对 SIFT 描述子做增量聚类；
    单张图片的描述子数量受限，避免某类图片主导聚类中心。
    """

    def __init__(self, n_clusters=64, max_des_per_image=500, random_state=42):
        """
        参数：
            n_clusters : int
                VLAD 码本聚类数
            max_des_per_image : int
                单张图片参与聚类的描述子上限
            random_state : int
                随机种子
        """
        self.n_clusters = n_clusters
        self.max_des_per_image = max_des_per_image
        self.random_state = random_state

    def load_or_train(self, train_paths, model_path):
        """
        返回：
            MiniBatchKMeans
        """
        if os.path.exists(model_path):
            print("\n========== 加载 VLAD 码本 ==========")
            with open(model_path, "rb") as f:
                kmeans = pickle.load(f)
            print(f"聚类数: {kmeans.n_clusters}")
            print(f"VLAD特征维度: {kmeans.n_clusters * 128}")
            return kmeans

        print("\n========== 训练 VLAD 码本 ==========")
        t_start = time.time()

        kmeans = MiniBatchKMeans(
            n_clusters=self.n_clusters,
            batch_size=10000,
            random_state=self.random_state,
            n_init=3,
            max_iter=100,
        )
        sift = cv2.SIFT_create()
        processed = 0
        total_des = 0

        for idx, path in enumerate(train_paths):
            img = cv2.imread(path)
            if img is None:
                continue
            _, des = sift.detectAndCompute(img, None)
            if des is not None and len(des) > 0:
                if len(des) > self.max_des_per_image:
                    indices = np.random.choice(
                        len(des), self.max_des_per_image, replace=False
                    )
                    des = des[indices]
                kmeans.partial_fit(des)
                processed += 1
                total_des += len(des)

            if (idx + 1) % 100 == 0 or (idx + 1) == len(train_paths):
                print(
                    f"VLAD 码本训练进度: {idx + 1}/{len(train_paths)}，"
                    f"其中 {processed} 张参与训练，"
                    f"累计增量训练 {total_des} 个描述子"
                )

        with open(model_path, "wb") as f:
            pickle.dump(kmeans, f)

        print("VLAD 码本训练完成")
        print(f"聚类数: {kmeans.n_clusters}")
        print(f"VLAD特征维度: {kmeans.n_clusters * 128}")
        print(f"[耗时] VLAD 码本训练: {time.time() - t_start:.2f} 秒")
        return kmeans


# ======================================================================
# 特征提取与缓存
# ======================================================================
class FeaturePipeline:
    """
    使用 FeatureExtractor 提取原始特征，并支持 npy 缓存。

    缓存维度与当前特征配置不一致时会主动报错，防止特征代码变更后误用旧缓存。
    """

    COLOR_DIM = 9
    GLCM_DIM = 4

    def __init__(self, extractor, cache_dir):
        """
        参数：
            extractor : FeatureExtractor
            cache_dir : str 或 pathlib.Path
        """
        self.extractor = extractor
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    def _expected_dim(self, sample_img):
        """根据当前 extractor 配置计算预期的原始特征维度。"""
        hog_dim = self.extractor.extract_spm_hog(sample_img).shape[0]
        return (
            self.extractor.vlad_dim
            + hog_dim
            + self.extractor.profile_segments
            + self.COLOR_DIM
            + self.GLCM_DIM
        )

    def extract_or_load(self, paths, cache_path, sample_img, split_name):
        """
        从缓存加载，或重新提取并存盘。

        参数：
            paths : list of str
            cache_path : str
            sample_img : numpy.ndarray
                用于计算预期维度的样本图
            split_name : str
                用于打印，如 "训练集"

        返回：
            numpy.ndarray
        """
        expected_dim = self._expected_dim(sample_img)

        if os.path.exists(cache_path):
            print(f"发现{split_name}缓存特征，直接加载...")
            X = np.load(cache_path)
            if X.shape[1] != expected_dim:
                raise ValueError(
                    f"{split_name}缓存特征维度 ({X.shape[1]}) 与当前特征维度 "
                    f"({expected_dim}) 不匹配，请删除缓存文件 {cache_path} 后重新运行"
                )
            print(f"{split_name}特征形状: {X.shape}")
            return X

        print(f"未找到缓存，开始提取{split_name}特征...")
        t_start = time.time()

        features = []
        total = len(paths)
        for idx, path in enumerate(paths):
            img = cv2.imread(path)
            if img is None:
                raise ValueError(f"无法读取图片: {path}")
            features.append(self.extractor.extract_raw_features(img))

            if (idx + 1) % 100 == 0 or (idx + 1) == total:
                print(f"{split_name}特征提取进度: {idx + 1}/{total}")

        X = np.array(features)
        np.save(cache_path, X)

        print(f"{split_name}特征已保存至 {cache_path}，形状: {X.shape}")
        print(f"[耗时] {split_name}特征提取: {time.time() - t_start:.2f} 秒")
        return X


# ======================================================================
# PCA 降维
# ======================================================================
class PCATrainer:
    """
    对高维 HOG 特征做 PCA 降维。

    若已保存的 PCA 主成分数与当前配置不一致，会重新训练。
    """

    def __init__(self, n_components=512, random_state=42):
        """
        参数：
            n_components : int
                目标主成分数
            random_state : int
        """
        self.n_components = n_components
        self.random_state = random_state

    def load_or_train(self, hog_train, hog_val, model_path):
        """
        返回：
            (pca, hog_pca_train, hog_pca_val)
        """
        actual_n = min(self.n_components, hog_train.shape[0], hog_train.shape[1])
        print(f"PCA 目标主成分数: {self.n_components}，实际使用: {actual_n}")

        if os.path.exists(model_path):
            print("加载已保存的 PCA 模型...")
            with open(model_path, "rb") as f:
                pca = pickle.load(f)

            if pca.n_components_ != actual_n:
                print("PCA 主成分数不一致，重新训练...")
                pca = PCA(n_components=actual_n, random_state=self.random_state)
                hog_pca_train = pca.fit_transform(hog_train)
                with open(model_path, "wb") as f:
                    pickle.dump(pca, f)
            else:
                hog_pca_train = pca.transform(hog_train)
        else:
            print("训练 PCA 降维模型...")
            t_start = time.time()
            pca = PCA(n_components=actual_n, random_state=self.random_state)
            hog_pca_train = pca.fit_transform(hog_train)
            with open(model_path, "wb") as f:
                pickle.dump(pca, f)
            print(f"[耗时] PCA 训练: {time.time() - t_start:.2f} 秒")

        hog_pca_val = pca.transform(hog_val)
        return pca, hog_pca_train, hog_pca_val


# ======================================================================
# 标准化
# ======================================================================
class ScalerManager:
    """
    管理 StandardScaler 的加载与训练。
    """

    def load_or_train(self, X_train, X_val, model_path):
        """
        返回：
            (scaler, X_train_scaled, X_val_scaled)
        """
        if os.path.exists(model_path):
            print("\n========== 加载标准化器 ==========")
            with open(model_path, "rb") as f:
                scaler = pickle.load(f)
            return scaler, scaler.transform(X_train), scaler.transform(X_val)

        print("\n========== 特征标准化 ==========")
        t_start = time.time()
        scaler = StandardScaler()
        X_train_scaled = scaler.fit_transform(X_train)
        X_val_scaled = scaler.transform(X_val)

        with open(model_path, "wb") as f:
            pickle.dump(scaler, f)
        print(f"[耗时] 特征标准化: {time.time() - t_start:.2f} 秒")
        return scaler, X_train_scaled, X_val_scaled


# ======================================================================
# 分类器
# ======================================================================
class ClassifierTrainer:
    """
    逻辑回归分类器训练与加载。
    """

    def __init__(self, C=0.1, max_iter=3000, random_state=42, verbose=True):
        """
        参数：
            C : float
                正则化强度的倒数，越小正则越强
            max_iter : int
                最大迭代次数
            random_state : int
            verbose : bool
                是否输出训练过程
        """
        self.C = C
        self.max_iter = max_iter
        self.random_state = random_state
        self.verbose = verbose

    def load_or_train(self, X_train, y_train, model_path):
        """
        返回：
            LogisticRegression
        """
        if os.path.exists(model_path):
            print("\n========== 加载逻辑回归模型 ==========")
            with open(model_path, "rb") as f:
                model = pickle.load(f)
            print("模型加载完成")
            return model

        print("\n========== 训练逻辑回归 ==========")
        t_start = time.time()
        model = LogisticRegression(
            C=self.C,
            class_weight="balanced",
            max_iter=self.max_iter,
            random_state=self.random_state,
            solver="saga",
            tol=1e-3,
            verbose=self.verbose,
        )
        model.fit(X_train, y_train)

        with open(model_path, "wb") as f:
            pickle.dump(model, f)
        print(f"[耗时] 逻辑回归训练: {time.time() - t_start:.2f} 秒")
        return model


# ======================================================================
# 训练总控
# ======================================================================
class LandmarkTrainer:
    """
    地标识别模型训练总控。

    负责串联数据加载、标签编码、VLAD 码本、特征提取、PCA、标准化
    与逻辑回归训练，并输出模型文件到 model_dir。
    """

    def __init__(
        self,
        train_dir=DATA_DIR / "train",
        valid_dir=DATA_DIR / "valid",
        model_dir=MODELS_DIR,
        cache_dir=CACHE_DIR,
        n_clusters=64,
        pca_components=512,
        force_rebuild=False,
    ):
        """
        参数：
            train_dir / valid_dir : 数据集目录
            model_dir : 模型输出目录
            cache_dir : 特征缓存目录
            n_clusters : VLAD 码本聚类数
            pca_components : HOG PCA 主成分数
            force_rebuild : 是否强制重建
        """
        self.train_dir = Path(train_dir)
        self.valid_dir = Path(valid_dir)
        self.model_dir = Path(model_dir)
        self.cache_dir = Path(cache_dir)
        self.n_clusters = n_clusters
        self.pca_components = pca_components
        self.force_rebuild = force_rebuild

        self.model_dir.mkdir(parents=True, exist_ok=True)
        self.cache_dir.mkdir(parents=True, exist_ok=True)

        # 各阶段产物路径
        self.paths = {
            "encoder": str(self.model_dir / "label_encoder.pkl"),
            "kmeans": str(self.model_dir / "kmeans_vlad.pkl"),
            "pca": str(self.model_dir / "pca_hog.pkl"),
            "scaler": str(self.model_dir / "scaler.pkl"),
            "classifier": str(self.model_dir / "lr_model.pkl"),
            "train_cache": str(self.cache_dir / "X_train.npy"),
            "val_cache": str(self.cache_dir / "X_val.npy"),
        }

    # ------------------------------------------------------------------
    def _clean_artifacts(self):
        """force_rebuild 时删除已有缓存与模型文件。"""
        print("检测到 --force-rebuild，删除已有缓存与模型文件...")
        for key in (
            "train_cache",
            "val_cache",
            "kmeans",
            "pca",
            "scaler",
            "classifier",
            "encoder",
        ):
            path = self.paths[key]
            if os.path.exists(path):
                os.remove(path)
                print(f"  已删除: {path}")

    # ------------------------------------------------------------------
    def run(self):
        """执行完整训练流程。"""
        overall_start = time.time()

        if self.force_rebuild:
            self._clean_artifacts()

        # 数据加载
        print("========== 数据加载 ==========")
        print("训练集数据加载：")
        train_paths, train_names = DataLoader(self.train_dir).load()
        print("\n验证集数据加载：")
        val_paths, val_names = DataLoader(self.valid_dir).load()

        # 标签编码
        encoder, train_labels, val_labels = LabelEncoderManager().load_or_train(
            train_names, val_names, self.paths["encoder"]
        )

        # VLAD 码本
        kmeans = VLADCodebookTrainer(n_clusters=self.n_clusters).load_or_train(
            train_paths, self.paths["kmeans"]
        )

        # 特征提取
        extractor = FeatureExtractor(kmeans)
        pipeline = FeaturePipeline(extractor, self.cache_dir)

        sample_img = cv2.imread(train_paths[0])
        if sample_img is None:
            raise ValueError(f"无法读取样本图片: {train_paths[0]}")

        print("\n========== 训练集特征提取 ==========")
        X_train = pipeline.extract_or_load(
            train_paths, self.paths["train_cache"], sample_img, "训练集"
        )

        print("\n========== 验证集特征提取 ==========")
        X_val = pipeline.extract_or_load(
            val_paths, self.paths["val_cache"], sample_img, "验证集"
        )

        y_train = np.array(train_labels)
        y_val = np.array(val_labels)

        # HOG PCA 降维
        print("\n========== HOG 特征降维 (PCA) ==========")
        vlad_dim = extractor.vlad_dim
        hog_dim = extractor.extract_spm_hog(sample_img).shape[0]
        hog_start = vlad_dim
        hog_end = vlad_dim + hog_dim

        hog_train = X_train[:, hog_start:hog_end]
        hog_val = X_val[:, hog_start:hog_end]

        pca, hog_pca_train, hog_pca_val = PCATrainer(
            n_components=self.pca_components
        ).load_or_train(hog_train, hog_val, self.paths["pca"])

        print(f"HOG 降维后维度: {hog_pca_train.shape[1]}")

        # 拼接：[VLAD, PCA-HOG, 轮廓, 颜色矩, GLCM]
        profile_start = hog_end
        profile_end = profile_start + extractor.profile_segments
        color_start = profile_end
        color_end = color_start + FeaturePipeline.COLOR_DIM
        glcm_start = color_end
        glcm_end = glcm_start + FeaturePipeline.GLCM_DIM

        X_train = np.concatenate(
            [
                X_train[:, :hog_start],
                hog_pca_train,
                X_train[:, profile_start:profile_end],
                X_train[:, color_start:color_end],
                X_train[:, glcm_start:glcm_end],
            ],
            axis=1,
        )
        X_val = np.concatenate(
            [
                X_val[:, :hog_start],
                hog_pca_val,
                X_val[:, profile_start:profile_end],
                X_val[:, color_start:color_end],
                X_val[:, glcm_start:glcm_end],
            ],
            axis=1,
        )
        print(f"最终特征向量总维度: {X_train.shape[1]}")

        # 标准化
        _, X_train_scaled, X_val_scaled = ScalerManager().load_or_train(
            X_train, X_val, self.paths["scaler"]
        )

        # 训练分类器
        model = ClassifierTrainer().load_or_train(
            X_train_scaled, y_train, self.paths["classifier"]
        )

        # 验证集评估
        print("\n========== 验证集预测 ==========")
        t_start = time.time()
        y_pred = model.predict(X_val_scaled)
        print(f"[耗时] 验证集预测: {time.time() - t_start:.2f} 秒")

        print("\n========== 评估模型性能 ==========")
        t_start = time.time()
        acc = accuracy_score(y_val, y_pred)
        print(f"验证集准确率: {acc:.4f}")
        report = classification_report(y_val, y_pred, target_names=encoder.classes_)
        print(report)
        print(f"[耗时] 性能评估: {time.time() - t_start:.2f} 秒")

        print("\n" + "=" * 50)
        print(f"所有步骤完成，总运行时间: {time.time() - overall_start:.2f} 秒")
        print(f"模型文件保存在: {self.model_dir}")


# ======================================================================
# 命令行入口
# ======================================================================
def _parse_args(argv=None):
    parser = argparse.ArgumentParser(
        prog="python scripts/train.py",
        description="地标识别模型训练脚本。",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "示例：\n"
            "  python scripts/train.py\n"
            "  python scripts/train.py --force-rebuild\n"
            "  python scripts/train.py --n-clusters 128 --pca-components 256\n"
        ),
    )
    parser.add_argument(
        "--train-dir",
        default=str(DATA_DIR / "train"),
        help="训练集目录，默认 config.DATA_DIR/train",
    )
    parser.add_argument(
        "--valid-dir",
        default=str(DATA_DIR / "valid"),
        help="验证集目录，默认 config.DATA_DIR/valid",
    )
    parser.add_argument(
        "--model-dir",
        default=str(MODELS_DIR),
        help="模型输出目录，默认 config.MODELS_DIR",
    )
    parser.add_argument(
        "--cache-dir",
        default=str(CACHE_DIR),
        help="特征缓存目录，默认 config.CACHE_DIR",
    )
    parser.add_argument(
        "--n-clusters",
        type=int,
        default=64,
        help="VLAD 码本聚类数，默认 64",
    )
    parser.add_argument(
        "--pca-components",
        type=int,
        default=512,
        help="HOG 降维后的主成分数，默认 512",
    )
    parser.add_argument(
        "--force-rebuild",
        action="store_true",
        help="忽略缓存与已有模型，全部重新训练",
    )
    return parser.parse_args(argv)


def main(argv=None):
    args = _parse_args(argv)

    trainer = LandmarkTrainer(
        train_dir=args.train_dir,
        valid_dir=args.valid_dir,
        model_dir=args.model_dir,
        cache_dir=args.cache_dir,
        n_clusters=args.n_clusters,
        pca_components=args.pca_components,
        force_rebuild=args.force_rebuild,
    )
    trainer.run()


if __name__ == "__main__":
    main()
