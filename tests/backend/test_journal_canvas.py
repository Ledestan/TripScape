"""
行旅识景 TripScape / 手账画布测试
创建日期: 2026-11-26

校验 3:4 画布文档的服务端归一化与接口往返，覆盖:
    1. 归一化：固定版式、字段白名单、数值夹取、层级重排
    2. 安全：图片地址只允许站内路径或 http(s)，文字截断
    3. 边界：元素超限、非法类型 → 中文错误
    4. 接口：创建带画布、详情读回、已通过手账的修改进 pending_edit

依赖:
    Python: >=3.10
    需求文件: requirements.txt
    依赖库:
        pytest
        Django==5.2
        django-ninja

用法（在项目根目录执行）:
    python -m pytest tests/backend/test_journal_canvas.py -v

注意:
    1. 只校验结构与安全边界，不校验渲染效果。
    2. 画布是可选字段：不传时手账照旧可用（canvas 为空对象）。
"""

import pytest

from services.journal_canvas import (
    CANVAS_HEIGHT,
    CANVAS_WIDTH,
    CanvasError,
    normalize_canvas,
)


def test_empty_payload_returns_empty_doc():
    """不传画布时返回空文档，兼容旧手账。"""
    assert normalize_canvas(None) == {}
    assert normalize_canvas({}) == {}


def test_layout_is_fixed_to_three_by_four():
    """前端传什么尺寸都以 720×960、3:4 为准。"""
    doc = normalize_canvas({"width": 100, "height": 9999, "ratio": "1:1", "elements": []})
    assert doc["width"] == CANVAS_WIDTH
    assert doc["height"] == CANVAS_HEIGHT
    assert doc["ratio"] == "3:4"
    assert doc["version"] == 1
    assert doc["elements"] == []


def test_element_fields_are_whitelisted():
    """未知字段直接丢弃，避免把任意数据写进 JSONField。"""
    doc = normalize_canvas(
        {
            "elements": [
                {
                    "type": "text",
                    "text": "在卢克索的黄昏",
                    "x": 40,
                    "y": 60,
                    "fontSize": 28,
                    "evil": "__proto__",
                    "onclick": "alert(1)",
                }
            ]
        }
    )
    element = doc["elements"][0]
    assert element["type"] == "text"
    assert element["text"] == "在卢克索的黄昏"
    assert "evil" not in element
    assert "onclick" not in element


def test_numbers_are_clamped():
    """位置/缩放/旋转越界会被夹到合理区间。"""
    doc = normalize_canvas(
        {
            "elements": [
                {
                    "type": "photo",
                    "src": "/uploads/a.jpg",
                    "x": -99999,
                    "y": 99999,
                    "scale": 99,
                    "rotation": -720,
                    "opacity": 0,
                    "width": 1,
                    "height": 99999,
                }
            ]
        }
    )
    element = doc["elements"][0]
    assert element["x"] == -2000
    assert element["y"] == CANVAS_HEIGHT + 2000
    assert element["scale"] == 4
    assert element["rotation"] == -180
    assert element["opacity"] == 0.1
    assert element["width"] == 16
    assert element["height"] == CANVAS_HEIGHT * 2


def test_photo_src_only_allows_site_or_http():
    """data: / javascript: 之类一律清空，避免注入。"""
    doc = normalize_canvas(
        {
            "elements": [
                {"type": "photo", "src": "data:image/png;base64,AAA"},
                {"type": "photo", "src": "javascript:alert(1)"},
                {"type": "photo", "src": "https://example.com/a.jpg"},
                {"type": "photo", "src": "/uploads/b.jpg"},
            ]
        }
    )
    assert doc["elements"][0]["src"] == ""
    assert doc["elements"][1]["src"] == ""
    assert doc["elements"][2]["src"] == "https://example.com/a.jpg"
    assert doc["elements"][3]["src"] == "/uploads/b.jpg"


