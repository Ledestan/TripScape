"""
模块名称：足迹打卡 API 路由

GET  /api/spots       获取所有地标坐标（供地图渲染）
GET  /api/footprint/  获取用户足迹列表（占位）
POST /api/footprint/  新增打卡（占位）
"""

import csv

from flask import Blueprint, jsonify

from app.core.config import SPOTS_CSV_PATH

footprint_bp = Blueprint("footprint", __name__)


@footprint_bp.route("/spots", methods=["GET"])
def list_spots():
    """返回所有地标坐标，供前端地图渲染。"""
    spots = []
    with open(SPOTS_CSV_PATH, "r", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            spots.append(
                {
                    "name": row["name"],
                    "lat": float(row["lat"]),
                    "lon": float(row["lon"]),
                }
            )
    return jsonify({"success": True, "data": spots})


@footprint_bp.route("/footprint/", methods=["GET"])
def list_footprints():
    """获取足迹列表（占位）。"""
    return jsonify({"success": True, "data": []})
