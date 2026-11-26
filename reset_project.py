"""
行旅识景 TripScape / 项目重置脚本
创建日期: 2026-11-25

把仓库恢复到「刚装好、第一次启动之前」的初始状态，完成:
    1. 清理运行产物（runtime/tmp|cache|logs、上传目录、截图目录、__pycache__）
    2. 清空业务数据库（本地 SQLite 直接删库；MySQL 走 init_tripscape --rebuild）
    3. 重新迁移并导入种子数据（26 地标 + 知识条目 + 徽章 + 敏感词 + 种子账号）
    4. 可选重建前端产物（默认重建，保证 dist 与当前源码一致）
    5. 可选跑一遍后端测试（--with-tests）

依赖:
    Python: >=3.10
    需求文件: requirements.txt
    依赖库:
        Django==5.2
    环境变量:
        DB_ENGINE    数据库引擎，默认 sqlite（MySQL 连不上时也回退 sqlite）
        RUNTIME_DIR  运行产物目录，默认 ./runtime

用法（在项目根目录执行）:
    python reset_project.py [选项]

可选参数:
    --yes            跳过确认，直接执行
    --no-frontend    不重建前端产物（dist 保持现状）
    --skip-db        只清运行产物，不动数据库
    --with-tests     重置完成后跑一遍后端测试

示例:
    python reset_project.py                 # 交互确认后完整重置（含前端构建）
    python reset_project.py --yes           # CI/脚本里直接重置
    python reset_project.py --yes --skip-db # 只清缓存与上传，保留数据

输出:
    终端阶段横幅、各阶段耗时与总耗时；重置后可直接 `python desktop.py` 启动

注意:
    1. 会删除业务数据（手记、评论、碎片、账号），执行前先备份需要保留的内容。
    2. MySQL 模式依赖本机 MySQL 已启动；不可达时自动按 SQLite 处理，不会静默清空 MySQL。
    3. 前端构建失败只提示、不中断，因为后端与桌面入口仍可运行。
"""

import argparse
import os
import shutil
import socket
import subprocess
import sys
import time
from pathlib import Path

sys.dont_write_bytecode = True

ROOT = Path(__file__).resolve().parent
BACKEND = ROOT / "backend"
PYTHON = sys.executable

# 逐阶段耗时与总耗时在结尾统一打印
TIMINGS: list[tuple[str, float]] = []


def print_banner(title: str) -> None:
    """阶段横幅：保证日志里每一段都能被一眼定位。"""
    print(f"\n========== {title} ==========")


def print_step_done(title: str, started: float) -> None:
    """打印单阶段耗时，并记录到 TIMINGS 供结尾汇总。"""
    cost = time.time() - started
    TIMINGS.append((title, cost))
    print(f"[耗时] {title}: {cost:.2f} 秒")


def project_env() -> dict[str, str]:
    """构造子进程环境：后端需要 PYTHONPATH 指向 backend 才能 import config。"""
    return {
        **os.environ,
        "DJANGO_SETTINGS_MODULE": "config.settings",
        "DJANGO_DEPLOY": "dev",
        "PYTHONPATH": str(BACKEND),
        "PYTHONIOENCODING": "utf-8",
        "PYTHONDONTWRITEBYTECODE": "1",
    }


def mysql_reachable() -> bool:
    """探测 .env 里配置的 MySQL 是否可连接；不可达时本脚本按 SQLite 处理。"""
    try:
        import environ

        env = environ.Env()
        env.read_env(str(ROOT / ".env"))
        host = env.str("MYSQL_HOST", default="127.0.0.1")
        port = env.int("MYSQL_PORT", default=3306)
    except Exception:  # 理论上 env 文件缺失只会走这里
        host, port = "127.0.0.1", 3306
    try:
        with socket.create_connection((host, port), timeout=1.5):
            return True
    except OSError:
        return False


def uses_sqlite() -> bool:
    """当前运行是否走 SQLite：显式配置优先，否则看 MySQL 是否可达。"""
    engine = os.environ.get("DB_ENGINE", "").strip().lower()
    if engine:
        return engine != "mysql"
    return not mysql_reachable()


def run(cmd: list[str], title: str, cwd: Path | None = None) -> int:
    """统一子进程入口：Windows 下 .cmd 必须经 cmd /c，前端命令要在 frontend/ 下跑。"""
    print(f"[执行] {' '.join(cmd)}")
    final = ["cmd", "/c", *cmd] if os.name == "nt" else cmd
    return subprocess.run(final, cwd=str(cwd or ROOT), env=project_env()).returncode


def clean_runtime() -> None:
    """清理运行产物目录，保留目录本身，避免首次启动时因缺目录报错。"""
    started = time.time()
    print_banner("第 1 步 / 清理运行产物")

    for sub in ("tmp", "cache", "logs"):
        target = ROOT / "runtime" / sub
        if target.exists():
            shutil.rmtree(target, ignore_errors=True)
        target.mkdir(parents=True, exist_ok=True)
        print(f"已清空 runtime/{sub}")

    uploads = ROOT / "runtime" / "uploads"
    if uploads.exists():
        shutil.rmtree(uploads, ignore_errors=True)
    uploads.mkdir(parents=True, exist_ok=True)
    print("已清空 runtime/uploads（用户上传文件）")

    screenshots = ROOT / "runtime" / "screenshots"
    if screenshots.exists():
        shutil.rmtree(screenshots, ignore_errors=True)
    print("已清空 runtime/screenshots")

    removed_pycache = 0
    for pycache in ROOT.rglob("__pycache__"):
        if ".venv" in str(pycache) or "node_modules" in str(pycache):
            continue
        shutil.rmtree(pycache, ignore_errors=True)
        removed_pycache += 1
    print(f"已清理 __pycache__ 目录: {removed_pycache} 个")

    print_step_done("清理运行产物", started)