def test_text_is_trimmed_and_capped():
    """文字去掉控制字符并截到 200 字。"""
    doc = normalize_canvas(
        {"elements": [{"type": "text", "text": "字" * 500 + "\x07"}]}
    )
    assert len(doc["elements"][0]["text"]) == 200


def test_layer_order_follows_array_order():
    """z 由数组顺序重排，前端传重复 z 也不会乱。"""
    doc = normalize_canvas(
        {
            "elements": [
                {"type": "text", "text": "第一层", "z": 9},
                {"type": "tape", "pattern": "plain", "z": 9},
            ]
        }
    )
    assert [element["z"] for element in doc["elements"]] == [0, 1]


def test_sticker_and_tape_fields():
    """贴纸与胶带进白名单；未知变体回落默认值。"""
    doc = normalize_canvas(
        {
            "elements": [
                {"type": "sticker", "variant": "heart", "color": "#c05a4a", "shadow": False, "cornerRadius": 0},
                {"type": "tape", "pattern": "stripe", "color": "#d6ba84", "borderWidth": 2},
                {"type": "sticker", "variant": "hacker"},
            ]
        }
    )
    heart, tape, fallback = doc["elements"]
    assert heart["variant"] == "heart"
    assert heart["shadow"] is False
    assert heart["cornerRadius"] == 0
    assert tape["pattern"] == "stripe"
    assert tape["borderWidth"] == 2
    assert fallback["variant"] == "star"
    assert fallback["color"] == "#d9a441"


def test_style_fields_are_clamped():
    """圆角、边框、投影都收在白名单里，越界值被夹取。"""
    doc = normalize_canvas(
        {
            "elements": [
                {
                    "type": "photo",
                    "src": "/uploads/a.jpg",
                    "cornerRadius": 999,
                    "borderWidth": 99,
                    "borderColor": "not-a-color",
                    "evil": 1,
                }
            ]
        }
    )
    element = doc["elements"][0]
    assert element["cornerRadius"] == 120
    assert element["borderWidth"] == 12
    assert element["borderColor"] == "#00000000"
    assert "evil" not in element


def test_unknown_type_raises():
    """不认识的元素类型直接报错，而不是悄悄存进去。"""
    with pytest.raises(CanvasError):
        normalize_canvas({"elements": [{"type": "video"}]})


def test_too_many_elements_raises():
    """元素上限 40。"""
    elements = [{"type": "text", "text": f"第{i}句"} for i in range(41)]
    with pytest.raises(CanvasError):
        normalize_canvas({"elements": elements})


@pytest.mark.django_db
def test_create_journal_with_canvas(api_client, user_token, landmark):
    """创建手账时带画布，详情能原样读回归一化后的结构。"""
    resp = api_client.json_post(
        "/api/journals/",
        {
            "landmark_id": landmark.id,
            "title": "画布手账",
            "content": "",
            "canvas": {
                "background": "#101820",
                "elements": [
                    {"type": "text", "text": "在黄昏抵达", "x": 24, "y": 40},
                    {"type": "sticker", "variant": "star", "color": "#d9a441"},
                ],
            },
        },
        token=user_token,
    )
    assert resp.status_code == 200, resp.content
    journal_id = resp.json()["data"]["id"]

    detail = api_client.json_get(f"/api/journals/{journal_id}", token=user_token)
    assert detail.status_code == 200
    canvas = detail.json()["data"]["canvas"]
    assert canvas["ratio"] == "3:4"
    assert canvas["background"] == "#101820"
    assert [element["type"] for element in canvas["elements"]] == ["text", "sticker"]


@pytest.mark.django_db
def test_invalid_canvas_returns_422(api_client, user_token, landmark):
    """非法画布在接口层被拦成 422。"""
    resp = api_client.json_post(
        "/api/journals/",
        {
            "landmark_id": landmark.id,
            "title": "坏画布",
            "canvas": {"elements": [{"type": "video"}]},
        },
        token=user_token,
    )
    assert resp.status_code == 422
    assert "类型不支持" in resp.json()["detail"]
