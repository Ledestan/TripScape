"""
模块名称：问答 API 路由

POST /api/chat
    请求 JSON：{"question": "用户问题"}
    返回 JSON：{"answer": "...", "source": "rag"}
"""

import sys
import traceback

sys.dont_write_bytecode = True
from flask import Blueprint, current_app, jsonify, request

from app.services import QASystem

qa_bp = Blueprint("qa", __name__)

_qa_system = None


def get_qa_system():
    """懒加载问答系统，全局只初始化一次。"""
    global _qa_system
    if _qa_system is None:
        _qa_system = QASystem()
    return _qa_system


@qa_bp.route("/chat", methods=["POST"])
def chat():
    """问答接口。"""
    data = request.get_json(silent=True) or {}
    question = (data.get("question") or "").strip()

    if not question:
        return jsonify({"error": "问题不能为空"}), 400

    try:
        result = get_qa_system().get_answer(question)
        return jsonify(result)
    except Exception as e:
        current_app.logger.error(f"问答失败: {e}\n{traceback.format_exc()}")
        return jsonify({"error": f"服务器内部错误: {e}"}), 500
