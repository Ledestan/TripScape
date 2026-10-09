"""行旅识景 TripScape / 高质量注册图筛选脚本
创建日期：2025-10-08

从 data/train 每类正向筛选高质量图片，复制到 data/<类名>/ 注册图目录，完成:
    1. 硬性门槛：清晰度（拉普拉斯方差）> 300、最短边 >= 400px、
       明暗正常（灰度均值 40~220）、无极端宽高比（<= 3:1）
    2. 感知哈希去重（pHash 汉明距离 <= 8 视为近似图，只留质量分最高的）
    3. 综合质量分排序（清晰度为主，分辨率与对比度为辅）
    4. 每类取前 N 张复制到输出目录（默认全部合格的 1/3，上限 60）

依赖:
    Python: >=3.10
    需求文件: requirements.txt
    依赖库:
        opencv-python-headless
        numpy>=1.26

用法（在项目根目录执行）:
    python scripts/select_registration_images.py               # 默认参数筛选
    python scripts/select_registration_images.py --per-class 30   # 每类固定 30 张
    python scripts/select_registration_images.py --dry-run     # 只报告不复制

可选参数:
    --data-dir <目录>    训练集目录，默认 data/train
    --out-dir <目录>     输出根目录（按类名建子目录），默认 data
    --per-class N        每类选取数量上限，默认 15（精品策略：宁缺毋滥）
    --min-side N         最短边下限，默认 500
    --min-sharpness F    清晰度下限，默认 500
    --dry-run            只检测并报告，不复制文件

输出:
    data/<类名>/<原文件名>    精选注册图（复制，不动源文件）

注意:
    1. 只复制不移动：data/train 原样保留，可反复用不同参数重筛。
    2. 输出目录已有同名文件会跳过（幂等）；重筛前可手动清空输出目录。
    3. 筛选后重跑 scripts/register_landmarks.py 更新识别索引。
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
# 质量评分器
# ======================================================================
class QualityScorer:
    """单张图片的门槛判定与综合质量分。

    门槛（任一不过即淘汰）：
        清晰度 > min_sharpness；最短边 >= min_side；
        灰度均值 40~220（过暗/过曝淘汰）；宽高比 <= 3:1。
    综合分 = 清晰度分位（0~1）* 0.6 + 最短边分位 * 0.25 + 对比度分位 * 0.15，
    分位基于本类全部过门槛图片归一化，保证跨类可比。
    """

    def __init__(self, min_side: int, min_sharpness: float):
        self.min_side = min_side
        self.min_sharpness = min_sharpness

    # ------------------------------------------------------------------
    def measure(self, path: Path) -> dict:
        """
        返回：
            {"ok": bool, "reason": str, "sharpness": float,
             "short_side": int, "contrast": float, "phash": np.ndarray}
            读取失败 ok=False。
        """
        img = cv2.imread(str(path))
        if img is None:
            return {"ok": False, "reason": "损坏", "sharpness": 0, "short_side": 0, "contrast": 0, "phash": None}

        h, w = img.shape[:2]
        short_side = min(h, w)
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

        if short_side < self.min_side:
            return {"ok": False, "reason": f"最短边 {short_side}", "sharpness": 0, "short_side": short_side, "contrast": 0, "phash": None}
        if max(h, w) / short_side > 3.0:
            return {"ok": False, "reason": "宽高比>3:1", "sharpness": 0, "short_side": short_side, "contrast": 0, "phash": None}

        g = cv2.resize(gray, (512, 512))
        sharpness = cv2.Laplacian(g, cv2.CV_64F).var()
        if sharpness <= self.min_sharpness:
            return {"ok": False, "reason": f"清晰度 {sharpness:.0f}", "sharpness": sharpness, "short_side": short_side, "contrast": 0, "phash": None}

        mean = g.mean()
        if not (40 <= mean <= 220):
            return {"ok": False, "reason": f"明暗 {mean:.0f}", "sharpness": sharpness, "short_side": short_side, "contrast": 0, "phash": None}

        # 感知哈希（DCT pHash，8x8）：近似图去重用
        small = cv2.resize(gray, (32, 32)).astype(np.float32)
        dct = cv2.dct(small)[:8, :8]
        phash = (dct > np.median(dct)).flatten()

        return {
            "ok": True, "reason": "",
            "sharpness": float(sharpness), "short_side": int(short_side),
            "contrast": float(g.std()), "phash": phash,
        }


# ======================================================================
# 筛选流程
# ======================================================================
# 自适应降档：精品门槛筛不满时逐级放宽，保证小数据类也有注册图
FALLBACK_TIERS = [
    (500, 500.0),  # 精品：清晰度 > 500 且最短边 >= 500
    (400, 300.0),  # 降一档
    (300, 150.0),  # 兜底：只排除明显差的
]
FALLBACK_MIN_KEEP = 8  # 每类期望的最低注册图数


def select_class(cls_dir: Path, scorer: QualityScorer, per_class: int) -> tuple:
    """单类筛选：门槛 -> 打分排序 -> pHash 去重 -> 截取前 N。

    精品门槛筛不满 FALLBACK_MIN_KEEP 张时逐级降档重筛
    （小数据类如 DjoserPyramid 整体 269px，500px 门槛会清零）。

    返回：
        ([(路径, 综合分), ...] 按分数降序, 拒绝统计, 使用的门槛档位)
    """
    for tier, (min_side, min_sharp) in enumerate(FALLBACK_TIERS):
        tier_scorer = QualityScorer(min_side, min_sharp)
        candidates, rejected = _collect(cls_dir, tier_scorer)
        kept = _dedupe_and_rank(candidates)
        if len(kept) >= min(FALLBACK_MIN_KEEP, per_class) or tier == len(FALLBACK_TIERS) - 1:
            limit = per_class if per_class > 0 else max(len(kept) // 3, 1)
            return kept[:limit], rejected, tier
    # 理论上不会到这（最后一档兜底直接返回）
    return [], {}, 0


def _collect(cls_dir: Path, scorer: QualityScorer) -> tuple:
    """按门槛收集合格图与拒绝统计。"""
    candidates = []
    rejected = {"清晰度": 0, "最短边": 0, "明暗": 0, "宽高比": 0, "损坏": 0}
    for p in sorted(cls_dir.glob("*.jpg")):
        m = scorer.measure(p)
        if not m["ok"]:
            for k in rejected:
                if m["reason"].startswith(k):
                    rejected[k] += 1
                    break
            continue
        candidates.append((p, m))
    return candidates, rejected


def _dedupe_and_rank(candidates: list) -> list:
    """综合分排序 + pHash 去重，返回 [(路径, 分数)] 降序。"""
    if not candidates:
        return []

    # 综合分（类内分位归一）
    sharp_arr = np.array([m["sharpness"] for _, m in candidates])
    side_arr = np.array([m["short_side"] for _, m in candidates])
    cont_arr = np.array([m["contrast"] for _, m in candidates])

    def rank_pct(arr):
        order = arr.argsort().argsort()
        return order / max(len(arr) - 1, 1)

    scores = 0.6 * rank_pct(sharp_arr) + 0.25 * rank_pct(side_arr) + 0.15 * rank_pct(cont_arr)
    for i in np.argsort(-scores):
        candidates[i][1]["score"] = float(scores[i])

    # 分数降序 -> pHash 去重（近似图只留分高的）
    candidates.sort(key=lambda x: -x[1]["score"])
    kept, hashes = [], []
    for p, m in candidates:
        dup = False
        for h in hashes:
            if m["phash"] is not None and h is not None and (m["phash"] != h).sum() <= 6:
                dup = True
                break
        if dup:
            continue
        kept.append((p, m["score"]))
        hashes.append(m["phash"])
    return kept


# ======================================================================
# 命令行入口
# ======================================================================
def _parse_args(argv=None):
    parser = argparse.ArgumentParser(
        prog="python scripts/select_registration_images.py",
        description="从训练集正向筛选高质量注册图（门槛 + 评分 + 去重）。",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "示例：\n"
            "  python scripts/select_registration_images.py\n"
            "  python scripts/select_registration_images.py --per-class 30\n"
            "  python scripts/select_registration_images.py --dry-run\n"
        ),
    )
    parser.add_argument("--data-dir", default=str(ROOT / "data" / "train"), help="训练集目录，默认 data/train")
    parser.add_argument("--out-dir", default=str(ROOT / "data"), help="输出根目录（按类名建子目录），默认 data")
    parser.add_argument("--per-class", type=int, default=15, help="每类上限，默认 15（精品策略）")
    parser.add_argument("--min-side", type=int, default=500, help="最短边下限，默认 500")
    parser.add_argument("--min-sharpness", type=float, default=500.0, help="清晰度下限，默认 500")
    parser.add_argument("--dry-run", action="store_true", help="只报告不复制")
    return parser.parse_args(argv)


def main(argv=None):
    overall_start = time.time()
    args = _parse_args(argv)

    data_dir = Path(args.data_dir)
    out_dir = Path(args.out_dir)
    if not data_dir.exists():
        raise SystemExit(f"错误: 训练集目录不存在 {data_dir}")

    print("\n========== 高质量注册图筛选 ==========")
    print(f"训练集: {data_dir}")
    print(f"门槛: 精品 清晰度>500+最短边>=500px | 降档 400/300 | 300/150（每类不足 {FALLBACK_MIN_KEEP} 张时逐级放宽）")
    if args.dry_run:
        print("模式: DRY-RUN（只报告，不复制）")

    classes = sorted(d for d in data_dir.iterdir() if d.is_dir())
    total_selected = 0
    tier_names = ["精品", "降一档", "兜底"]
    for cls in classes:
        kept, rejected, tier = select_class(cls, None, args.per_class)
        if not kept:
            print(f"  [空] {cls.name:22} 无合格图片")
            continue
        rej_str = " ".join(f"{k}×{v}" for k, v in rejected.items() if v)
        mark = "DRY" if args.dry_run else "OK "
        print(f"  [{mark}] {cls.name:22} 精选 {len(kept):>3}（{tier_names[tier]}）| 淘汰 {rej_str}")
        if not args.dry_run:
            dest = out_dir / cls.name
            dest.mkdir(parents=True, exist_ok=True)
            for p, _ in kept:
                target = dest / p.name
                if not target.exists():  # 幂等：已有同名跳过
                    shutil.copy2(p, target)
        total_selected += len(kept)

    print(f"\n总计精选 {total_selected} 张（{len(classes)} 类）")
    if not args.dry_run:
        print(f"已复制到: {out_dir}/<类名>/")
        print("筛选后请重跑 python scripts/register_landmarks.py 更新识别索引")
    print(f"\n所有步骤完成，总运行时间: {time.time() - overall_start:.2f} 秒")


if __name__ == "__main__":
    main()
