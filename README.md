# TripScape（行旅识景：世界著名地标智能识别）

集地标图像识别、智能问答、足迹打卡图鉴于一体的交互平台，用户上传照片即可识别地标并获取百科信息，输入问题可获得 RAG 检索问答，打卡地标在地球上可视化旅行足迹。

---

## 目录

- [功能特性](#功能特性)
- [快速开始](#快速开始)
- [文件架构](#文件架构)
- [运行方式](#运行方式)
- [API 说明](#api-说明)
- [数据集](#数据集)
- [支持库](#支持库)
- [作者与许可证](#作者与许可证)

---

## 功能特性

- **地标识别**：上传图片，基于 SIFT-VLAD + HOG + 轮廓 + 颜色矩 + GLCM 多特征融合，配合多尺度贝叶斯滑动窗口分类，返回地标名称与置信度。
- **智能问答**：基于本地知识库的 RAG 检索问答，向量检索 + BM25 混合策略，支持复合问题自动拆分与合并。
- **足迹打卡**：在渲染的地球上点击地标光点打卡，支持聚焦、取消打卡、可视化旅行足迹。

---

## 快速开始

```bash
# 安装依赖
pip install -r requirements.txt

# 启动服务
python run.py
```

- 访问 **[http://127.0.0.1:5000](http://127.0.0.1:5000)**

> 首次运行需要确保 `data/landmark.db`、`models/*.pkl`、`models/bge-small-zh/` 已就绪。
> 数据库缺失时，先运行 `python scripts/init_db.py` 从 SQL 重建；
> 模型文件缺失时，先运行 `python scripts/train.py` 训练地标识别模型；
> 向量模型缺失时，需从 HuggingFace 下载 `bge-small-zh` 到 `models/` 目录。

---

## 文件架构

```text
TripScape/
├─ app/                             # 应用源码包
│  ├─ __init__.py                   # 应用工厂
│  ├─ core/                         # 核心配置与基础设施
│  │  ├─ __init__.py
│  │  ├─ config.py                  # 全局路径常量
│  │  └─ db.py                      # SQLite 访问层
│  ├─ routes/                       # Flask 路由层
│  │  ├─ __init__.py
│  │  ├─ main.py                    # 页面路由
│  │  ├─ qa.py                      # 问答 API
│  │  ├─ recognition.py             # 识别 API
│  │  └─ footprint.py               # 足迹 API
│  ├─ services/                     # 业务逻辑层
│  │  ├─ __init__.py                # 对外导出
│  │  ├─ image_recognizer.py        # 地标识别
│  │  └─ qa_engine.py               # RAG 问答
│  ├─ static/                       # 前端静态资源
│  │  └─ images/
│  │      └─ earth.png              # 地球贴图
│  └─ templates/                    # 网页模板
│     ├─ index.html                 # 首页
│     └─ app.html                   # 功能主页
├─ data/                            # 数据集与数据库
│  ├─ landmark.db                   # SQLite 数据库
│  ├─ spots.csv                     # 地标经纬度坐标
│  ├─ train/                        # 训练集
│  └─ valid/                        # 验证集
├─ models/                          # 模型文件
│  ├─ label_encoder.pkl             # 标签编码器（训练产物）
│  ├─ kmeans_vlad.pkl               # VLAD 码本（训练产物）
│  ├─ pca_hog.pkl                   # HOG PCA 降维模型（训练产物）
│  ├─ scaler.pkl                    # 特征标准化器（训练产物）
│  ├─ lr_model.pkl                  # 逻辑回归分类器（训练产物）
│  └─ bge-small-zh/                 # 中文向量模型（RAG 用，需单独下载）
├─ scripts/                         # 独立脚本
│  ├─ init_db.py                    # 数据库初始化脚本
│  ├─ train.py                      # 地标识别模型训练脚本
│  └─ db/                           # 数据库初始化 SQL
│     ├─ init_sqlite.sql            # 建表与索引
│     ├─ heritage_items.sql         # 地标基础数据
│     └─ knowledge_base.sql         # 知识库问答数据
├─ cache/                           # 特征缓存（X_train.npy、X_val.npy）
├─ .gitignore                       # git 推送忽略文件
├─ LICENSE                          # Apache-2.0 原文
├─ README.md                        # 项目说明
├─ requirements.txt                 # 依赖清单
└─ run.py                           # 启动入口
```

### 各目录职责

| 目录               | 职责                                   |
| ------------------ | -------------------------------------- |
| `app/`           | Web 应用源码包                         |
| `app/core/`      | 配置与基础设施（路径常量、数据库访问） |
| `app/routes/`    | 路由层，只做参数校验与转发             |
| `app/services/`  | 业务逻辑层（识别、问答）               |
| `app/static/`    | 前端资源                               |
| `app/templates/` | 前端模板                               |
| `data/`          | 数据集与数据库                         |
| `models/`        | 模型文件                               |
| `scripts/`       | 独立脚本（数据库初始化、模型训练）     |
| `cache/`         | 特征缓存（训练产物）                   |

### 模块依赖关系

```text
run.py
  └─ app.create_app()
       ├─ app.routes.main         →  templates/
       ├─ app.routes.qa           →  app.services.QASystem
       │                                └─ app.services.qa_engine
       │                                     └─ app.core.config
       ├─ app.routes.recognition  →  app.services.ImageRecognizer
       │                                └─ app.services.image_recognizer
       │                                     ├─ app.core.config
       │                                     └─ app.core.db
       └─ app.routes.footprint    →  app.core.config（读 spots.csv）

scripts/init_db.py
  ├─ app.core.config
  └─ scripts/db/*.sql

scripts/train.py
  ├─ app.core.config
  └─ app.services.image_recognizer.FeatureExtractor
       （训练与推理共用同一套特征管线，避免漂移）
```

---

## 运行方式

```bash
# 初始化数据库（首次运行前执行一次）
python scripts/init_db.py
python scripts/init_db.py --force-rebuild   # 删掉旧库重建

# 训练地标识别模型（从项目根目录执行）
python scripts/train.py
python scripts/train.py --force-rebuild
python scripts/train.py --n-clusters 128 --pca-components 256

# 启动 Web 服务
python run.py

# 识别单张图片（以模块方式运行）
python -m app.services.image_recognizer test.jpg
python -m app.services.image_recognizer test.jpg 5
python -m app.services.image_recognizer test.jpg --no-bayes

# 命令行问答
python -m app.services.qa_engine "埃菲尔铁塔有多高？"
python -m app.services.qa_engine "天坛用途和门票" --top-k 5
```

---

## API 说明

### POST /api/chat

问答接口。

**请求**：JSON

```json
{"question": "埃菲尔铁塔有多高？"}
```

**响应**：JSON

```json
{"answer": "...", "source": "rag"}
```

**错误**：`400` 问题为空；`500` 服务器内部错误。

---

### POST /api/recognize

地标图像识别接口。

**请求**：`multipart/form-data`，字段名 `image`

- 支持格式：PNG、JPG、JPEG
- 大小限制：2MB

**响应**：JSON

```json
{
  "success": true,
  "target_id": "eiffeltower",
  "name": "埃菲尔铁塔",
  "confidence": 0.87,
  "confidence_percent": "87.0%"
}
```

**错误**：`400` 未上传图片 / 格式不支持 / 超过大小限制；`500` 识别失败。

---

### GET /api/spots

返回所有地标坐标，供前端地图渲染。

**响应**：JSON

```json
{
  "success": true,
  "data": [
    {"name": "埃菲尔铁塔", "lat": 48.858, "lon": 2.294},
    {"name": "长城", "lat": 40.358, "lon": 116.024}
  ]
}
```

---

### GET /api/footprint/

获取用户足迹列表（占位接口）。

**响应**：JSON

```json
{"success": true, "data": []}
```

---

## 数据集

### 来源

Kaggle 地标图像数据集

### 结构

- `data/train/` — 训练集，按地标名分目录
- `data/valid/` — 验证集，目录结构与 `train` 一致

### 类别

共 26 类地标：

| 目录名            | 地标中文名       |
| ----------------- | ---------------- |
| AbuSimbelTemples  | 阿布辛贝神庙     |
| AngelFalls        | 安赫尔瀑布       |
| BentPyramid       | 弯曲金字塔       |
| BurjKhalifa       | 哈利法塔         |
| ChichenItza       | 奇琴伊察         |
| ChristTheRedeemer | 救世基督像       |
| DjoserPyramid     | 左塞尔金字塔     |
| EiffelTower       | 埃菲尔铁塔       |
| GizaPyramids      | 吉萨金字塔群     |
| GreatWall         | 长城             |
| HatshepsutTemples | 哈特谢普苏特神庙 |
| HeavenTemple      | 天坛             |
| Huangguoshu       | 黄果树瀑布       |
| Leifeng           | 雷峰塔           |
| LibertyStatue     | 自由女神像       |
| MachuPicchu       | 马丘比丘         |
| MemnonColossi     | 门农巨像         |
| Petra             | 佩特拉           |
| Potala            | 布达拉宫         |
| Qomolangma        | 珠穆朗玛峰       |
| Ramesseum         | 拉美西姆神庙     |
| RomanColosseum    | 罗马斗兽场       |
| Sphinx            | 狮身人面像       |
| Stonehenge        | 巨石阵           |
| TajMahal          | 泰姬陵           |
| ThreePagodas      | 崇圣寺三塔       |

### 许可

仅用于学习与研究，不得商用。详见原始数据集页面。

---

## 支持库

### 运行环境

- Python 3.10+
- 操作系统：Windows / macOS / Linux

### Web 框架

| 包名  | 用途           |
| ----- | -------------- |
| Flask | Web 服务与路由 |

### 图像识别

| 包名          | 用途                                    |
| ------------- | --------------------------------------- |
| opencv-python | SIFT 特征提取、图像读写                 |
| scikit-image  | HOG、GLCM 纹理特征                      |
| scikit-learn  | KMeans、PCA、逻辑回归、标准化、标签编码 |
| numpy         | 数值计算                                |
| scipy         | 矢量量化 vq                             |

### 问答系统

| 包名                  | 用途           |
| --------------------- | -------------- |
| faiss-cpu             | 向量索引与检索 |
| sentence-transformers | 文本编码       |
| jieba                 | 中文分词       |

### 完整依赖清单

见根目录 `requirements.txt`。

---

## 作者与许可证

- **作者**：Tingchu
- **许可证**：Apache License 2.0
- **欢迎参考与学习**：你可以自由地使用、复制、修改和分发本项目的代码，包括用于个人学习、学术研究或商业用途。使用前请阅读并遵守 Apache-2.0 许可证。
- **使用要求**：
  - **保留声明**：分发软件副本或衍生作品时，必须保留原始版权声明、许可声明，并附上 Apache-2.0 许可证副本。
  - **修改声明**：如修改了源文件，需在修改后的文件中显著标明“已修改”。
  - **专利与商标**：Apache-2.0 授予相应专利许可；但若你对本项目发起专利诉讼，相关专利许可将终止。该许可证不授予商标、商号或服务标志使用权，不得以作者或项目名义进行背书。
  - **免责声明**：本软件按“原样”提供，不提供任何明示或暗示担保。作者及贡献者不对因使用或无法使用本软件而产生的任何索赔、损害或其他责任负责。具体以 [`LICENSE`](LICENSE) 文件为准。

> 以上为便于阅读的摘要，不替代 Apache-2.0 正式条款。若摘要与 `LICENSE` 冲突，以 `LICENSE` 为准。
