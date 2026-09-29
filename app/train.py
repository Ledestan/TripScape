import os
import pickle
import time
import warnings

import cv2
import numpy as np
from scipy.cluster.vq import vq
from skimage.feature import graycomatrix, graycoprops, hog
from sklearn.cluster import MiniBatchKMeans
from sklearn.decomposition import PCA
from sklearn.exceptions import InconsistentVersionWarning
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, classification_report
from sklearn.preprocessing import LabelEncoder, StandardScaler

warnings.filterwarnings("ignore", category=InconsistentVersionWarning)


def load_data(data_dir):
    """
    从指定目录加载图片路径和对应的类别名称。

    目录结构要求：
        data_dir/类别名/*.jpg (或 .jpeg/.png)

    参数
    ----------
    data_dir : str
        数据集根目录路径。

    返回
    -------
    image_paths : list of str
        所有图片的完整路径列表。
    label_names : list of str
        与路径一一对应的类别名称（原始字符串）列表。
    """
    image_paths = []
    label_names = []
    if not os.path.exists(data_dir):
        raise FileNotFoundError(f"目录不存在: {data_dir}")
    # 获取所有子目录作为类别，排序保证可复现性
    # 使用 os.listdir 并过滤目录，再通过 sorted 稳定排序
    classes = sorted(
        [d for d in os.listdir(data_dir) if os.path.isdir(os.path.join(data_dir, d))]
    )
    for class_name in classes:
        class_dir = os.path.join(data_dir, class_name)
        count = 0
        for file_name in os.listdir(class_dir):
            if file_name.lower().endswith((".jpg", ".jpeg", ".png")):
                image_paths.append(os.path.join(class_dir, file_name))
                label_names.append(class_name)
                count += 1
        print(f"- {class_name}: {count}")
    print(f"从 {data_dir} 加载了 {len(image_paths)} 张图片")
    return image_paths, label_names


def extract_sift_vlad(img, kmeans_model, max_kp):
    """
    提取 SIFT 关键点并计算 VLAD（局部聚合描述子）向量。

    SIFT 是一种尺度不变特征变换算法，检测图像中的关键点并生成 128 维描述子，
    对旋转、尺度、亮度变化具有鲁棒性。
    VLAD 将每个描述子分配到最近聚类中心，累加描述子与中心的残差，形成紧凑的全局图像表示，
    相比词袋模型保留了更多空间分布信息。

    参数
    ----------
    img : numpy.ndarray
        BGR 格式的图像。
    kmeans_model : sklearn.cluster.KMeans
        已训练的码本（聚类中心）。
    max_kp : int, optional
        单张图片最多参与 VLAD 编码的关键点数量（随机采样）。

    返回
    -------
    numpy.ndarray
        VLAD 特征向量，维度 = 聚类数 × 128。若无关键点，返回零向量。
    """
    # 创建 SIFT 对象并检测关键点及描述子
    sift = cv2.SIFT_create()
    kp, des = sift.detectAndCompute(img, None)

    # 若无关键点，返回同维度零向量，确保所有图片特征维度一致
    if des is None or len(des) == 0:
        return np.zeros(kmeans_model.cluster_centers_.shape[0] * 128, dtype=np.float32)

    # 随机采样关键点，控制参与 VLAD 编码的数量，降低计算开销
    if len(des) > max_kp:
        indices = np.random.choice(len(des), max_kp, replace=False)
        des = des[indices]

    # 将描述子硬分配至最近的聚类中心（使用 vq）
    labels, _ = vq(des, kmeans_model.cluster_centers_)
    k = kmeans_model.n_clusters
    d = des.shape[1]

    # 初始化 VLAD 矩阵，累加每个描述子与其对应聚类中心的残差
    vlad = np.zeros((k, d), dtype=np.float32)
    residuals = des - kmeans_model.cluster_centers_[labels]
    np.add.at(vlad, labels, residuals)

    # 展平并 L2 归一化，减小光照变化影响
    vlad = vlad.flatten()
    vlad = vlad / (np.linalg.norm(vlad) + 1e-8)
    return vlad


