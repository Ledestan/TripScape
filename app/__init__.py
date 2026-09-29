"""
模块名称：Flask 应用工厂

功能：
- 负责创建 app、注册蓝图、注册全局错误处理。
- 模型/问答引擎等重量级对象由各蓝图懒加载，避免启动时阻塞。
"""

import sys
import warnings

from flask import Flask, jsonify

sys.dont_write_bytecode = True
warnings.filterwarnings("ignore", category=UserWarning, module="jieba")


def create_app():
    """
    创建并配置 Flask 应用。

    返回：
        Flask
    """
    app = Flask(__name__)

    # 注册蓝图
    from app.routes.footprint import footprint_bp
    from app.routes.main import main_bp
    from app.routes.qa import qa_bp
    from app.routes.recognition import recognition_bp

    app.register_blueprint(main_bp)
    app.register_blueprint(qa_bp, url_prefix="/api")
    app.register_blueprint(recognition_bp, url_prefix="/api")
    app.register_blueprint(footprint_bp, url_prefix="/api")

    # 全局错误处理
    @app.errorhandler(404)
    def not_found(e):
        return jsonify({"error": "资源未找到"}), 404

    @app.errorhandler(500)
    def internal_error(e):
        return jsonify({"error": "服务器内部错误"}), 500

    return app
