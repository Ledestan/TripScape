"""
模块名称：地标图像识别 API 路由

POST /api/recognize
    请求：multipart/form-data，字段名 "image"
    返回：识别结果 JSON
"""

import sys
import traceback

sys.dont_write_bytecode = True
from flask import Blueprint, current_app, jsonify, request

from app.services import ImageRecognizer

recognition_bp = Blueprint("recognition", __name__)

_recognizer = None

ALLOWED_EXTS = (".png", ".jpg", ".jpeg")
MAX_FILE_SIZE = 2 * 1024 * 1024  # 2MB


def get_recognizer():
    """懒加载图像识别器，全局只初始化一次。"""
    global _recognizer
    if _recognizer is None:
        _recognizer = ImageRecognizer()
    return _recognizer


@recognition_bp.route("/recognize", methods=["POST"])
def recognize_image():
    """图像识别接口。"""
    try:
        if "image" not in request.files:
            return jsonify({"error": "请上传图片文件"}), 400

        file = request.files["image"]

        if not file.filename.lower().endswith(ALLOWED_EXTS):
            return jsonify({"error": "仅支持 PNG、JPG 格式图片"}), 400

        # 检查文件大小
        file.seek(0, 2)
        file_size = file.tell()
        file.seek(0)

        if file_size > MAX_FILE_SIZE:
            return jsonify({"error": "图片大小不能超过 2MB"}), 400

        image_data = file.read()
        result = get_recognizer().recognize(image_data)
        return jsonify(result)

    except Exception as e:
        current_app.logger.error(f"识别失败: {e}\n{traceback.format_exc()}")
        return jsonify({"error": f"识别失败: {e}"}), 500