def extract_spm_hog(img):
    """
    提取 HOG（方向梯度直方图）特征，输入图像先经 Letterbox 等比例缩放+填充。

    HOG 通过统计图像局部区域的梯度方向直方图来捕捉物体的边缘和形状信息，
    对光照变化和小的空间偏移具有鲁棒性，常用于行人检测等任务。
    Letterbox 处理保持物体原始宽高比，避免拉伸变形，填充黑色区域梯度为零不影响统计。

    参数
    ----------
    img : numpy.ndarray
        BGR 格式的图像。

    返回
    -------
    numpy.ndarray
        HOG 特征向量（原始高维，后续会经由主流程中的 PCA 进行降维）。
    """
    target_size = 256
    h, w = img.shape[:2]
    # 计算等比例缩放因子，使长边等于目标尺寸
    scale = target_size / max(h, w)
    new_w = max(1, int(w * scale))
    new_h = max(1, int(h * scale))

    # 使用 INTER_AREA 进行缩放，适合缩小操作以减少锯齿
    resized = cv2.resize(img, (new_w, new_h), interpolation=cv2.INTER_AREA)
    # 创建黑色画布并居中放置缩放后的图像，保证输入尺寸固定
    canvas = np.full((target_size, target_size, 3), 0, dtype=np.uint8)
    dx = (target_size - new_w) // 2
    dy = (target_size - new_h) // 2
    canvas[dy : dy + new_h, dx : dx + new_w] = resized

    # 转为灰度图并计算 HOG 描述子
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


def extract_profile(img, profile_segments):
    """
    提取轴向宽度轮廓曲线特征，用于刻画建筑的纵向形状变化。
    该特征将二值化前景沿垂直方向均匀分为多个水平段，统计每段的最大宽度，形成轮廓曲线。

    参数
    ----------
    img : numpy.ndarray
        BGR 格式的图像。

    返回
    -------
    numpy.ndarray
        长度为 profile_segments 的归一化宽度曲线，数值范围 [0, 1]。
    """
    # 灰度化后二值化（阈值 30 过滤暗噪声），提取前景区域
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    _, thresh = cv2.threshold(gray, 30, 255, cv2.THRESH_BINARY)
    h, w = thresh.shape
    # 将图像沿垂直方向均匀分为 profile_segments 段
    segments = np.linspace(0, h, profile_segments + 1, dtype=int)
    widths = []
    for i in range(profile_segments):
        roi = thresh[segments[i] : segments[i + 1], :]
        if roi.size == 0:
            widths.append(0)
            continue
        # 取该段内每行前景像素数目的最大值作为该位置的轮廓宽度
        row_sums = np.sum(roi > 0, axis=1)
        if np.max(row_sums) == 0:
            widths.append(0)
        else:
            widths.append(np.max(row_sums))
    widths = np.array(widths, dtype=np.float32)
    # 归一化至 [0,1]，消除物体尺寸和拍摄距离的尺度影响
    if np.max(widths) > 0:
        widths = widths / np.max(widths)
    return widths


def extract_color_moments(img):
    """
    在 Lab 颜色空间计算颜色矩：一阶矩（均值）、二阶矩（标准差）、三阶矩（偏度）。

    颜色矩是一种紧凑的颜色特征，不需要量化颜色直方图，每个通道仅三个值，
    对光照和视角变化具有一定鲁棒性。Lab 空间的设计使得颜色差异更符合人眼感知。

    参数
    ----------
    img : numpy.ndarray
        BGR 格式的图像。

    返回
    -------
    numpy.ndarray
        长度为 9 的颜色矩特征向量（L均值、L标准差、L偏度、a均值、a标准差、a偏度、b均值、b标准差、b偏度）。
    """
    # 转换至 Lab 颜色空间
    lab = cv2.cvtColor(img, cv2.COLOR_BGR2LAB)
    moments = []
    for ch in range(3):
        channel = lab[:, :, ch].astype(np.float32)
        mean = np.mean(channel)
        std = np.std(channel)
        # 偏度计算公式为 E[(X-μ)^3] / σ^3，描述分布不对称程度
        skew = np.mean(((channel - mean) ** 3)) / ((std + 1e-8) ** 3)
        moments.extend([mean, std, skew])
    return np.array(moments, dtype=np.float32)


