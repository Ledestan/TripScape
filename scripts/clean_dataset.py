"""行旅识景 TripScape / 数据集图片清洗脚本
创建日期：2025-10-08

清洗 data/train 下各地标文件夹中的低质量图片，完成:
    1. 拉普拉斯方差检测模糊（方差低于阈值 = 对焦差/运动模糊）
    2. 最短边分辨率检测（低于阈值 = 分辨率不足）
    3. 灰度方差检测纯色/近纯色图（截图残片、空白图）
    4. 极端宽高比检测（拼接长图、条幅图）
    5. 低质量图移动到 data/_rejected/<地标名>/ 隔离（不直接删除，人工复核后可整体删）

依赖:
    Python: >=3.10
    需求文件: requirements.txt
    依赖库:
        opencv-python>=4.10    # 拉普拉斯方差与图像统计
        numpy>=1.26

用法（在项目根目录执行）:
    python scripts/clean_dataset.py                     # 默认清洗 data/train
    python scripts/clean_dataset.py --dry-run           # 只报告不移动
    python scripts/clean_dataset.py --min-side 200      # 提高分辨率门槛

可选参数:
    --data-dir <目录>     数据集根目录，默认 data/train
    --reject-dir <目录>   隔离目录，默认 data/_rejected
    --min-side N          最短边像素下限，默认 128
    --blur-threshold F    拉普拉斯方差下限，默认 60.0（越小越宽容）
    --dry-run             只检测并报告，不移动文件

输出:
    终端报告每类的清洗统计；被拒图片移至 data/_rejected/<地标名>/

注意:
    1. 隔离不删除：复核确认后手动删 data/_rejected 即可，误杀可移回。
    2. 清洗后需重跑 scripts/register_landmarks.py（注册图清单可能变化）。
"""

import argparse
import shutil
import sys
import time
from pathlib import Path

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parent.parent

import cv2
import numpy as np


# ======================================================================
# 质量检测器
# ======================================================================
class ImageQualityChecker:
    """单张图片的低质量判定。

    检查项（按序短路，命中即拒）：
        1. 损坏/无法读取
        2. 分辨率不足（最短边 < min_side）
        3. 文件体积过小（<8KB 的图基本是缩略图/占位图）
        4. 极端宽高比（>4:1 拼接长图/条幅）
        5. 纯色/近纯色（灰度方差极小）
        6. 过暗/过曝（均值 <25 或 >230，夜景废片与死白图）
        7. 模糊（拉普拉斯方差 < blur_threshold，缩到 512 保证阈值稳定）
    """

    def __init__(self, min_side: int, blur_threshold: float):
        self.min_side = min_side
        self.blur_threshold = blur_threshold

    # ------------------------------------------------------------------
    def check(self, path: Path) -> tuple:
        """
        参数：
            path : Path，图片文件

        返回：
            (是否通过, 拒绝原因或 "")
            读取失败按拒绝处理（损坏文件）。
        """
        img = cv2.imread(str(path))
        if img is None:
            return False, "损坏/无法读取"

        # 3. 文件体积（先查省解码开销）
        if path.stat().st_size < 8 * 1024:
            return False, "文件过小(<8KB)"

        h, w = img.shape[:2]
        short_side = min(h, w)

        # 2. 分辨率
        if short_side < self.min_side:
            return False, f"分辨率不足 {w}x{h}"

        # 4. 极端宽高比（>4:1 的拼接长图/条幅）
        if max(h, w) / short_side > 4.0:
            return False, f"极端宽高比 {w}x{h}"

        # 5. 纯色/近纯色（灰度方差极小）
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        if gray.std() < 10:
            return False, "纯色/空白图"

        # 6. 过暗/过曝（均值两端；清晰风景照均值通常在 60~200）
        mean = gray.mean()
        if mean < 25:
            return False, f"过暗 (均值 {mean:.0f})"
        if mean > 230:
            return False, f"过曝 (均值 {mean:.0f})"

        # 7. 模糊（拉普拉斯方差；缩到 512 加速且阈值更稳定）
        g = cv2.resize(gray, (512, 512))
        sharpness = cv2.Laplacian(g, cv2.CV_64F).var()
        if sharpness < self.blur_threshold:
            return False, f"模糊 (方差 {sharpness:.0f})"

        return True, ""


