"""
项目名称: 行旅识景：世界著名地标智能识别
创建时间: 2026-06-25

模块名称：启动入口

- 本项目数据集来源于 Kaggle 平台，在 data 文件夹中形成了 train 和 valid 文件夹
- 应用配置与路由注册见 app/__init__.py

用法：
    python run.py
"""

import sys
import warnings

sys.dont_write_bytecode = True
warnings.filterwarnings("ignore", category=UserWarning, module="jieba")

from app import create_app

app = create_app()


if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=5000)
