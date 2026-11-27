"""
行旅识景 TripScape / apps/landmarks/validators

地标字段校验（API 与预置页面生成共用）。

安全口径：
- target_id 直接参与磁盘文件名（backend/content/landmarks/<target_id>.json），
  必须限定为【字母/数字/下划线/短横线】，否则可构造 ../ 穿越读取或写入
  页面目录之外的文件；
- 经纬度必须落在物理区间内，避免脏数据进入地球渲染与检索排序。
"""

import re

# 与 Landmark.target_id 列宽一致
TARGET_ID_RE = re.compile(r"^[A-Za-z0-9_-]{1,50}$")
NAME_MAX = 100
SHORT_TEXT_MAX = 64
IMAGE_URL_MAX = 512
INTRO_MAX = 20000
LAT_RANGE = (-90.0, 90.0)
LON_RANGE = (-180.0, 180.0)


def is_valid_target_id(value: str) -> bool:
    """target_id 是否安全可用（同时可作文件名）。"""
    return bool(isinstance(value, str) and TARGET_ID_RE.match(value))


def clean_target_id(value, fallback: str = "") -> str:
    """校验并返回 target_id；非法抛 ValueError（由 API 翻译成 400）。"""
    tid = (value or "").strip() if isinstance(value, str) else ""
    tid = tid or (fallback or "").strip()
    if not is_valid_target_id(tid):
        raise ValueError("target_id 仅支持英文字母、数字、下划线、短横线（1-50 位）")
    return tid


def clean_coordinates(lat, lon) -> tuple[float, float]:
    """校验经纬度区间；非法抛 ValueError。"""
    try:
        lat_f = float(lat)
        lon_f = float(lon)
    except (TypeError, ValueError):
        raise ValueError("经纬度必须是数字")
    if not (LAT_RANGE[0] <= lat_f <= LAT_RANGE[1]):
        raise ValueError("纬度必须在 -90 ~ 90 之间")
    if not (LON_RANGE[0] <= lon_f <= LON_RANGE[1]):
        raise ValueError("经度必须在 -180 ~ 180 之间")
    return lat_f, lon_f