def reset_database() -> None:
    """删除本地库文件（SQLite）或调用 init_tripscape 重建（MySQL）。"""
    started = time.time()
    print_banner("第 2 步 / 重置数据库")

    if uses_sqlite():
        db_path = ROOT / "runtime" / "tripscape.db"
        for suffix in ("", "-wal", "-shm", "-journal"):
            candidate = Path(str(db_path) + suffix)
            if candidate.exists():
                candidate.unlink()
                print(f"已删除 {candidate.relative_to(ROOT)}")
        code = run(
            [PYTHON, str(BACKEND / "manage.py"), "migrate", "--noinput"], "migrate"
        )
        if code == 0:
            code = run(
                [PYTHON, str(BACKEND / "manage.py"), "init_tripscape"],
                "init_tripscape",
            )
    else:
        code = run(
            [PYTHON, str(BACKEND / "manage.py"), "init_tripscape", "--rebuild"],
            "init_tripscape --rebuild",
        )

    if code != 0:
        sys.exit("数据库重置失败：请检查数据库是否可用，处理后再重试")

    print_step_done("重置数据库", started)


def build_frontend() -> None:
    """用仓库内已安装的 tsc / vite 构建，避免依赖全局 pnpm。"""
    started = time.time()
    print_banner("第 3 步 / 重建前端产物")

    tsc = ROOT / "frontend" / "node_modules" / ".bin" / "tsc.cmd"
    vite = ROOT / "frontend" / "node_modules" / ".bin" / "vite.cmd"
    if not tsc.exists() or not vite.exists():
        print("未找到 frontend/node_modules，跳过前端构建（先执行一次依赖安装）")
        print_step_done("重建前端产物", started)
        return

    dist = ROOT / "frontend" / "dist"
    if dist.exists():
        shutil.rmtree(dist, ignore_errors=True)
        print("已清空 frontend/dist")

    # 先类型检查再打包：类型错误不应该被 vite 的转译掩盖；
    # vite 的入口是 frontend/index.html，所以两条命令都必须在 frontend/ 下执行
    frontend = ROOT / "frontend"
    if run([str(tsc), "-b"], "tsc -b", cwd=frontend) != 0:
        print("类型检查未通过，前端产物可能不可用")
    run([str(vite), "build"], "vite build", cwd=frontend)

    # 以产物是否落盘为准：node 退出时偶发 libuv 断言（Windows）不代表构建失败
    if (dist / "index.html").exists():
        print("前端产物已就绪：frontend/dist/index.html")
    else:
        print("前端构建失败：请到 frontend/ 手工执行 vite build 查看完整错误")

    print_step_done("重建前端产物", started)


def run_tests() -> None:
    """可选：重置后跑一遍后端测试，确认初始状态本身是健康的。"""
    started = time.time()
    print_banner("第 4 步 / 后端测试")
    code = run(
        [PYTHON, "-m", "pytest", "tests/backend", "-q", "--no-header"],
        "pytest",
    )
    print("测试通过" if code == 0 else "存在失败用例（请查看上面的输出）")
    print_step_done("后端测试", started)


def confirm() -> bool:
    """交互确认：删除数据前必须让操作者明确知道代价。"""
    print("本操作会删除业务数据（手记 / 评论 / 碎片 / 账号）并重建前端产物。")
    answer = input("确认继续？输入 y 回车: ").strip().lower()
    return answer in {"y", "yes"}


def main() -> None:
    """按固定顺序串联各阶段，最后打印总耗时与启动方式。"""
    parser = argparse.ArgumentParser(
        description="TripScape 项目重置（恢复初始状态）",
        epilog="示例: python reset_project.py --yes --no-frontend",
    )
    parser.add_argument("--yes", action="store_true", help="跳过确认，直接执行")
    parser.add_argument("--no-frontend", action="store_true", help="不重建前端产物")
    parser.add_argument(
        "--skip-db", action="store_true", help="只清运行产物，不动数据库"
    )
    parser.add_argument(
        "--with-tests", action="store_true", help="重置完成后跑后端测试"
    )
    args = parser.parse_args()

    overall_start = time.time()
    print("TripScape 2.0 项目重置")
    print(f"工作目录: {ROOT}")
    print(f"数据库: {'SQLite（runtime/tripscape.db）' if uses_sqlite() else 'MySQL'}")

    if not args.yes and not confirm():
        sys.exit("已取消，未做任何修改")

    clean_runtime()
    if not args.skip_db:
        reset_database()
    if not args.no_frontend:
        build_frontend()
    if args.with_tests:
        run_tests()

    print("\n" + "=" * 50)
    for title, cost in TIMINGS:
        print(f"[耗时] {title}: {cost:.2f} 秒")
    print(f"所有步骤完成，总运行时间: {time.time() - overall_start:.2f} 秒")
    print("启动方式:")
    print("  桌面应用: python desktop.py")
    print("  开发服务: python backend/manage.py runserver 127.0.0.1:8000")
    print("  种子账号: admin / admin123456（管理员）· demo / demo123456（演示用户）")


if __name__ == "__main__":
    main()
