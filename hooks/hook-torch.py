"""PyInstaller hook：收集 torch 全家（DLL/数据/子模块）。"""

from PyInstaller.utils.hooks import collect_all, collect_submodules

binaries, datas, hiddenimports = [], [], []
for pkg in ("torch", "torchvision", "transformers", "sentence_transformers"):
    b, d, h = collect_all(pkg)
    binaries += b
    datas += d
    hiddenimports += h

hiddenimports += collect_submodules("torch.distributed")