def extract_glcm(img):
    """
    基于灰度共生矩阵（GLCM）计算四个纹理统计量：能量、对比度、同质性、相关性。

    GLCM 统计图像中一定距离和方向上的像素对出现的概率，从而描述纹理的粗细、方向性等。
    能量反映纹理均匀程度，对比度反映局部变化强度，同质性衡量平滑度，
    相关性描述灰度线性依赖关系。本实现使用 0° 和 45° 两个方向的平均值，以获得一定旋转不变性。

    参数
    ----------
    img : numpy.ndarray
        BGR 格式的图像。

    返回
    -------
    numpy.ndarray
        长度为 4 的 GLCM 特征向量 [energy, contrast, homogeneity, correlation]。
    """
    # 灰度化并缩放到 128x128 以加速计算
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    gray = cv2.resize(gray, (128, 128), interpolation=cv2.INTER_AREA)

    # 计算距离为1，角度为 0° 和 45° 的共生矩阵，并取平均
    glcm = graycomatrix(
        gray, distances=[1], angles=[0, np.pi / 4], levels=256, symmetric=True
    )
    props = ["energy", "contrast", "homogeneity", "correlation"]
    features = []
    for prop in props:
        feat = graycoprops(glcm, prop).mean()
        features.append(feat)
    return np.array(features, dtype=np.float32)


def extract_features(img_path, kmeans_model):
    """
    从单张图片路径提取所有原始特征并拼接为完整特征向量（未经 PCA 降维处理）。

    特征组成顺序：[VLAD, HOG, 轮廓, 颜色矩, GLCM]。
    其中 VLAD 和 HOG 侧重于结构形状，轮廓提供精细的轴向比例，
    颜色矩和 GLCM 提供颜色与纹理信息。HOG 的高维部分会在主训练流程中单独进行 PCA 降维。

    参数
    ----------
    img_path : str
        图片文件路径。
    kmeans_model : sklearn.cluster.KMeans
        已训练的 VLAD 码本。

    返回
    -------
    numpy.ndarray
        拼接后的完整原始特征向量（含高维 HOG）。
    """
    # 读取图像，若失败则抛出异常
    img = cv2.imread(img_path)
    if img is None:
        raise ValueError(f"无法读取图片: {img_path}")

    # 分别提取各个子特征，最后按固定顺序拼接
    vlad = extract_sift_vlad(img, kmeans_model, max_kp=500)
    hog = extract_spm_hog(img)
    profile = extract_profile(img, profile_segments)
    color = extract_color_moments(img)
    glcm = extract_glcm(img)

    feat = np.concatenate([vlad, hog, profile, color, glcm])
    return feat.astype(np.float32)


