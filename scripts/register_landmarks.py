"""行旅识景 TripScape / 地标注册图索引构建脚本
创建日期：2025-10-08

从注册图清单构建 FAISS 检索索引，完成:
    1. 读取注册图清单（scripts/db/register_images.json，外置可扩展）
    2. 每张图提取 DINOv2 全局特征（384 维）
    3. 写入 FAISS 索引 + 元数据 JSON（与索引行号对齐）

依赖:
    Python: >=3.10
    需求文件: requirements.txt
    依赖库:
        torch / faiss-cpu（同 backend/services/retrieval_engine.py）
    环境变量:
        HF_ENDPOINT    HuggingFace 镜像，默认 https://hf-mirror.com

用法（在项目根目录执行）:
    python scripts/register_landmarks.py                 # 增量注册（清单未变则跳过）
    python scripts/register_landmarks.py --list <路径>   # 指定其它清单文件
    python scripts/register_landmarks.py --force-rebuild # 忽略旧索引全部重建

可选参数:
    --list <路径>         注册图清单 JSON，默认 scripts/db/register_images.json
    --max-per-landmark N  每个地标最多注册图数，默认 40（精选图已去重，可放心多收）
    --force-rebuild       删除旧索引后全部重建

输出:
    runtime/index/landmarks.faiss        FAISS 向量索引
    runtime/index/landmarks.meta.json    元数据（target_id / path / lat / lon / reg_id）

注意:
    1. 清单与索引带指纹校验：清单内容变化后旧索引自动失效并提示重建。
    2. 新增地标：往清单加条目（或依赖 data/train 目录自动生成），重跑本脚本即可。
"""

import argparse
import hashlib
import json
import sys
import time
from pathlib import Path

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "backend"))

import os

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
os.environ.setdefault("HF_ENDPOINT", "https://hf-mirror.com")

import django

django.setup()

