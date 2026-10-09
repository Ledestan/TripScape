"""行旅识景 TripScape
创建日期：2025-09-01

模块名称：全局初始化脚本（一键重置重测）

作用（按顺序）：
    1. 清空 runtime/ 下的临时与缓存产物（logs/tmp/cache，保留 backups）
    2. 清空并重建 MySQL 业务表（Django migrations）
    3. 导入种子数据（26 地标 + 204 知识条目 + 徽章 + 敏感词 + 种子账号 + 百科图片）
    4. 重建前端（可选，默认跳过，--with-frontend 开启）
    5. 跑一遍后端测试（可选，--with-tests 开启）

用法（在仓库根目录执行）：
    python scripts/reset_all.py                # 重置数据库与运行时
    python scripts/reset_all.py --skip-db      # 只清 runtime，不动数据库
    python scripts/reset_all.py --with-frontend --with-tests   # 全量重测
"""

import argparse
import shutil
import subprocess
import sys
from pathlib import Path

sys.dont_write_bytecode = True

ROOT = Path(__file__).resolve().parent.parent
BACKEND = ROOT / "backend"
PY = sys.executable


def step(title: str):
    print(f"\n{'=' * 50}\n{title}\n{'=' * 50}")


def clean_runtime():
    step("1/4 清理 runtime/ 与 __pycache__")
    for sub in ("tmp", "cache", "logs"):
        d = ROOT / "runtime" / sub
        if d.exists():
            shutil.rmtree(d, ignore_errors=True)
        d.mkdir(parents=True, exist_ok=True)
    uploads = ROOT / "runtime" / "uploads"
    uploads.mkdir(parents=True, exist_ok=True)
    # 识别暂存目录单独建
    (uploads / "recognize").mkdir(exist_ok=True)
    # 清掉项目内所有 __pycache__
    for pyc in ROOT.rglob("__pycache__"):
        if ".venv" in str(pyc):
            continue
        shutil.rmtree(pyc, ignore_errors=True)
    # 自愈：确保 venv 的 sitecustomize（禁用字节码）存在
    sc = ROOT / ".venv" / "Lib" / "site-packages" / "sitecustomize.py"
    if not sc.exists():
        sc.parent.mkdir(parents=True, exist_ok=True)
        sc.write_text(
            "import sys\n\nsys.dont_write_bytecode = True\n",
            encoding="utf-8",
        )
        print("已重建 sitecustomize.py（禁用 __pycache__）")
    print("runtime/tmp|cache|logs 已清空，__pycache__ 已清零")


def reset_db():
    step("2/4 重置 MySQL（migrate + 种子）")
    env = {
        **__import__("os").environ,
        "DJANGO_SETTINGS_MODULE": "config.settings",
        "DJANGO_DEPLOY": "dev",
        "PYTHONPATH": str(BACKEND),
        "PYTHONIOENCODING": "utf-8",
    }
    r = subprocess.run(
        [PY, str(BACKEND / "manage.py"), "init_tripscape", "--rebuild"],
        cwd=str(ROOT),
        env=env,
    )
    if r.returncode != 0:
        sys.exit("数据库重置失败，请检查 MySQL 是否运行")


def build_indexes():
    step("3/5 重建检索与问答索引（本地运行产物）")
    env = {
        **__import__("os").environ,
        "PYTHONPATH": str(BACKEND),
        "PYTHONIOENCODING": "utf-8",
        "PYTHONDONTWRITEBYTECODE": "1",
        "HF_ENDPOINT": "https://hf-mirror.com",
    }
    # 文章规范化（繁转简 + wikitext 残留清理，幂等）
    r0 = subprocess.run([PY, str(ROOT / "scripts" / "normalize_articles.py")], env=env)
    # 识别索引：注册图特征 -> FAISS（清单未变时自动复用缓存指纹）
    r1 = subprocess.run([PY, str(ROOT / "scripts" / "register_landmarks.py")], env=env)
    # 问答索引：文章分块 -> 向量 + BM25（文章未变时自动复用缓存指纹）
    r2 = subprocess.run([PY, str(ROOT / "scripts" / "build_qa_index.py")], env=env)
    if r1.returncode != 0 or r2.returncode != 0:
        print("索引构建失败（可单独重跑对应脚本）")


def build_frontend():
    step("4/5 构建前端")
    pnpm = (
        Path.home()
        / ".dsh"
        / "dsh-runtimes"
        / "dsh-primary-runtime"
        / "dependencies"
        / "pnpm"
        / "bin"
        / "pnpm.mjs"
    )
    node = (
        Path.home()
        / ".dsh"
        / "dsh-runtimes"
        / "dsh-primary-runtime"
        / "dependencies"
        / "node"
        / "bin"
        / "node.exe"
    )
    if not pnpm.exists():
        print("未找到 pnpm，跳过前端构建（可手动 cd frontend && pnpm build）")
        return
    fe = ROOT / "frontend"
    if not (fe / "node_modules").exists():
        print("node_modules 不存在，先安装依赖…")
        subprocess.run(
            [
                str(node),
                str(pnpm),
                "install",
                "--registry=https://registry.npmmirror.com",
            ],
            cwd=str(fe),
        )
    r = subprocess.run([str(node), str(pnpm), "run", "build"], cwd=str(fe))
    if r.returncode != 0:
        print("前端构建失败（可手动重试）")


def run_tests():
    step("5/5 后端测试")
    r = subprocess.run(
        [PY, "-m", "pytest", "tests/backend", "-q", "--no-header"],
        cwd=str(ROOT),
        env={
            **__import__("os").environ,
            "PYTHONPATH": str(BACKEND),
            "PYTHONIOENCODING": "utf-8",
            "PYTHONDONTWRITEBYTECODE": "1",
        },
    )
    print("测试通过" if r.returncode == 0 else "存在失败用例")


def main():
    parser = argparse.ArgumentParser(description="TripScape 全局初始化（重置重测）")
    parser.add_argument("--skip-db", action="store_true", help="只清 runtime，不重置数据库")
    parser.add_argument("--skip-index", action="store_true", help="跳过索引重建（仅调试用）")
    parser.add_argument("--with-frontend", action="store_true", help="顺带构建前端")
    parser.add_argument("--with-tests", action="store_true", help="最后跑后端测试")
    args = parser.parse_args()

    clean_runtime()
    if not args.skip_db:
        reset_db()
    if not args.skip_index:
        build_indexes()
    if args.with_frontend:
        build_frontend()
    if args.with_tests:
        run_tests()

    step("完成")
    print("启动方式：")
    print("  开发服务： python backend/manage.py runserver")
    print("  桌面应用： python desktop.py")
    print("  种子账号： admin/admin123456（管理员）· demo/demo123456（演示用户）")


if __name__ == "__main__":
    main()
