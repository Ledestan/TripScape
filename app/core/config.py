"""
模块名称：全局配置

集中定义项目路径常量，供其他模块通过 `from app.core.config import ...` 使用。

约定：
- 开发态：BASE_DIR 指向项目根目录
- PyInstaller 打包后：EXTERNAL_DIR 指向 exe 所在目录，模型与数据集放这里
- 静态资源、模板打包进 exe，通过 BASE_DIR 访问
- 运行时目录（缓存、上传）在导入时自动创建
"""

import sys
from pathlib import Path


def _get_base_dir():
    """
    返回代码/资源所在目录。

    开发态：项目根目录
    打包态：PyInstaller 解压出的临时目录（sys._MEIPASS）
    """
    if getattr(sys, "frozen", False):
        return Path(sys._MEIPASS)
    return Path(__file__).resolve().parent.parent.parent


def _get_external_dir():
    """
    返回外部资源目录，用于读取模型、数据集等大文件。

    开发态：项目根目录
    打包态：exe 所在目录（模型和数据集跟 exe 放一起，不打进包内）
    """
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent.parent.parent


BASE_DIR = _get_base_dir()
EXTERNAL_DIR = _get_external_dir()

# 数据、模型、缓存放外部目录（不打进 exe）
DATA_DIR = EXTERNAL_DIR / "data"
MODELS_DIR = EXTERNAL_DIR / "models"
CACHE_DIR = EXTERNAL_DIR / "cache"
RUNTIME_DIR = EXTERNAL_DIR / "runtime"
UPLOAD_DIR = RUNTIME_DIR / "uploads"

DB_PATH = DATA_DIR / "landmark.db"
EMBEDDING_MODEL_PATH = MODELS_DIR / "bge-small-zh"
SPOTS_CSV_PATH = DATA_DIR / "spots.csv"

# 确保运行时目录存在
CACHE_DIR.mkdir(parents=True, exist_ok=True)
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