# ======================================================================
# 清洗流程
# ======================================================================
class DatasetCleaner:
    """遍历数据集目录，低质量图片移动到隔离目录。"""

    def __init__(self, data_dir: Path, reject_dir: Path, checker: ImageQualityChecker):
        self.paths = {"data": data_dir, "reject": reject_dir}
        self.checker = checker

    # ------------------------------------------------------------------
    def run(self, dry_run: bool) -> dict:
        """
        返回：
            {"kept": N, "rejected": N, "total": N, "by_reason": {...}}
        """
        classes = sorted(d for d in self.data.iterdir() if d.is_dir())
        total_kept = total_rejected = 0
        by_reason = {}

        for cls in classes:
            images = sorted(
                p for p in cls.iterdir()
                if p.suffix.lower() in (".jpg", ".jpeg", ".png")
            )
            kept = rejected = 0
            reasons = []
            for p in images:
                ok, reason = self.checker.check(p)
                if ok:
                    kept += 1
                    continue
                rejected += 1
                reasons.append(reason.split(" (")[0])  # 归并数值细节
                if not dry_run:
                    dest = self.reject / cls.name
                    dest.mkdir(parents=True, exist_ok=True)
                    shutil.move(str(p), dest / p.name)
            total_kept += kept
            total_rejected += rejected
            for r in set(reasons):
                by_reason[r] = by_reason.get(r, 0) + reasons.count(r)
            mark = "DRY" if dry_run else "OK "
            print(f"  [{mark}] {cls.name:20} 保留 {kept:>4} | 拒绝 {rejected:>3} | {', '.join(sorted(set(reasons))) or '-'}")

        return {"kept": total_kept, "rejected": total_rejected,
                "total": total_kept + total_rejected, "by_reason": by_reason}

    # ---------- 属性（构造后不变） ----------
    @property
    def data(self):
        return self.paths["data"]

    @property
    def reject(self):
        return self.paths["reject"]


# ======================================================================
# 命令行入口
# ======================================================================
def _parse_args(argv=None):
    parser = argparse.ArgumentParser(
        prog="python scripts/clean_dataset.py",
        description="数据集低质量图片清洗（模糊/低分辨率/纯色/极端宽高比）。",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "示例：\n"
            "  python scripts/clean_dataset.py\n"
            "  python scripts/clean_dataset.py --dry-run\n"
            "  python scripts/clean_dataset.py --min-side 200 --blur-threshold 80\n"
        ),
    )
    parser.add_argument("--data-dir", default=str(ROOT / "data" / "train"), help="数据集根目录，默认 data/train")
    parser.add_argument("--reject-dir", default=str(ROOT / "data" / "_rejected"), help="隔离目录，默认 data/_rejected")
    parser.add_argument("--min-side", type=int, default=128, help="最短边像素下限，默认 128")
    parser.add_argument("--blur-threshold", type=float, default=60.0, help="拉普拉斯方差下限，默认 60.0")
    parser.add_argument("--dry-run", action="store_true", help="只检测并报告，不移动文件")
    return parser.parse_args(argv)


def main(argv=None):
    overall_start = time.time()
    args = _parse_args(argv)

    data_dir = Path(args.data_dir)
    if not data_dir.exists():
        raise SystemExit(f"错误: 数据集目录不存在 {data_dir}")

    print("\n========== 数据集图片清洗 ==========")
    print(f"目录: {data_dir}")
    print(f"阈值: 最短边 >= {args.min_side}px | 拉普拉斯方差 >= {args.blur_threshold}")
    if args.dry_run:
        print("模式: DRY-RUN（只报告，不移动）")

    checker = ImageQualityChecker(args.min_side, args.blur_threshold)
    cleaner = DatasetCleaner(data_dir, Path(args.reject_dir), checker)
    stats = cleaner.run(args.dry_run)

    print("\n========== 清洗统计 ==========")
    print(f"总计 {stats['total']} 张：保留 {stats['kept']}，拒绝 {stats['rejected']}")
    for reason, n in sorted(stats["by_reason"].items(), key=lambda x: -x[1]):
        print(f"  {reason}: {n} 张")
    if stats["rejected"] and not args.dry_run:
        print(f"\n拒绝图片已移至: {args.reject_dir}")
        print("复核后手动删除该目录；清洗后请重跑 scripts/register_landmarks.py")
    print(f"\n所有步骤完成，总运行时间: {time.time() - overall_start:.2f} 秒")


if __name__ == "__main__":
    main()
