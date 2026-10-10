"""行旅识景 TripScape
创建日期：2025-09-01

Django settings —— TripScape

- 所有配置经 django-environ 从根目录 .env 读取，未设置时使用开发默认值。
- MySQL / Redis / Celery / Qdrant / Meilisearch / MinIO / runtime 路径 /
  权限矩阵 / 置信度阈值 / 分页大小 全部集中在此。
"""

import os
from pathlib import Path

import environ

# ----------------------------------------------------------------------
# 基础路径：
#   BACKEND_DIR = backend/（Django 工程根）
#   BASE_DIR    = 仓库根（data/ models/ runtime/ frontend/ .env 都在这里）
#
# PyInstaller 冻结环境：datas 以 .py 原样拷贝，__file__ 保留打包机
# 绝对路径——必须改按 exe 实际位置解析（_internal/），否则运行期
# 读写全落在打包机目录（库建到源项目、模型读源路径）。
# ----------------------------------------------------------------------
import sys as _sys

if getattr(_sys, "frozen", False):
    BACKEND_DIR = Path(_sys.executable).resolve().parent / "_internal" / "backend"
else:
    BACKEND_DIR = Path(__file__).resolve().parent.parent.parent
BASE_DIR = BACKEND_DIR.parent

env = environ.Env(
    # ---------------- 通用 ----------------
    DJANGO_DEBUG=(bool, False),
    DJANGO_SECRET_KEY=(str, "django-insecure-tripscape-dev-key-change-me"),
    DJANGO_ALLOWED_HOSTS=(list, ["*"]),
    DJANGO_CSRF_TRUSTED_ORIGINS=(list, []),
    # ---------------- 数据库 ----------------
    DB_ENGINE=(str, "mysql"),  # mysql | sqlite（打包分发用单文件库）
    MYSQL_HOST=(str, "127.0.0.1"),
    MYSQL_PORT=(int, 3306),
    MYSQL_DB=(str, "tripscape"),
    MYSQL_USER=(str, "root"),
    MYSQL_PASSWORD=(str, "Root@123456"),
    # ---------------- Redis / Celery ----------------
    REDIS_URL=(str, "redis://127.0.0.1:6379/0"),
    CELERY_BROKER_URL=(str, "redis://127.0.0.1:6379/1"),
    CELERY_RESULT_BACKEND=(str, "redis://127.0.0.1:6379/2"),
    # ---------------- Meilisearch ----------------
    MEILI_HOST=(str, "http://127.0.0.1:7700"),
    MEILI_MASTER_KEY=(str, ""),
    # ---------------- MinIO ----------------
    MINIO_ENDPOINT=(str, "127.0.0.1:9000"),
    MINIO_ACCESS_KEY=(str, "minioadmin"),
    MINIO_SECRET_KEY=(str, "minioadmin"),
    MINIO_BUCKET=(str, "tripscape"),
    MINIO_SECURE=(bool, False),
    MINIO_PUBLIC_URL=(str, "http://127.0.0.1:9000"),
    # ---------------- runtime 目录 ----------------
    RUNTIME_DIR=(str, str(BASE_DIR / "runtime")),
    # ---------------- 模型与数据 ----------------
    EMBEDDING_MODEL_DIR=(str, str(BASE_DIR / "models" / "bge-small-zh")),
    # ---------------- 业务参数 ----------------
    QA_CONFIDENCE_THRESHOLD=(float, 0.20),
    QA_TOP_K=(int, 3),
    # 识别置信度阈值：低于此值前端展示候选列表
    RECOG_CONFIDENCE_THRESHOLD=(float, 0.35),
    # HuggingFace 镜像（DINOv2 权重下载走镜像，国内环境必需）
    HF_ENDPOINT=(str, "https://hf-mirror.com"),
    PAGE_SIZE=(int, 20),
    PAGE_SIZE_MAX=(int, 100),
    LOGIN_RATELIMIT=(str, "10/min"),
    UPLOAD_MAX_SIZE_MB=(int, 10),
    # ---------------- JWT ----------------
    JWT_SECRET=(str, "tripscape-jwt-dev-secret"),
    JWT_EXPIRE_HOURS=(int, 72),
)