if __name__ == "__main__":
    MODEL_DIR = "models"
    CACHE_DIR = "cache"
    os.makedirs(MODEL_DIR, exist_ok=True)
    os.makedirs(CACHE_DIR, exist_ok=True)

    overall_start = time.time()

    # ========== 数据加载 ==========
    print("========== 数据加载 ==========")
    print("训练集数据加载：")
    train_paths, train_names = load_data("data/train")
    print("\n验证集数据加载：")
    val_paths, val_names = load_data("data/valid")

    # ========== 标签编码 ==========
    # 将类别名称转换为整数标签，并持久化编码器以备后续使用
    encoder_path = os.path.join(MODEL_DIR, "label_encoder.pkl")
    if os.path.exists(encoder_path):
        print("\n========== 加载标签编码器 ==========")
        with open(encoder_path, "rb") as f:
            encoder = pickle.load(f)
        print(f"类别数: {len(encoder.classes_)}")
        print(f"类别列表: {list(encoder.classes_)}")
        print(
            f"类别映射: {dict(zip(encoder.classes_, encoder.transform(encoder.classes_)))}"
        )
        train_labels = encoder.transform(train_names)
        val_labels = encoder.transform(val_names)
    else:
        print("\n========== 训练标签编码器 ==========")
        t_start = time.time()
        encoder = LabelEncoder()
        train_labels = encoder.fit_transform(train_names)
        # transform 验证集时若出现未见类别会报错，确保数据一致性
        try:
            val_labels = encoder.transform(val_names)
        except ValueError as e:
            raise ValueError("验证集中存在训练集未包含的类别，请检查数据") from e
        with open(encoder_path, "wb") as f:
            pickle.dump(encoder, f)
        print(f"训练集类别数: {len(encoder.classes_)}")
        print(f"类别列表: {list(encoder.classes_)}")
        print(
            f"类别映射: {dict(zip(encoder.classes_, encoder.transform(encoder.classes_)))}"
        )
        print(f"[耗时] 标签编码: {time.time() - t_start:.2f} 秒")

    # ========== VLAD 码本训练 ==========
    # 训练或加载 SIFT 描述子的聚类中心（码本），用于后续 VLAD 编码
    kmeans_path = os.path.join(MODEL_DIR, "kmeans_vlad.pkl")
    if os.path.exists(kmeans_path):
        print("\n========== 加载 VLAD 码本 ==========")
        with open(kmeans_path, "rb") as f:
            kmeans = pickle.load(f)
        print(f"聚类数: {kmeans.n_clusters}")
        print(f"VLAD特征维度: {kmeans.n_clusters * 128}")
    else:
        print("\n========== 训练 VLAD 码本 ==========")
        t_start = time.time()

        # 使用 MiniBatchKMeans 进行增量聚类，适应大规模数据集
        kmeans = MiniBatchKMeans(
            n_clusters=64,
            batch_size=10000,
            random_state=42,
            n_init=3,
            max_iter=100,
        )
        sift = cv2.SIFT_create()

        processed_images = 0
        total_des_used = 0
        max_des_per_image = 500  # 限制单张图片的描述子数量，避免类别不平衡

        # 遍历训练集，提取 SIFT 描述子并逐步更新聚类模型
        for idx, path in enumerate(train_paths):
            img = cv2.imread(path)
            if img is None:
                continue
            _, des = sift.detectAndCompute(img, None)
            if des is not None and len(des) > 0:
                # 随机下采样，避免某张图片描述子过多主导聚类中心
                if len(des) > max_des_per_image:
                    indices = np.random.choice(
                        len(des), max_des_per_image, replace=False
                    )
                    des = des[indices]
                kmeans.partial_fit(des)
                processed_images += 1
                total_des_used += len(des)

            if (idx + 1) % 100 == 0 or (idx + 1) == len(train_paths):
                print(
                    f"VLAD 码本训练进度: {idx + 1}/{len(train_paths)}，"
                    f"其中 {processed_images} 张参与训练，累计增量训练 {total_des_used} 个描述子"
                )

        print("VLAD 码本训练完成")
        with open(kmeans_path, "wb") as f:
            pickle.dump(kmeans, f)
        print(f"聚类数: {kmeans.n_clusters}")
        print(f"VLAD特征维度: {kmeans.n_clusters * 128}")
        print(f"[耗时] VLAD 码本训练: {time.time() - t_start:.2f} 秒")

    # ========== 特征提取 ==========
    # 提取训练集和验证集的原始特征（含高维 HOG），并使用缓存避免重复计算
    train_cache = os.path.join(CACHE_DIR, "X_train.npy")
    val_cache = os.path.join(CACHE_DIR, "X_val.npy")
    profile_segments = 20  # 轴向轮廓曲线的垂直分段数

    # ---------- 训练集特征提取 ----------
    print("\n========== 训练集特征提取 ==========")
    if os.path.exists(train_cache):
        print("发现训练集缓存特征，直接加载...")
        X_train = np.load(train_cache)
        # 校验缓存维度是否与当前特征配置一致，防止特征代码变更后误用旧缓存
        sample_img = cv2.imread(train_paths[0])
        total_feat_dim = (
            kmeans.n_clusters * 128
            + extract_spm_hog(sample_img).shape[0]
            + profile_segments
            + 9
            + 4
        )
        if X_train.shape[1] != total_feat_dim:
            raise ValueError(
                f"训练集缓存特征维度 ({X_train.shape[1]}) 与当前特征维度 ({total_feat_dim}) 不匹配，"
                f"请删除缓存文件 {train_cache} 后重新运行"
            )
        print(f"训练集特征形状: {X_train.shape}")
    else:
        print("未找到缓存，开始提取训练集特征...")
        t_start = time.time()
        X_train = []
        total_train = len(train_paths)
        for idx, path in enumerate(train_paths):
            feat = extract_features(path, kmeans)
            X_train.append(feat)
            if (idx + 1) % 100 == 0 or (idx + 1) == total_train:
                print(f"训练集特征提取进度: {idx + 1}/{total_train}")
        X_train = np.array(X_train)
        np.save(train_cache, X_train)
        print(f"训练集特征已保存至 {train_cache}，形状: {X_train.shape}")
        print(f"[耗时] 训练集特征提取: {time.time() - t_start:.2f} 秒")

    # ---------- 验证集特征提取 ----------
    print("\n========== 验证集特征提取 ==========")
    if os.path.exists(val_cache):
        print("发现验证集缓存特征，直接加载...")
        X_val = np.load(val_cache)
        # 校验维度一致性
        sample_img = cv2.imread(train_paths[0])
        total_feat_dim = (
            kmeans.n_clusters * 128
            + extract_spm_hog(sample_img).shape[0]
            + profile_segments
            + 9
            + 4
        )
        if X_val.shape[1] != total_feat_dim:
            raise ValueError(
                f"验证集缓存特征维度 ({X_val.shape[1]}) 与当前特征维度 ({total_feat_dim}) 不匹配，"
                f"请删除缓存文件 {val_cache} 后重新运行"
            )
        print(f"验证集特征形状: {X_val.shape}")
    else:
        print("未找到缓存，开始提取验证集特征...")
        t_start = time.time()
        X_val = []
        total_val = len(val_paths)
        for idx, path in enumerate(val_paths):
            feat = extract_features(path, kmeans)
            X_val.append(feat)
            if (idx + 1) % 100 == 0 or (idx + 1) == total_val:
                print(f"验证集特征提取进度: {idx + 1}/{total_val}")
        X_val = np.array(X_val)
        np.save(val_cache, X_val)
        print(f"验证集特征已保存至 {val_cache}，形状: {X_val.shape}")
        print(f"[耗时] 验证集特征提取: {time.time() - t_start:.2f} 秒")

    y_train = np.array(train_labels)
    y_val = np.array(val_labels)

    # ========== HOG 特征主成分分析（PCA）降维 ==========
    # 对高维 HOG 特征进行 PCA 降维，解决维度灾难并平衡各特征贡献
    print("\n========== HOG 特征降维 (PCA) ==========")
    # 计算 VLAD 和 HOG 的维度，用于从完整特征中切分
    vlad_dim = kmeans.n_clusters * 128
    sample_img = cv2.imread(train_paths[0])
    hog_dim = extract_spm_hog(sample_img).shape[0]
    hog_start = vlad_dim
    hog_end = vlad_dim + hog_dim

    hog_train = X_train[:, hog_start:hog_end]
    hog_val = X_val[:, hog_start:hog_end]

    # 实际主成分数不能超过样本数和特征数，取三者最小值
    pca_components = 512  # HOG 特征经 PCA 降维后的目标主成分数
    n_components = min(pca_components, hog_train.shape[0], hog_train.shape[1])
    print(f"PCA 目标主成分数: {pca_components}，实际使用: {n_components}")

    pca_path = os.path.join(MODEL_DIR, "pca_hog.pkl")
    if os.path.exists(pca_path):
        print("加载已保存的 PCA 模型...")
        with open(pca_path, "rb") as f:
            pca = pickle.load(f)
        # 若保存的 PCA 主成分数与当前期望不符，则重新拟合
        if pca.n_components_ != n_components:
            print("PCA 主成分数不一致，重新训练...")
            pca = PCA(n_components=n_components, random_state=42)
            hog_pca_train = pca.fit_transform(hog_train)
            with open(pca_path, "wb") as f:
                pickle.dump(pca, f)
        else:
            hog_pca_train = pca.transform(hog_train)
        hog_pca_val = pca.transform(hog_val)
    else:
        print("训练 PCA 降维模型...")
        t_start = time.time()
        pca = PCA(n_components=n_components, random_state=42)
        hog_pca_train = pca.fit_transform(hog_train)
        with open(pca_path, "wb") as f:
            pickle.dump(pca, f)
        print(f"[耗时] PCA 训练: {time.time() - t_start:.2f} 秒")
        hog_pca_val = pca.transform(hog_val)

    print(f"HOG 降维后维度: {hog_pca_train.shape[1]}")

    # ---------- 拼接特征：[VLAD, PCA-HOG, 轮廓, 颜色矩, GLCM] ----------
    # 将降维后的 HOG 与 VLAD、轮廓、颜色、纹理特征重新拼接为最终特征向量
    profile_dim = profile_segments
    color_dim = 9
    glcm_dim = 4
    profile_start = hog_end
    profile_end = profile_start + profile_dim
    color_start = profile_end
    color_end = color_start + color_dim
    glcm_start = color_end
    glcm_end = glcm_start + glcm_dim

    X_train = np.concatenate(
        [
            X_train[:, :hog_start],  # VLAD 部分
            hog_pca_train,  # 降维后的 HOG
            X_train[:, profile_start:profile_end],  # 轮廓曲线
            X_train[:, color_start:color_end],  # 颜色矩
            X_train[:, glcm_start:glcm_end],  # GLCM
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

    # ========== 特征标准化 ==========
    # 对特征进行 Z-score 标准化，使各维度均值为0、标准差为1，消除量纲影响
    scaler_path = os.path.join(MODEL_DIR, "scaler.pkl")
    if os.path.exists(scaler_path):
        print("\n========== 加载标准化器 ==========")
        with open(scaler_path, "rb") as f:
            scaler = pickle.load(f)
        X_train_scaled = scaler.transform(X_train)
        X_val_scaled = scaler.transform(X_val)
        print("标准化器加载完成")
    else:
        print("\n========== 特征标准化 ==========")
        t_start = time.time()
        scaler = StandardScaler()
        X_train_scaled = scaler.fit_transform(X_train)
        X_val_scaled = scaler.transform(X_val)
        with open(scaler_path, "wb") as f:
            pickle.dump(scaler, f)
        print(f"[耗时] 特征标准化: {time.time() - t_start:.2f} 秒")

    # ========== 训练逻辑回归分类器 ==========
    model_path = os.path.join(MODEL_DIR, "lr_model.pkl")  # 改名
    if os.path.exists(model_path):
        print("\n========== 加载逻辑回归模型 ==========")
        with open(model_path, "rb") as f:
            model = pickle.load(f)
        print("模型加载完成")
    else:
        print("\n========== 训练逻辑回归 ==========")
        t_start = time.time()
        model = LogisticRegression(
            C=0.1,  # 强正则化，让决策边界更平滑开放
            class_weight="balanced",  # 自动处理类别不平衡
            max_iter=3000,
            random_state=42,
            solver="saga",  # 适合多分类 + L2 惩罚
            tol=1e-3,
            verbose=True,
        )
        model.fit(X_train_scaled, y_train)
        with open(model_path, "wb") as f:
            pickle.dump(model, f)
        print(f"[耗时] 逻辑回归训练: {time.time() - t_start:.2f} 秒")

    # ========== 验证集预测 ==========
    print("\n========== 验证集预测 ==========")
    t_start = time.time()
    y_pred = model.predict(X_val_scaled)
    print(f"[耗时] 验证集预测: {time.time() - t_start:.2f} 秒")

    # ========== 评估模型性能 ==========
    print("\n========== 评估模型性能 ==========")
    t_start = time.time()
    acc = accuracy_score(y_val, y_pred)
    print(f"验证集准确率: {acc:.4f}")
    report = classification_report(y_val, y_pred, target_names=encoder.classes_)
    print(report)
    print(f"[耗时] 性能评估: {time.time() - t_start:.2f} 秒")

    # ========== 总运行时间 ==========
    print("\n" + "=" * 50)
    print(f"所有步骤完成，总运行时间: {time.time() - overall_start:.2f} 秒")
    print(f"模型文件保存在: {MODEL_DIR}")
