"""行旅识景 TripScape / 补充图整理脚本
创建日期：2025-10-08

整理用户手工补充的地标图片，完成:
    1. webp/png 等格式统一转 jpg（质量 92）
    2. 格式化命名：<地标英文ID>_<三位序号>.jpg（跳过已是该格式的）
    3. 从新补充图中选出尺寸达标的（最短边 >= 500px，与精品门槛一致），
       替换到精选目录 data/<类名>/（同名覆盖旧图）

依赖:
    Python: >=3.10
    需求文件: requirements.txt
    依赖库:
        opencv-python-headless（cv2 读写，自动处理 webp/png/bmp）

用法（在项目根目录执行）:
    python scripts/organize_supplement.py                # 转换 + 命名 + 选优替换
    python scripts/organize_supplement.py --dry-run      # 只报告不动文件

可选参数:
    --min-side N    替换门槛的最短边，默认 500（与注册图精品档一致）
    --dry-run       只报告不执行

注意:
    1. 处理对象：data/<类名>/ 下所有非标准命名的图片（用户手工放入的）。
    2. 标准命名 <ID>_<序号>.jpg 且尺寸达标的直接参与"替换展示图"评选，
       不达标的移入 data/_rejected/supplement/。
    3. 替换 = 用新图覆盖精选目录里同名文件（序号顺延，不与现存冲突）。
"""

import argparse
import re
import shutil
import sys
import time
from pathlib import Path

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parent.parent

import cv2

# 类名（target_id）正则：大写开头的驼峰
TID_RE = re.compile(r"^[A-Z][A-Za-z0-9]*$")


def to_jpg(src: Path, quality: int = 92) -> Path:
    """任意格式转 jpg（同目录同名 .jpg），成功后删源文件。"""
    img = cv2.imread(str(src), cv2.IMREAD_COLOR)
    if img is None:
        return None
    dst = src.with_suffix(".jpg")
    cv2.imwrite(str(dst), img, [cv2.IMWRITE_JPEG_QUALITY, quality])
    src.unlink()
    return dst


def next_index(cls_dir: Path, tid: str) -> int:
    """该类现存 <tid>_N.jpg 的最大序号 + 1。"""
    mx = 0
    for p in cls_dir.glob(f"{tid}_*.jpg"):
        m = re.match(rf"{tid}_(\d+)\.jpg$", p.name)
        if m:
            mx = max(mx, int(m.group(1)))
    return mx + 1


def shortest_side(p: Path) -> int:
    img = cv2.imread(str(p))
    if img is None:
        return 0
    h, w = img.shape[:2]
    return min(h, w)


def process(dry_run: bool, min_side: int):
    data = ROOT / "data"
    skip = {"train", "_rejected", "_pending", "valid"}
    rej_root = data / "_rejected" / "supplement"

    converted = renamed = replaced = small = 0
    for cls_dir in sorted(data.iterdir()):
        if not cls_dir.is_dir() or cls_dir.name in skip or not TID_RE.match(cls_dir.name):
            continue
        tid = cls_dir.name
        files = sorted(f for f in cls_dir.iterdir() if f.suffix.lower() in (".webp", ".png", ".bmp", ".jpg", ".jpeg"))

        for f in files:
            # 只处理手工补充的（非标准命名）；已审定的 <tid>_N.jpg 一律不动
            if re.match(rf"{tid}_\d+\.jpg$", f.name):
                continue

            # 1. 格式转换
            if f.suffix.lower() != ".jpg":
                if dry_run:
                    print(f"  [DRY] {tid}/{f.name} -> 转 jpg")
                    converted += 1
                    continue
                nf = to_jpg(f)
                if nf is None:
                    print(f"  [跳过] {tid}/{f.name} 无法读取")
                    continue
                f = nf
                converted += 1

            # 2. 命名格式化：<tid>_<序号>.jpg（顺延不冲突）
            if dry_run:
                print(f"  [DRY] {tid}/{f.name} -> {tid}_N.jpg")
                renamed += 1
                continue
            n = next_index(cls_dir, tid)
            target = cls_dir / f"{tid}_{n}.jpg"
            f = f.rename(target)
            renamed += 1

            # 3. 尺寸评选：达标留精选（就是展示图一员），不足移 _rejected/supplement
            side = shortest_side(f)
            if side < min_side:
                rej_root.mkdir(parents=True, exist_ok=True)
                (rej_root / tid).mkdir(exist_ok=True)
                shutil.move(str(f), rej_root / tid / f.name)
                small += 1
            else:
                replaced += 1

    print(f"\n转换 {converted} | 重命名 {renamed} | 达标入选 {replaced} | 尺寸不足隔离 {small}")
    if not dry_run:
        print("完成后重跑 scripts/topup_registration_images.py --pending 可继续补缺")


def main():
    parser = argparse.ArgumentParser(prog="python scripts/organize_supplement.py", description="整理手工补充图（转 jpg + 规范命名 + 尺寸评选）")
    parser.add_argument("--min-side", type=int, default=500, help="达标最短边，默认 500")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    process(args.dry_run, args.min_side)


if __name__ == "__main__":
    main()