# 优先读取仓库根 .env（存在即读）
environ.Env.read_env(BASE_DIR / ".env")

# ----------------------------------------------------------------------
# 安全
# ----------------------------------------------------------------------
SECRET_KEY = env("DJANGO_SECRET_KEY")
DEBUG = env("DJANGO_DEBUG")
ALLOWED_HOSTS = env("DJANGO_ALLOWED_HOSTS")
CSRF_TRUSTED_ORIGINS = env("DJANGO_CSRF_TRUSTED_ORIGINS")

# ----------------------------------------------------------------------
# 应用
# ----------------------------------------------------------------------
DJANGO_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
]

LOCAL_APPS = [
    "apps.core",
    "apps.accounts",
    "apps.landmarks",
    "apps.comments",
    "apps.journals",
    "apps.badges",
    "apps.notifications",
    "apps.search",
    "apps.shares",
    "apps.dashboard",
    "apps.admin_panel",
]

INSTALLED_APPS = DJANGO_APPS + LOCAL_APPS

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    # 自定义：请求日志 + 请求 ID
    "apps.core.middleware.RequestLogMiddleware",
]

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

ASGI_APPLICATION = "config.asgi.application"
WSGI_APPLICATION = "config.wsgi.application"

# ----------------------------------------------------------------------
# 数据库（django-environ 读取 .env）
#     DB_ENGINE=sqlite  -> runtime/tripscape.db 单文件库（演示/打包分发，
#                          收方零安装；预构建种子随包）
#     默认 mysql        -> 完整部署
# ----------------------------------------------------------------------
if env("DB_ENGINE") == "sqlite":
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": BASE_DIR / "runtime" / "tripscape.db",
        }
    }
else:
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.mysql",
            "NAME": env("MYSQL_DB"),
            "USER": env("MYSQL_USER"),
            "PASSWORD": env("MYSQL_PASSWORD"),
            "HOST": env("MYSQL_HOST"),
            "PORT": env("MYSQL_PORT"),
            "OPTIONS": {
                "charset": "utf8mb4",
            },
        }
    }

# ----------------------------------------------------------------------
# Redis / Celery
# ----------------------------------------------------------------------
REDIS_URL = env("REDIS_URL")
CELERY_BROKER_URL = env("CELERY_BROKER_URL")
CELERY_RESULT_BACKEND = env("CELERY_RESULT_BACKEND")
CELERY_ACCEPT_CONTENT = ["json"]
CELERY_TASK_SERIALIZER = "json"
CELERY_RESULT_SERIALIZER = "json"
CELERY_TIMEZONE = "Asia/Shanghai"
CELERY_TASK_TRACK_STARTED = True

# ----------------------------------------------------------------------
# Meilisearch / MinIO
# ----------------------------------------------------------------------
MEILI_HOST = env("MEILI_HOST")
MEILI_MASTER_KEY = env("MEILI_MASTER_KEY") or None
MEILI_ENABLED = True  # 服务不可用时 search 服务自动降级为 ORM

MINIO_ENDPOINT = env("MINIO_ENDPOINT")
MINIO_ACCESS_KEY = env("MINIO_ACCESS_KEY")
MINIO_SECRET_KEY = env("MINIO_SECRET_KEY")
MINIO_BUCKET = env("MINIO_BUCKET")
MINIO_SECURE = env("MINIO_SECURE")
MINIO_PUBLIC_URL = env("MINIO_PUBLIC_URL")

