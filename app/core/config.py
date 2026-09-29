"""
模块名称：全局配置

集中定义项目路径常量，供其他模块通过 `from app.core.config import ...` 使用。

约定：
- 开发态：EXTERNAL_DIR 指向项目根目录
- 打包态：EXTERNAL_DIR 指向 exe 同级目录，模型与数据集放这里
- 数据、模型、缓存从 EXTERNAL_DIR 访问
"""

import sys
from pathlib import Path


def _is_frozen():
    """返回当前是否运行在 PyInstaller 打包后的环境中。"""
    return getattr(sys, "frozen", False)


def _get_external_dir():
    """
    返回外部资源目录，用于读取模型、数据集等大文件。

    开发态：项目根目录（app/core/config.py → 上溯三级）
    打包态：exe 所在目录
    """
    if _is_frozen():
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent.parent.parent


# 外部资源目录
EXTERNAL_DIR = _get_external_dir()

# 数据与模型
DATA_DIR = EXTERNAL_DIR / "data"
MODELS_DIR = EXTERNAL_DIR / "models"

# 关键文件路径
DB_PATH = DATA_DIR / "landmark.db"
SPOTS_CSV_PATH = DATA_DIR / "spots.csv"
EMBEDDING_MODEL_PATH = MODELS_DIR / "bge-small-zh"
