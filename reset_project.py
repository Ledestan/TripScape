"""
行旅识景 TripScape / 项目重置脚本

项目重置：把仓库恢复到"刚装好、第一次启动之前"的干净状态，完成:
    1. 清理运行产物（runtime 临时目录、上传文件、截图、__pycache__）
    2. 清空并重建业务数据库（SQLite 删库重建 / MySQL 走 init_tripscape --rebuild）
    3. 校验问答索引；缺失或显式要求时重新构建
    4. 重建前端产物（类型检查 + vite build，可跳过）

依赖:
    需求文件: requirements.txt
    依赖库:
        Django>=5.2
        django-environ（读 .env 判断数据库是否可达）
    环境变量:
        DB_ENGINE     sqlite / mysql，留空则按"MySQL 是否可连"自动判断
        RUNTIME_DIR   运行产物根目录，默认 ./runtime

用法（项目根目录执行）:
    python reset_project.py [选项]

可选参数:
    --yes             跳过交互确认
    --skip-db         只清运行产物，不动数据库
    --no-frontend     不重建前端产物
    --rebuild-index   强制重建问答索引（文章改动后用它）

示例:
    python reset_project.py --yes
    python reset_project.py --yes --no-frontend
    python reset_project.py --yes --rebuild-index

输出:
    各阶段横幅、单阶段耗时与总耗时；结束后按终端提示启动服务

注意:
    1. 会删除全部业务数据（账号、手账、评论、足迹、徽章记录），执行前自行备份。
    2. MySQL 模式依赖本机数据库已启动；连不上时本脚本按 SQLite 处理，不会误清 MySQL。
    3. 前端构建失败只提示不中断，后端与桌面入口仍可使用。
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

# 阶段耗时在结尾统一汇总，方便定位哪一步最慢
TIMINGS: list[tuple[str, float]] = []


def print_banner(title: str) -> None:
    """阶段横幅：让日志每一段都能被一眼定位。"""
    print(f"\n========== {title} ==========")


def print_step_done(title: str, started: float) -> None:
    """打印单阶段耗时并记录，供结尾汇总。"""
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
    """探测 .env 配置的 MySQL 端口；连不上就把本次重置按 SQLite 处理。"""
    try:
        import environ

        env = environ.Env()
        env.read_env(str(ROOT / ".env"))
        host = env.str("MYSQL_HOST", default="127.0.0.1")
        port = env.int("MYSQL_PORT", default=3306)
    except Exception:  # 理论上只有 .env 缺失才走到这里
        host, port = "127.0.0.1", 3306
    try:
        with socket.create_connection((host, port), timeout=1.5):
            return True
    except OSError:
        return False


def uses_sqlite() -> bool:
    """显式 DB_ENGINE 优先；否则由 MySQL 可达性决定，避免误判。"""
    engine = os.environ.get("DB_ENGINE", "").strip().lower()
    if engine:
        return engine != "mysql"
    return not mysql_reachable()


def ensure_no_bytecode_hook() -> None:
    """在 venv 写 sitecustomize，保证后续子进程不会生成 __pycache__。

    该钩子属于环境产物（.venv 不入库），重建虚拟环境后会丢失，
    所以每次重置都先补一遍，避免重置过程自己产出一堆缓存。
    """
    started = time.time()
    print_banner("第 0 步 / 关闭字节码缓存")

    site_dir = Path(sys.prefix) / "Lib" / "site-packages"
    if not site_dir.exists():  # 非 Windows 布局
        site_dir = Path(sys.prefix) / "lib" / "site-packages"
    hook = site_dir / "sitecustomize.py"
    hook.write_text(
        '"""解释器钩子：禁用 __pycache__（由 reset_project.py 自动重建）。"""\n\n'
        "import sys\n\n"
        "sys.dont_write_bytecode = True\n",
        encoding="utf-8",
    )
    os.environ["PYTHONDONTWRITEBYTECODE"] = "1"
    print(f"已写入解释器钩子: {hook}")
    print_step_done("关闭字节码缓存", started)


def run(cmd: list[str], title: str, cwd: Path | None = None) -> int:
    """统一子进程入口：Windows 下 .cmd 必须经 cmd /c，前端命令要在 frontend/ 下跑。"""
    print(f"[执行] {' '.join(cmd)}")
    final = ["cmd", "/c", *cmd] if os.name == "nt" else cmd
    return subprocess.run(final, cwd=str(cwd or ROOT), env=project_env()).returncode


def clean_runtime() -> None:
    """清理运行产物目录；目录本身保留，首次启动不会因缺目录报错。"""
    started = time.time()
    print_banner("第 1 步 / 清理运行产物")

    for sub in ("tmp", "cache", "logs"):
        target = ROOT / "runtime" / sub
        shutil.rmtree(target, ignore_errors=True)
        target.mkdir(parents=True, exist_ok=True)
        print(f"已清空 runtime/{sub}")

    for sub in ("uploads", "screenshots"):
        target = ROOT / "runtime" / sub
        if target.exists():
            shutil.rmtree(target, ignore_errors=True)
        print(f"已清空 runtime/{sub}")

    removed_pycache = 0
    for pycache in ROOT.rglob("__pycache__"):
        if ".venv" in str(pycache) or "node_modules" in str(pycache):
            continue
        shutil.rmtree(pycache, ignore_errors=True)
        removed_pycache += 1
    print(f"已清理 __pycache__ 目录: {removed_pycache} 个")

    print_step_done("清理运行产物", started)


def reset_database() -> None:
    """删除本地 SQLite 库后重新迁移与播种，或让 init_tripscape 重建 MySQL 业务表。"""
    started = time.time()
    print_banner("第 3 步 / 重置数据库")

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
        sys.exit("数据库重置失败：请确认数据库可用后重试")

    print_step_done("重置数据库", started)


def ensure_qa_index(force: bool) -> None:
    """问答索引缺失或要求强制时重建；已存在则跳过，避免每次重置都跑 40 秒。"""
    started = time.time()
    print_banner("第 2 步 / 问答索引")

    index_dir = ROOT / "runtime" / "index"
    chunks = index_dir / "qa_chunks.json"
    vectors = index_dir / "qa_vectors.npy"
    if chunks.exists() and vectors.exists() and not force:
        print(f"已存在问答索引（{chunks.name}），跳过重建")
        print_step_done("问答索引", started)
        return

    cmd = [PYTHON, str(ROOT / "scripts" / "build_qa_index.py")]
    if force:
        cmd.append("--force-rebuild")
    code = run(cmd, "build_qa_index")
    if code != 0:
        print("问答索引构建失败：智能问答不可用，其余功能不受影响")
    print_step_done("问答索引", started)


def build_frontend() -> None:
    """用仓库内已安装的 tsc / vite 构建，避免依赖全局 pnpm。"""
    started = time.time()
    print_banner("第 4 步 / 重建前端产物")

    tsc = ROOT / "frontend" / "node_modules" / ".bin" / "tsc.cmd"
    vite = ROOT / "frontend" / "node_modules" / ".bin" / "vite.cmd"
    if not tsc.exists() or not vite.exists():
        print("未找到 frontend/node_modules，跳过前端构建（先安装依赖）")
        print_step_done("重建前端产物", started)
        return

    dist = ROOT / "frontend" / "dist"
    shutil.rmtree(dist, ignore_errors=True)
    print("已清空 frontend/dist")

    frontend = ROOT / "frontend"
    # 先类型检查再打包：类型错误不该被 vite 转译掩盖；入口在 frontend/，必须在该目录执行
    if run([str(tsc), "-b"], "tsc -b", cwd=frontend) != 0:
        print("类型检查未通过，前端产物可能不可用")
    run([str(vite), "build"], "vite build", cwd=frontend)

    if (dist / "index.html").exists():
        print("前端产物已就绪：frontend/dist/index.html")
    else:
        print("前端构建失败：请到 frontend/ 手工执行 pnpm build 查看完整错误")

    print_step_done("重建前端产物", started)


def confirm() -> bool:
    """删除数据前必须让操作者明确知道代价。"""
    print("本操作会删除全部业务数据（账号 / 手账 / 评论 / 足迹 / 徽章记录）。")
    answer = input("确认继续？输入 y 回车: ").strip().lower()
    return answer in {"y", "yes"}


def main() -> None:
    """按固定顺序串联各阶段，最后打印总耗时与启动方式。"""
    parser = argparse.ArgumentParser(
        description="TripScape 重置（恢复初始状态）",
        epilog="示例: python reset_project.py --yes --no-frontend",
    )
    parser.add_argument("--yes", action="store_true", help="跳过确认，直接执行")
    parser.add_argument(
        "--skip-db", action="store_true", help="只清运行产物，不动数据库"
    )
    parser.add_argument("--no-frontend", action="store_true", help="不重建前端产物")
    parser.add_argument("--rebuild-index", action="store_true", help="强制重建问答索引")
    args = parser.parse_args()

    overall_start = time.time()
    print("TripScape 项目重置")
    print(f"工作目录: {ROOT}")
    print(f"数据库: {'SQLite（runtime/tripscape.db）' if uses_sqlite() else 'MySQL'}")

    if not args.yes and not confirm():
        sys.exit("已取消，未做任何修改")

    # 先补字节码钩子，再跑任何子进程，避免重置过程自己产出缓存
    ensure_no_bytecode_hook()
    clean_runtime()
    # 先建索引再重建库：init_tripscape 生成地标页面时要读 runtime/index
    ensure_qa_index(force=args.rebuild_index)
    if not args.skip_db:
        reset_database()
    if not args.no_frontend:
        build_frontend()

    print("\n" + "=" * 50)
    for title, cost in TIMINGS:
        print(f"[耗时] {title}: {cost:.2f} 秒")
    print(f"所有步骤完成，总运行时间: {time.time() - overall_start:.2f} 秒")
    print("启动方式:")
    print("  桌面应用: python desktop.py")
    print("  开发服务: python backend/manage.py runserver 127.0.0.1:8000")
    print("  展示状态: python reset_demo.py --yes（先重置，再铺演示数据）")


if __name__ == "__main__":
    main()
