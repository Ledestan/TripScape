"""
页面路由：首页与功能主页
"""

from flask import Blueprint, render_template

main_bp = Blueprint("main", __name__)


@main_bp.route("/")
def home():
    """入口主页。"""
    return render_template("index.html")


@main_bp.route("/app")
def app_page():
    """功能主页。"""
    return render_template("app.html")