# ======================================================================
# 清单生成：优先精选目录，回退 data/train 采样
# ======================================================================
def build_manifest_from_dataset(max_per_landmark: int) -> list:
    """生成注册图清单。

    来源优先级：
        1. data/<类名>/ 精选目录（scripts/select_registration_images.py 产物，
           已按质量分排序 + 去重，直接全量收录，仅截取每类上限）；
        2. data/train/<类名>/ 采样（无精选目录时的回退：文件大小中位段）。
    """
    from django.conf import settings

    data_dir = Path(settings.BASE_DIR) / "data"
    train_dir = data_dir / "train"
    if not train_dir.exists():
        raise FileNotFoundError(f"数据集目录不存在: {train_dir}")

    # 类名集合：train 下的目录（精选目录类名与之相同）
    classes = sorted(d.name for d in train_dir.iterdir() if d.is_dir())
    entries = []
    for cls in classes:
        # 1) 精选目录优先
        curated = data_dir / cls
        if curated.is_dir():
            imgs = sorted(
                p for p in curated.iterdir()
                if p.suffix.lower() in (".jpg", ".jpeg", ".png")
            )
            source = "精选目录"
        else:
            # 2) train 采样回退
            class_dir = train_dir / cls
            imgs = sorted(
                (p for p in class_dir.iterdir() if p.suffix.lower() in (".jpg", ".jpeg", ".png")),
                key=lambda p: p.stat().st_size,
            )
            lo = max(0, len(imgs) // 10)
            hi = max(lo + 1, len(imgs) - len(imgs) // 10)
            imgs = imgs[lo:hi]
            source = "train 采样"
        picked = imgs[:max_per_landmark]
        print(f"  {cls:22} {len(picked):>3} 张（{source}）")
        for p in picked:
            entries.append(
                {
                    "target_id": cls,
                    "path": str(p.relative_to(ROOT)).replace("\\", "/"),
                    "lat": None,
                    "lon": None,
                }
            )
    return entries


# ======================================================================
# 索引构建
# ======================================================================
class IndexBuilder:
    """注册图特征提取与 FAISS 索引写入（产物路径集中管理）。"""

    def __init__(self, out_dir: Path):
        self.paths = {
            "faiss": str(out_dir / "landmarks.faiss"),
            "meta": str(out_dir / "landmarks.meta.json"),
            "manifest": str(out_dir / "landmarks.manifest.json"),
        }
        out_dir.mkdir(parents=True, exist_ok=True)

    # ------------------------------------------------------------------
    def _fingerprint(self, manifest: list) -> str:
        """清单指纹（内容哈希）：判断旧索引是否可复用。"""
        return hashlib.sha256(
            json.dumps(manifest, ensure_ascii=False, sort_keys=True).encode()
        ).hexdigest()[:16]

    # ------------------------------------------------------------------
    def load_or_build(self, manifest: list, force_rebuild: bool):
        """索引幂等构建：指纹一致直接复用，不一致或 --force-rebuild 重建。"""
        import faiss
        import numpy as np

        fp = self._fingerprint(manifest)
        if not force_rebuild and Path(self.paths["manifest"]).exists():
            old = json.loads(Path(self.paths["manifest"]).read_text(encoding="utf-8"))
            if old.get("fingerprint") == fp and Path(self.paths["faiss"]).exists():
                print(f"发现索引且清单未变（指纹 {fp}），直接复用；--force-rebuild 可强制重建")
                return
            print("清单已变化，旧索引失效，开始重建 ...")

        print("\n========== 提取注册图特征 ==========")
        t_start = time.time()
        from services.retrieval_engine import DinoEmbedder

        embedder = DinoEmbedder()
        feats, meta = [], []
        for i, item in enumerate(manifest, 1):
            p = ROOT / item["path"]
            if not p.exists():
                print(f"  跳过（文件不存在）: {item['path']}")
                continue
            feats.append(embedder.embed(p.read_bytes()))
            meta.append(
                {
                    "target_id": item["target_id"],
                    "path": item["path"],
                    "lat": item.get("lat"),
                    "lon": item.get("lon"),
                    "reg_id": len(meta),
                }
            )
            if i % 50 == 0 or i == len(manifest):
                print(f"特征提取进度: {i}/{len(manifest)}")

        if not feats:
            raise RuntimeError("清单中没有可用的注册图")

        print("\n========== 写入 FAISS 索引 ==========")
        dim = len(feats[0])
        index = faiss.IndexFlatIP(dim)  # 内积 = 余弦（向量已归一化）
        index.add(np.stack(feats))
        faiss.write_index(index, self.paths["faiss"])
        Path(self.paths["meta"]).write_text(
            json.dumps(meta, ensure_ascii=False, indent=1), encoding="utf-8"
        )
        Path(self.paths["manifest"]).write_text(
            json.dumps({"fingerprint": fp, "count": len(meta)}, ensure_ascii=False),
            encoding="utf-8",
        )

        print(f"索引已保存: {self.paths['faiss']}")
        print(f"元数据: {self.paths['meta']}（{len(meta)} 条）")
        print(f"[耗时] 索引构建: {time.time() - t_start:.2f} 秒")


# ======================================================================
# 命令行入口
# ======================================================================
def _parse_args(argv=None):
    parser = argparse.ArgumentParser(
        prog="python scripts/register_landmarks.py",
        description="地标注册图 FAISS 索引构建（幂等，可重复执行）。",
        epilog=(
            "示例：\n"
            "  python scripts/register_landmarks.py\n"
            "  python scripts/register_landmarks.py --max-per-landmark 12\n"
            "  python scripts/register_landmarks.py --force-rebuild\n"
        ),
    )
    parser.add_argument(
        "--list",
        default=str(ROOT / "scripts" / "db" / "register_images.json"),
        help="注册图清单 JSON，默认 scripts/db/register_images.json",
    )
    parser.add_argument(
        "--max-per-landmark", type=int, default=40, help="每地标最多注册图数，默认 40"
    )
    parser.add_argument(
        "--force-rebuild", action="store_true", help="删除旧索引后全部重建"
    )
    return parser.parse_args(argv)


def main(argv=None):
    overall_start = time.time()
    args = _parse_args(argv)

    list_path = Path(args.list)
    if list_path.exists():
        print(f"从清单加载注册图: {list_path}")
        manifest = json.loads(list_path.read_text(encoding="utf-8"))
    else:
        print("清单不存在，从 data/train 自动生成（可编辑清单后重跑以调整）")
        manifest = build_manifest_from_dataset(args.max_per_landmark)
        list_path.parent.mkdir(parents=True, exist_ok=True)
        list_path.write_text(
            json.dumps(manifest, ensure_ascii=False, indent=1), encoding="utf-8"
        )
        print(f"清单已生成: {list_path}（{len(manifest)} 张）")

    builder = IndexBuilder(ROOT / "runtime" / "index")
    builder.load_or_build(manifest, args.force_rebuild)

    print("\n" + "=" * 50)
    print(f"所有步骤完成，总运行时间: {time.time() - overall_start:.2f} 秒")


if __name__ == "__main__":
    main()
