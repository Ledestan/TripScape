"""识别索引自评（A4 技术可信度证据）。

用途：给出**可复现、可核对**的识别管线自评数字，而不是"效果很好"这类无证据声明。

做法（诚实说明局限，数字全部由脚本实测写出）：
    1. 从 data/<target_id>/ 按文件名排序取第 1 张（每个地标 1 张，共 26 张）；
    2. 逐张调用 services/retrieval_engine.get_engine().predict()；
    3. 统计 top-1 命中率、置信度分布、单图耗时；
    4. **同时统计评测图与索引注册图的重合数**（runtime/index/landmarks.meta.json），
       因为索引可能是旧批次构建的：重合越少，越接近"留出集"，但仍不是泛化评测。
    报告里显式写出重合数、索引路径缺失数，避免把"自评"说成"泛化"。

用法:
    $env:DB_ENGINE='sqlite'
    .venv\\Scripts\\python.exe scripts/recognition_selfcheck.py

产物:
    docs/competition/evidence/a4-recognition-selfcheck.json
"""

import json
import os
import statistics
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "backend"))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
os.environ.setdefault("DB_ENGINE", "sqlite")

import django  # noqa: E402

django.setup()

from apps.landmarks.models import Landmark  # noqa: E402
from services.retrieval_engine import get_engine  # noqa: E402

DATA = ROOT / "data"
OUT = ROOT / "docs" / "competition" / "evidence" / "a4-recognition-selfcheck.json"


def main():
    t_load = time.time()
    engine = get_engine()
    load_seconds = round(time.time() - t_load, 1)
    if engine is None:
        raise SystemExit("识别索引不可用，先运行 scripts/register_landmarks.py")

    meta = json.loads((ROOT / "runtime" / "index" / "landmarks.meta.json").read_text(encoding="utf-8"))
    meta_names = {Path(item.get("path", "")).name for item in meta}
    meta_missing = sum(1 for item in meta if not (ROOT / item.get("path", "")).is_file())

    rows = []
    started = time.time()
    for lm in Landmark.objects.all().order_by("id"):
        folder = DATA / lm.target_id
        if not folder.is_dir():
            continue
        images = sorted(p for p in folder.iterdir() if p.suffix.lower() in (".jpg", ".jpeg", ".png"))
        if not images:
            continue
        image = images[0]
        t0 = time.time()
        results = engine.predict(image.read_bytes(), top_k=3) or []
        elapsed_ms = int((time.time() - t0) * 1000)
        top1 = results[0][0] if results else None
        rows.append(
            {
                "landmark_id": lm.id,
                "target_id": lm.target_id,
                "image": image.name,
                "in_index": image.name in meta_names,
                "top1": top1,
                "hit": (top1 or "").lower() == lm.target_id.lower(),
                "confidence": round(float(results[0][1]), 6) if results else None,
                "top3": [t for t, _ in results],
                "elapsed_ms": elapsed_ms,
            }
        )

    total = len(rows)
    hits = sum(1 for r in rows if r["hit"])
    confidences = sorted(r["confidence"] for r in rows if r["confidence"] is not None)
    elapsed = sorted(r["elapsed_ms"] for r in rows)
    overlap = sum(1 for r in rows if r["in_index"])

    def bucket(lo, hi):
        return sum(1 for c in confidences if lo <= c < hi)

    report = {
        "artifact": "A4-recognition-selfcheck",
        "protocol": (
            "每地标取 data/<target_id>/ 下按文件名排序的第 1 张，共 26 张；"
            "其中与索引注册图重名的张数与索引路径缺失数见 eval/ index 两节。"
            "本报告是跨批次自评（部分图为索引外照片），不构成泛化准确率声明。"
        ),
        "index": {
            "manifest": json.loads((ROOT / "runtime" / "index" / "landmarks.manifest.json").read_text(encoding="utf-8")),
            "registered_images": len(meta),
            "meta_paths_missing_on_disk": meta_missing,
        },
        "engine_load_seconds": load_seconds,
        "evaluated": total,
        "evaluated_in_index": overlap,
        "evaluated_out_of_index": total - overlap,
        "top1_hits": hits,
        "top1_rate": round(hits / total, 4) if total else None,
        "confidence": {
            "min": confidences[0] if confidences else None,
            "median": round(statistics.median(confidences), 6) if confidences else None,
            "max": confidences[-1] if confidences else None,
            "buckets": {
                "<0.35": bucket(0.0, 0.35),
                "0.35-0.70": bucket(0.35, 0.70),
                ">=0.70": bucket(0.70, 1.0001),
            },
        },
        "elapsed_ms": {
            "first": rows[0]["elapsed_ms"] if rows else None,
            "min": elapsed[0] if elapsed else None,
            "median": int(statistics.median(elapsed)) if elapsed else None,
            "max": elapsed[-1] if elapsed else None,
        },
        "thresholds": {"RECOG_CONFIDENCE_THRESHOLD_source": "backend/config/settings/base.py"},
        "elapsed_seconds": round(time.time() - started, 1),
        "caveat": (
            "评测图与索引注册图只部分重合；每类仅 1 张、无对抗样本，"
            "不得作为对外准确率或泛化能力声明。"
        ),
        "rows": rows,
    }

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"written: {OUT.relative_to(ROOT)}")
    print(
        json.dumps(
            {
                k: report[k]
                for k in ("evaluated", "evaluated_in_index", "top1_hits", "top1_rate", "confidence", "elapsed_ms", "engine_load_seconds")
            },
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