# ----------------------------------------------------------------------
# runtime 目录（uploads / cache / logs / tmp / backups 统一收口）
# ----------------------------------------------------------------------
RUNTIME_DIR = Path(env("RUNTIME_DIR"))
RUNTIME_UPLOADS_DIR = RUNTIME_DIR / "uploads"
RUNTIME_CACHE_DIR = RUNTIME_DIR / "cache"
RUNTIME_LOGS_DIR = RUNTIME_DIR / "logs"
RUNTIME_TMP_DIR = RUNTIME_DIR / "tmp"
RUNTIME_BACKUPS_DIR = RUNTIME_DIR / "backups"
for _d in (
    RUNTIME_DIR,
    RUNTIME_UPLOADS_DIR,
    RUNTIME_CACHE_DIR,
    RUNTIME_LOGS_DIR,
    RUNTIME_TMP_DIR,
    RUNTIME_BACKUPS_DIR,
):
    _d.mkdir(parents=True, exist_ok=True)

MEDIA_ROOT = str(RUNTIME_UPLOADS_DIR)
MEDIA_URL = "/media/"

STATIC_URL = "static/"
STATIC_ROOT = RUNTIME_CACHE_DIR / "staticfiles"

# ----------------------------------------------------------------------
# 模型与数据路径
# ----------------------------------------------------------------------
EMBEDDING_MODEL_DIR = Path(env("EMBEDDING_MODEL_DIR"))

# ----------------------------------------------------------------------
# 业务参数
# ----------------------------------------------------------------------
QA_CONFIDENCE_THRESHOLD = env("QA_CONFIDENCE_THRESHOLD")
QA_TOP_K = env("QA_TOP_K")
RECOG_CONFIDENCE_THRESHOLD = env("RECOG_CONFIDENCE_THRESHOLD")
PAGE_SIZE = env("PAGE_SIZE")
PAGE_SIZE_MAX = env("PAGE_SIZE_MAX")
LOGIN_RATELIMIT = env("LOGIN_RATELIMIT")
UPLOAD_MAX_SIZE = env("UPLOAD_MAX_SIZE_MB") * 1024 * 1024

# HuggingFace 权重下载走镜像（须在 transformers/torch.hub 首次下载前生效）
os.environ.setdefault("HF_ENDPOINT", env("HF_ENDPOINT"))

JWT_SECRET = env("JWT_SECRET")
JWT_EXPIRE_HOURS = env("JWT_EXPIRE_HOURS")

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

AUTH_USER_MODEL = "accounts.User"

AUTH_PASSWORD_VALIDATORS = [
    {
        "NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
        "OPTIONS": {"min_length": 6},
    },
]

# ----------------------------------------------------------------------
# 密码哈希：PBKDF2（安全底线：密码加密存储）
# ----------------------------------------------------------------------
PASSWORD_HASHERS = [
    "django.contrib.auth.hashers.PBKDF2PasswordHasher",
    "django.contrib.auth.hashers.PBKDF2SHA1PasswordHasher",
]

LANGUAGE_CODE = "zh-hans"
TIME_ZONE = "Asia/Shanghai"
USE_I18N = True
USE_TZ = True

# ----------------------------------------------------------------------
# 日志：RotatingFileHandler + 控制台
# ----------------------------------------------------------------------
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "verbose": {
            "format": "{asctime} {levelname} [{name}] {message}",
            "style": "{",
        },
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "verbose",
        },
        "file": {
            "class": "logging.handlers.RotatingFileHandler",
            "filename": str(RUNTIME_LOGS_DIR / "tripscape.log"),
            "maxBytes": 10 * 1024 * 1024,
            "backupCount": 5,
            "encoding": "utf-8",
            "formatter": "verbose",
        },
    },
    "root": {
        "handlers": ["console", "file"],
        "level": "INFO",
    },
    "loggers": {
        "django.db.backends": {
            "level": "WARNING",
            "handlers": ["file"],
            "propagate": False,
        },
        "tripscape": {
            "level": "DEBUG",
            "handlers": ["console", "file"],
            "propagate": False,
        },
    },
}

# ----------------------------------------------------------------------
# Django Ninja（接口文档自动生成在 /api/docs）
# ----------------------------------------------------------------------
