"""补充精选注册图：只补缺口，绝不恢复用户手动删除的。

原理：
    1. 读取精选目录现存文件 -> 这些是用户认可保留的；
    2. 与上一轮筛选清单（register_images.json）比对 -> 差集即"用户删除的"；
    3. 重新筛选时把这些文件名拉黑，只补每类不足 per-class 的部分；
    4. 把删除记录持久化到 scripts/db/curated_deleted.json，
       后续重跑也永远不会再捡回来（除非手动清空该文件）。

待审模式（--pending）：
    补选图放 data/_pending/<类名>/，不直接进精选目录；
    人工审核后把满意的挪入 data/<类名>/，不要的直接删；
    下次重跑本脚本时 pending 里被删的同样进黑名单（闭环）。
"""

import argparse
import json
import sys
import time
from pathlib import Path

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "backend"))
sys.path.insert(0, str(ROOT / "scripts"))

import os

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

import django

django.setup()

from select_registration_images import FALLBACK_TIERS, FALLBACK_MIN_KEEP, _collect, _dedupe_and_rank

# 删除记录持久化（用户删除的文件名按类记录）
DELETED_LOG = ROOT / "scripts" / "db" / "curated_deleted.json"
OUT_DIR = ROOT / "data"
TRAIN = ROOT / "data" / "train"


def load_deleted() -> dict:
    if DELETED_LOG.exists():
        return json.loads(DELETED_LOG.read_text(encoding="utf-8"))
    return {}


def save_deleted(d: dict):
    DELETED_LOG.parent.mkdir(parents=True, exist_ok=True)
    DELETED_LOG.write_text(json.dumps(d, ensure_ascii=False, indent=1), encoding="utf-8")


def sync_deletions(deleted: dict, prev_manifest: list):
    """比对上一轮清单与现存文件，把新删除的记入黑名单。

    覆盖两个来源：
        - 精选目录 data/<类>/（正式审定的）
        - 待审目录 data/_pending/<类>/（上次补选待审的）
    """
    prev_by_cls = {}
    for e in prev_manifest:
        prev_by_cls.setdefault(e["target_id"], set()).add(Path(e["path"]).name)

    # 上一轮 pending 的记录（把 pending 现状也持久化过一份）
    pending_snapshot = ROOT / "scripts" / "db" / "curated_pending_snapshot.json"
    if pending_snapshot.exists():
        for cls, names in json.loads(pending_snapshot.read_text(encoding="utf-8")).items():
            prev_by_cls.setdefault(cls, set()).update(names)

    for cls, prev_names in prev_by_cls.items():
        newly = set()
        # 精选目录
        cur = OUT_DIR / cls
        cur_names = set(p.name for p in cur.glob("*.jpg")) if cur.is_dir() else set()
        # 待审目录（存在则其内容也算"还留着"）
        pend = OUT_DIR / "_pending" / cls
        if pend.is_dir():
            cur_names |= set(p.name for p in pend.glob("*.jpg"))
        newly = prev_names - cur_names
        if newly:
            deleted.setdefault(cls, [])
            for n in newly:
                if n not in deleted[cls]:
                    deleted[cls].append(n)
                    print(f"    [黑名单+] {cls}/{n}")


def topup(per_class: int, dry_run: bool, pending: bool):
    deleted = load_deleted()
    # 上一轮清单（若已被删则视为空——以精选目录现状 + 黑名单为准）
    manifest_path = ROOT / "scripts" / "db" / "register_images.json"
    prev_manifest = json.loads(manifest_path.read_text(encoding="utf-8")) if manifest_path.exists() else []
    sync_deletions(deleted, prev_manifest)
    save_deleted(deleted)

    # --pending 模式：补选图放 data/_pending/<类>/ 待人工审核，
    # 审核通过的图手动挪入 data/<类>/；pending 里被删掉的同样进黑名单
    out_root = OUT_DIR / "_pending" if pending else OUT_DIR

    total_added = 0
    for cls_dir in sorted(d for d in TRAIN.iterdir() if d.is_dir()):
        cls = cls_dir.name
        blacklist = set(deleted.get(cls, []))
        cur_dir = OUT_DIR / cls
        have = set(p.name for p in cur_dir.glob("*.jpg")) if cur_dir.is_dir() else set()
        need = per_class - len(have)
        if need <= 0:
            print(f"  [满] {cls:22} 已有 {len(have)}")
            continue

        # 逐档筛选（与主脚本同逻辑），跳过黑名单与已有
        picked = []
        for tier in range(len(FALLBACK_TIERS)):
            min_side, min_sharp = FALLBACK_TIERS[tier]
            from select_registration_images import QualityScorer

            candidates, _ = _collect(cls_dir, QualityScorer(min_side, min_sharp))
            kept = _dedupe_and_rank(candidates)
            pool = [(p, s) for p, s in kept if p.name not in blacklist and p.name not in have]
            if len(have) + len(pool) >= min(FALLBACK_MIN_KEEP, per_class) or tier == len(FALLBACK_TIERS) - 1:
                picked = pool[:need]
                break

        mark = "DRY" if dry_run else "OK "
        dest_dir = out_root / cls
        print(f"  [{mark}] {cls:22} 现有 {len(have)} | 补 {len(picked)} -> {dest_dir.relative_to(ROOT)}")
        if not dry_run:
            dest_dir.mkdir(parents=True, exist_ok=True)
            import shutil

            for p, _ in picked:
                shutil.copy2(p, dest_dir / p.name)
        total_added += len(picked)

    mode = "（待审模式：审核后手动挪入 data/<类>/，不要的直接删）" if pending else ""
    print(f"\n合计补充 {total_added} 张{mode}")
    print(f"黑名单共 {sum(len(v) for v in deleted.values())} 张已删图永不恢复")

    # 待审快照落盘（下次 sync 时把 pending 里被删的也纳入黑名单）
    if not dry_run:
        snap = {}
        pend_root = OUT_DIR / "_pending"
        if pend_root.is_dir():
            for d in pend_root.iterdir():
                if d.is_dir():
                    snap[d.name] = sorted(p.name for p in d.glob("*.jpg"))
        snap_path = ROOT / "scripts" / "db" / "curated_pending_snapshot.json"
        snap_path.write_text(json.dumps(snap, ensure_ascii=False, indent=1), encoding="utf-8")

    if not dry_run and total_added:
        if pending:
            print(f"补选图在 data/_pending/<类名>/，审核通过后挪入 data/<类名>/，再重建索引")
        else:
            print("请删除 scripts/db/register_images.json 后重跑 scripts/register_landmarks.py 重建索引")


def main():
    parser = argparse.ArgumentParser(prog="python scripts/topup_registration_images.py", description="补充精选注册图（跳过用户已删除的）")
    parser.add_argument("--per-class", type=int, default=15, help="每类目标数量，默认 15")
    parser.add_argument("--pending", action="store_true", help="补选图放 data/_pending/ 待人工审核，不直接进精选目录")
    parser.add_argument("--dry-run", action="store_true", help="只报告不复制")
    args = parser.parse_args()
    topup(args.per_class, args.dry_run, args.pending)


if __name__ == "__main__":
    main()
