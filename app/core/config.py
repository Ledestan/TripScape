"""
模块名称：全局配置

集中定义项目路径常量，供其他模块通过 `from app.core.config import ...` 使用。

约定：
- 所有路径均为 pathlib.Path 绝对路径，基于项目根目录计算
- 运行时目录（缓存、上传）在导入时自动创建
- 数据、模型、数据库路径统一在此定义，禁止在业务代码里写相对路径
"""

from pathlib import Path

# 项目根目录：app/core/config.py → 上溯三级到 TripScape/
BASE_DIR = Path(__file__).resolve().parent.parent.parent

DATA_DIR = BASE_DIR / "data"
MODELS_DIR = BASE_DIR / "models"
CACHE_DIR = BASE_DIR / "cache"

DB_PATH = DATA_DIR / "landmark.db"
EMBEDDING_MODEL_PATH = MODELS_DIR / "bge-small-zh"
SPOTS_CSV_PATH = DATA_DIR / "spots.csv"

# 确保运行时目录存在
CACHE_DIR.mkdir(parents=True, exist_ok=True)
