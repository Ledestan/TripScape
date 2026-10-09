"""行旅识景 TripScape / 展示图更换脚本
创建日期：2025-10-08

从每类精选注册图中选一张最佳作为地标展示图（百科图），完成:
    1. 每类 15 张中按综合分评选（清晰度 60% + 对比度 20% + 构图居中 20%）
    2. 缩放到统一规格（长边 1200px，质量 88，控制体积）
    3. 覆盖 frontend/public/landmarks/<tid>.jpg

依赖:
    Python: >=3.10
    需求文件: requirements.txt
    依赖库:
        opencv-python-headless
        numpy>=1.26

用法（在项目根目录执行）:
    python scripts/update_showcase_images.py             # 全部 26 类
    python scripts/update_showcase_images.py --dry-run   # 只报告每类会选哪张

注意:
    1. 展示图用于地标详情/搜索缩略图；注册索引不受影响。
    2. 前端构建后生效（Django 直接服务 public/ 下的静态图）。
"""

import argparse
import sys
import time
from pathlib import Path

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parent.parent

import cv2
import numpy as np

DATA = ROOT / "data"
DEST = ROOT / "frontend" / "public" / "landmarks"
SKIP = {"train", "_rejected", "_pending", "valid"}
MAX_LONG = 1200


def quality_metrics(p: Path) -> dict:
    img = cv2.imread(str(p))
    if img is None:
        return {"sharp": 0, "contrast": 0, "center": 0, "img": None}
    g = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    gs = cv2.resize(g, (512, 512))
    sharp = cv2.Laplacian(gs, cv2.CV_64F).var()

    # 构图居中：中央 40% 区域的边缘密度（主体居中的图中央细节丰富）
    gx = cv2.Sobel(gs, cv2.CV_32F, 1, 0)
    gy = cv2.Sobel(gs, cv2.CV_32F, 0, 1)
    mag = np.sqrt(gx * gx + gy * gy)
    c = mag.shape[0] * 3 // 10
    center = mag[c:-c, c:-c].mean()

    return {"sharp": float(sharp), "contrast": float(gs.std()), "center": float(center), "img": img}


def pick_and_write(cls_dir: Path, tid: str, dry_run: bool) -> str:
    files = sorted(cls_dir.glob(f"{tid}_*.jpg"))
    if not files:
        return "无图"

    metas = [(p, quality_metrics(p)) for p in files]
    metas = [(p, m) for p, m in metas if m["img"] is not None]
    if not metas:
        return "全部无法读取"

    # 类内分位归一后加权
    def pct(arr):
        a = np.array(arr)
        return a.argsort().argsort() / max(len(a) - 1, 1)

    scores = (
        0.6 * pct([m["sharp"] for _, m in metas])
        + 0.2 * pct([m["contrast"] for _, m in metas])
        + 0.2 * pct([m["center"] for _, m in metas])
    )
    best_i = int(np.argmax(scores))
    best_p, best_m = metas[best_i]

    if dry_run:
        return f"{best_p.name}（清晰 {best_m['sharp']:.0f}）"

    # 缩放写出到前端静态目录
    img = best_m["img"]
    h, w = img.shape[:2]
    long_side = max(h, w)
    if long_side > MAX_LONG:
        scale = MAX_LONG / long_side
        img = cv2.resize(img, (int(w * scale), int(h * scale)), interpolation=cv2.INTER_AREA)
    DEST.mkdir(parents=True, exist_ok=True)
    cv2.imwrite(str(DEST / f"{tid}.jpg"), img, [cv2.IMWRITE_JPEG_QUALITY, 88])
    return f"{best_p.name}（清晰 {best_m['sharp']:.0f}）-> landmarks/{tid}.jpg"


def main():
    parser = argparse.ArgumentParser(prog="python scripts/update_showcase_images.py", description="从精选图评选并更新地标展示图")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    t0 = time.time()
    print("\n========== 展示图评选与更换 ==========")
    if args.dry_run:
        print("模式: DRY-RUN")
    done = 0
    for cls_dir in sorted(DATA.iterdir()):
        if not cls_dir.is_dir() or cls_dir.name in SKIP:
            continue
        import re

        if not re.match(r"^[A-Z][A-Za-z0-9]*$", cls_dir.name):
            continue
        result = pick_and_write(cls_dir, cls_dir.name, args.dry_run)
        print(f"  {cls_dir.name:22} {result}")
        done += 1

    print(f"\n处理 {done} 类 | [耗时] {time.time() - t0:.2f} 秒")
    if not args.dry_run:
        print("展示图已更新至 frontend/public/landmarks/（前端构建后生效）")


if __name__ == "__main__":
    main()
