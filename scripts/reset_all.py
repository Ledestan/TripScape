"""
行旅识景 TripScape / 重置入口（兼容旧命令）
创建日期: 2025-09-01

保留历史命令 `python scripts/reset_all.py` 的入口，实际实现已统一到 reset_project.py，
完成:
    1. 把命令行参数原样转交给仓库根的重置脚本
    2. 避免两套重置逻辑（旧入口曾依赖已删除的 normalize_articles.py）产生分叉

依赖:
    需求文件: requirements.txt
    依赖库:
        Django==5.2

用法（在项目根目录执行）:
    python scripts/reset_all.py [选项]

示例:
    python scripts/reset_all.py --yes
    python scripts/reset_all.py --yes --no-frontend --with-tests

输出:
    终端输出与 reset_project.py 完全一致

注意:
    1. 真实逻辑在 reset_project.py，改重置流程只需改那一处。
    2. 参数含义见 `python reset_project.py --help`。
"""

import subprocess
import sys

sys.dont_write_bytecode = True
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def main() -> None:
    """把参数转交给根目录的重置脚本，并用同一解释器执行以继承虚拟环境。"""
    target = ROOT / "reset_project.py"
    if not target.exists():
        sys.exit(f"错误: {target} 不存在，无法重置")
    code = subprocess.run(
        [sys.executable, str(target), *sys.argv[1:]], cwd=str(ROOT)
    ).returncode
    sys.exit(code)


if __name__ == "__main__":
    main()
