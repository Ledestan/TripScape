# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller 打包配置。

用法：
    pyinstaller TripScape.spec --noconfirm --clean

打包结果：
    dist/TripScape/TripScape.exe
"""

from PyInstaller.utils.hooks import (
    collect_submodules,
    collect_data_files,
    collect_dynamic_libs,
)

# ---- 收集第三方库的子模块和资源 ----
hiddenimports = []
hiddenimports += collect_submodules("sklearn")
hiddenimports += collect_submodules("skimage")
hiddenimports += collect_submodules("sentence_transformers")
hiddenimports += collect_submodules("transformers")
hiddenimports += collect_submodules("jieba")
hiddenimports += [
    "sklearn.utils._typedefs",
    "sklearn.neighbors._partition_nodes",
    "scipy.special._cdflib",
    "scipy._lib.messagestream",
]

datas = []
datas += collect_data_files("jieba")
datas += collect_data_files("sentence_transformers")
datas += collect_data_files("transformers")

binaries = []
binaries += collect_dynamic_libs("cv2")
binaries += collect_dynamic_libs("faiss")

a = Analysis(
    ["desktop.py"],
    pathex=[],
    binaries=binaries,
    datas=datas + [
        ("app/static", "app/static"),
        ("app/templates", "app/templates"),
    ],
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=["matplotlib", "tkinter", "PyQt5", "PyQt6", "PySide2", "PySide6"],
    noarchive=False,
)

pyz = PYZ(a.pure)

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
    console=False,          # 不显示控制台窗口
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
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
