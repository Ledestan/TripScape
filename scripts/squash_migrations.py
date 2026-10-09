"""把每个 app 的迁移历史压扁成单个 0001_initial（重建基准）。

做法：删掉现有迁移文件 → 用 --reset 起点重新 makemigrations。
注意：压扁后需要重置数据库（reset_all.py 已含 --rebuild）。
"""

import shutil
import subprocess
import sys
from pathlib import Path

sys.dont_write_bytecode = True

ROOT = Path(__file__).resolve().parent.parent
BACKEND = ROOT / "backend"
APPS = ["accounts", "badges", "comments", "journals", "landmarks", "notifications", "routes", "shares"]

for app in APPS:
    d = BACKEND / "apps" / app / "migrations"
    if not d.exists():
        continue
    # 保留 __init__.py，删除迁移文件
    for f in d.glob("0*.py"):
        f.unlink()
    print(f"cleared {app}/migrations ({len(list(d.glob('0*.py')))} left)")

# 重新生成基准迁移（依赖顺序按 app 列表）
env = {
    **__import__("os").environ,
    "DJANGO_SETTINGS_MODULE": "config.settings",
    "PYTHONPATH": str(BACKEND),
    "PYTHONIOENCODING": "utf-8",
    "PYTHONDONTWRITEBYTECODE": "1",
}
r = subprocess.run(
    [sys.executable, str(BACKEND / "manage.py"), "makemigrations", *APPS],
    cwd=str(ROOT),
    env=env,
)
sys.exit(r.returncode)
