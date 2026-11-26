"""
行旅识景 TripScape / 手账画布校验
创建日期: 2026-11-26

手账画布（3:4 版式）的服务端归一化，完成:
    1. 固定版式：逻辑尺寸 720×960、比例 "3:4"，前端传什么都按此校准
    2. 元素白名单：photo / text / fragment 三类，各自只保留允许的字段
    3. 数值夹取：位置、缩放、旋转限制在合理区间，元素数量上限 40
    4. 内容限制：文字 ≤200 字，图片只接受站内路径或 http(s)

依赖:
    Python: >=3.10
    依赖库: 无（仅标准库）

用法:
    from services.journal_canvas import normalize_canvas, CanvasError

    try:
        doc = normalize_canvas(payload.canvas)
    except CanvasError as exc:
        raise HttpError(422, str(exc))

注意:
    1. 这里不做渲染，只保证存进去的 JSON 结构可控、可回放。
    2. 未知字段直接丢弃而不是报错：前端迭代字段时不至于把旧数据卡死。
"""

import re
from urllib.parse import urlparse

CANVAS_WIDTH = 720
CANVAS_HEIGHT = 960
CANVAS_RATIO = "3:4"
MAX_ELEMENTS = 40
MAX_TEXT_LENGTH = 200

ELEMENT_TYPES = ("photo", "text", "fragment")

# 元素允许的字段（其余键一律丢弃）
COMMON_FIELDS = ("id", "type", "x", "y", "width", "height", "rotation", "scale", "opacity", "z")
TYPE_FIELDS = {
    "photo": ("src",),
    "text": ("text", "fontSize", "color", "align", "fontFamily", "fontStyle"),
    "fragment": ("title", "snippet", "year", "landmarkId", "color"),
}

HEX_COLOR = re.compile(r"^#(?:[0-9a-fA-F]{3}|[0-9a-fA-F]{6}|[0-9a-fA-F]{8})$")


class CanvasError(ValueError):
    """画布数据不合法（由 API 层翻译成 422）。"""


def _clamp(value, low, high, default=0.0) -> float:
    """把数值夹到区间内；非数值回落默认值。"""
    try:
        number = float(value)
    except (TypeError, ValueError):
        return float(default)
    return max(low, min(high, number))


def _color(value, fallback: str) -> str:
    """只接受 #rgb / #rrggbb / #rrggbbaa，其余回落默认色。"""
    if isinstance(value, str) and HEX_COLOR.match(value):
        return value
    return fallback


def _image_src(value) -> str:
    """图片地址只允许站内相对路径或 http(s)，拒绝 data:/javascript: 之类。"""
    if not isinstance(value, str):
        return ""
    src = value.strip()
    if not src:
        return ""
    if src.startswith("/"):
        return src[:512]
    parsed = urlparse(src)
    if parsed.scheme in ("http", "https") and parsed.netloc:
        return src[:512]
    return ""


def _text(value, limit: int = MAX_TEXT_LENGTH) -> str:
    """纯文本：去掉控制字符并截断。"""
    if not isinstance(value, str):
        return ""
    cleaned = re.sub(r"[\x00-\x08\x0b-\x1f]", "", value).strip()
    return cleaned[:limit]


def normalize_element(raw, index: int) -> dict:
    """归一化单个元素。

    参数：
        raw   : dict，前端提交的元素
        index : int，元素序号（用于生成缺省 id 与层级）

    返回：
        dict：只含白名单字段的元素

    异常：
        CanvasError：类型缺失或不在白名单内
    """
    if not isinstance(raw, dict):
        raise CanvasError(f"第 {index + 1} 个元素格式不对")

    kind = str(raw.get("type", "")).strip()
    if kind not in ELEMENT_TYPES:
        raise CanvasError(f"第 {index + 1} 个元素类型不支持：{kind or '空'}")

    element = {
        "id": _text(raw.get("id"), 64) or f"{kind}-{index}",
        "type": kind,
        "x": round(_clamp(raw.get("x"), -2000, CANVAS_WIDTH + 2000, 0), 2),
        "y": round(_clamp(raw.get("y"), -2000, CANVAS_HEIGHT + 2000, 0), 2),
        "width": round(_clamp(raw.get("width"), 16, CANVAS_WIDTH * 2, 240), 2),
        "height": round(_clamp(raw.get("height"), 16, CANVAS_HEIGHT * 2, 160), 2),
        "rotation": round(_clamp(raw.get("rotation"), -180, 180, 0), 2),
        "scale": round(_clamp(raw.get("scale"), 0.1, 4, 1), 3),
        "opacity": round(_clamp(raw.get("opacity"), 0.1, 1, 1), 2),
        "z": int(_clamp(raw.get("z"), 0, MAX_ELEMENTS, index)),
    }

    for key in TYPE_FIELDS[kind]:
        element[key] = raw.get(key)

    if kind == "photo":
        element["src"] = _image_src(element.get("src"))
        element["color"] = _color(raw.get("color"), "#1b1b1b")
    elif kind == "text":
        element["text"] = _text(element.get("text"))
        element["fontSize"] = round(_clamp(element.get("fontSize"), 10, 96, 24), 2)
        element["color"] = _color(element.get("color"), "#f5f2ea")
        element["align"] = "center" if raw.get("align") == "center" else "left"
        element["fontFamily"] = _text(raw.get("fontFamily"), 40) or "serif"
        element["fontStyle"] = "italic" if raw.get("fontStyle") == "italic" else "normal"
    else:  # fragment
        element["title"] = _text(element.get("title"), 60)
        element["snippet"] = _text(element.get("snippet"), MAX_TEXT_LENGTH)
        element["year"] = _text(element.get("year"), 16)
        element["landmarkId"] = int(_clamp(element.get("landmarkId"), 0, 10**9, 0))
        element["color"] = _color(raw.get("color"), "#12161d")

    return element


def normalize_canvas(payload) -> dict:
    """归一化整份画布文档。

    参数：
        payload : dict | None，前端提交的画布 JSON

    返回：
        dict：`{version, ratio, width, height, background, elements}`；
        传入空值时返回空文档（表示"没有画布"）

    异常：
        CanvasError：元素过多或结构不合法
    """
    if not payload:
        return {}

    if not isinstance(payload, dict):
        raise CanvasError("画布数据格式不对")

    raw_elements = payload.get("elements")
    if raw_elements is None:
        raw_elements = []
    if not isinstance(raw_elements, list):
        raise CanvasError("画布 elements 必须是数组")
    if len(raw_elements) > MAX_ELEMENTS:
        raise CanvasError(f"画布元素最多 {MAX_ELEMENTS} 个")

    elements = [normalize_element(item, index) for index, item in enumerate(raw_elements)]
    # 层级按数组顺序重排，避免前端传来重复 z 导致回放顺序漂移
    for order, element in enumerate(elements):
        element["z"] = order

    return {
        "version": 1,
        "ratio": CANVAS_RATIO,
        "width": CANVAS_WIDTH,
        "height": CANVAS_HEIGHT,
        "background": _color(payload.get("background"), "#0d1016"),
        "elements": elements,
    }
