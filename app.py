"""
项目名称: 行旅识景：世界著名地标智能识别
创建时间: 2026-06-25

- 本项目数据集来源于 Kaggle 平台，在 data 文件夹中形成了 train 和 valid 文件夹
"""

import sys
import traceback
import warnings

sys.dont_write_bytecode = True
warnings.filterwarnings("ignore", category=UserWarning, module="jieba")

# 导入自定义模块
from app import ImageRecognizer, QASystem
from flask import Flask, jsonify, render_template, request

# 初始化 Flask 应用
app = Flask(__name__)

# 初始化问答系统
qa_system = QASystem()

# 初始化图像识别器
recognizer = ImageRecognizer()


@app.route("/")
def home():
    """入口主页"""
    return render_template("index.html")


@app.route("/app")
def app_page():
    """功能主页"""
    return render_template("app.html")


@app.route("/api/chat", methods=["POST"])
def chat():
    """
    问答 API 接口
    接收 JSON: {"question": "用户问题"}
    返回: {"answer": "回答内容"}
    """
    data = request.json
    question = data.get("question", "").strip()

    if not question:
        return jsonify({"error": "问题不能为空"}), 400

    try:
        result = qa_system.get_answer(question)
        return jsonify(result)
    except Exception as e:
        app.logger.error(f"问答失败: {str(e)}\n{traceback.format_exc()}")
        return jsonify({"error": f"服务器内部错误: {str(e)}"}), 500


@app.route("/api/recognize", methods=["POST"])
def recognize_image():
    """
    图像识别 API 接口
    接收: multipart/form-data 中的 'image' 文件
    返回: 识别结果（包括名称）
    """
    try:
        if "image" not in request.files:
            return jsonify({"error": "请上传图片文件"}), 400

        file = request.files["image"]

        # 检查文件类型
        if not file.filename.lower().endswith((".png", ".jpg", ".jpeg")):
            return jsonify({"error": "仅支持 PNG、JPG 格式图片"}), 400

        # 检查文件大小（限制 2MB）
        file.seek(0, 2)
        file_size = file.tell()
        file.seek(0)

        if file_size > 2 * 1024 * 1024:  # 2MB
            return jsonify({"error": "图片大小不能超过 2MB"}), 400

        # 读取图片二进制数据
        image_data = file.read()

        # 调用识别器
        result = recognizer.recognize(image_data)

        return jsonify(result)

    except Exception as e:
        app.logger.error(f"识别失败: {str(e)}\n{traceback.format_exc()}")
        return jsonify({"error": f"识别失败: {str(e)}"}), 500


# 错误处理
@app.errorhandler(404)
def not_found(e):
    return jsonify({"error": "资源未找到"}), 404


@app.errorhandler(500)
def internal_error(e):
    return jsonify({"error": "服务器内部错误"}), 500


if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=5000)
