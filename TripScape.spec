# -*- mode: python ; coding: utf-8 -*-
# 行旅识景 TripScape 打包配置
# 用法：pyinstaller TripScape.spec
# 产物：dist/TripScape/TripScape.exe（目录式，携带后端/前端/数据/模型）

import os

block_cipher = None

# 数据清单：源 -> 目标（相对 exe 目录）
datas = [
    # Django 后端（代码 + 迁移 + 种子命令）
    ("backend", "backend"),
    # 前端构建产物（SPA 由 Django 直接服务）
    ("frontend/dist", "frontend/dist"),
    # 前端静态资源（地球贴图/星空/百科图，SPA 引用 /landmarks/... 等）
    ("frontend/public", "frontend/public"),
    # 精选注册图（识别索引源）
    ("data", "data"),
    # bge 向量模型（问答索引）
    ("models", "models"),
    # 预构建的识别/问答索引（免用户本地重建）
    ("runtime/index", "runtime/index"),
    # 种子数据（首启自动建库导入）
    ("scripts/db", "scripts/db"),
    # .env 不入包：desktop.py 首启自动生成 sqlite 配置（避免密码打包泄露）
]

a = Analysis(
    ["desktop.py"],
    pathex=["."],
    binaries=[],
    datas=datas,
    hiddenimports=[
        # Django 应用（PyInstaller 静态分析发现不了的动态导入）
        "apps.accounts",
        "apps.landmarks",
        "apps.comments",
        "apps.journals",
        "apps.badges",
        "apps.notifications",
        "apps.shares",
        "apps.search",
        "apps.dashboard",
        "apps.admin_panel",
        "apps.core",
        # settings 依赖（动态导入）
        "environ",
        # Django Ninja 及其依赖（security 等子模块为动态导入）
        "ninja",
        "ninja.security",
        "ninja.main",
        "ninja.params",
        "ninja.constants",
        "ninja.compatibility",
        "ninja.utils",
        "ninja.errors",
        "ninja.responses",
        "ninja.operation",
        "ninja.router",
        "pydantic",
        "pytz",
        # 服务层（惰性 import）
        "services.retrieval_engine",
        "services.article_qa",
        "services.recognition_service",
        # MySQL / celery 后端
        "MySQLdb",
        "celery",
        # 识别与问答依赖
        "faiss",
        "torch",
        "torchvision",
        "sentence_transformers",
        "transformers",
        "transformers.models.bert",
        "jieba",
        "opencc",
        "cv2",
        "rank_bm25",
        # 模板引擎
        "django.template.loaders",
        # pywebview Windows 后端
        "webview.platforms.winforms",
        "webview.platforms.edgechromium",
    ],
    hookspath=["hooks"],
    hooksconfig={
        # torch 全家以源码形态落地（inspect.getsource 需要真 .py 文件；
        # PYZ 字节码形态下 torch.distributed.config 等必炸）
        "torch": {"module_collection_mode": "source"},
        "torchvision": {"module_collection_mode": "source"},
        "transformers": {"module_collection_mode": "source"},
        "sentence_transformers": {"module_collection_mode": "source"},
    },
    runtime_hooks=[],
    excludes=[
        # 减体积：不用的大模块
        "tkinter",
        "matplotlib",
        "pandas",
        "IPython",
        "jupyter",
        "pytest",
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="TripScape",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,          # 无控制台窗口（桌面应用）
    disable_windowed_traceback=False,
    icon=None,              # 无自定义图标；有 ico 放项目根并改为 icon="app.ico"
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name="TripScape",
)
