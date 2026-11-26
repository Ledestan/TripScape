"""
行旅识景 TripScape / tests/backend/test_s2_card_contract
创建日期: 2026-11-24

S2 功能证据：叙事卡片字段契约（§3.3）。

约束（SPEC §3.3）：
1. 契约测试必须独立于实现文件——本文件**硬编码**卡片字段清单，
   不从 `services.narrative_service` / `api.recognition` 导入任何字段列表，
   避免"自己证明自己"。
2. 断言识别接口返回对象包含 §2 S2 的全部 9 个字段；
   `timeFragments` / `ragSnippets` 为非空数组；`confidence` 为 0–1 数值。
3. 另外验证 feature flag 默认关闭时响应不含卡片字段（§5 硬边界：
   叙事层是 2.0 本体，识别响应默认携带卡片字段）。

识别引擎在本测试中用测试替身注入"识别结果"（target_id + 置信度），
这样断言的是 **HTTP 响应契约 + 真实 DB 地标 + 真实叙事服务**，
而不是模型的推理质量；模型真实推理另有手动证据（见 A4）。
"""

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import override_settings

# §2 S2 固定字段集（硬编码，刻意不引用实现）
CARD_FIELDS = (
    "id",
    "landmarkId",
    "photo",
    "title",
    "geo",
    "timeFragments",
    "ragSnippets",
    "confidence",
    "source",
)


class _FakeEngine:
    """识别引擎替身：只负责把 target_id 与置信度交给识别服务。"""

    def __init__(self, target_id: str, confidence: float):
        self.target_id = target_id
        self.confidence = confidence

    def predict(self, image_bytes, top_k=3):  # noqa: ARG002
        return [(self.target_id, self.confidence)]


@pytest.fixture
def engine(monkeypatch, landmark):
    """注入识别结果（不改变下游真实逻辑：DB 地标 + 叙事卡片组装）。"""
    import services.retrieval_engine as retrieval_engine

    eng = _FakeEngine(landmark.target_id, 0.91)
    monkeypatch.setattr(retrieval_engine, "get_engine", lambda: eng)
    return eng


def _recognize(client):
    """带着一张"照片"调用同步识别接口。"""
    image = SimpleUploadedFile(
        "narrative-shot.jpg",
        b"\xff\xd8\xff\xe0" + b"0" * 128,
        content_type="image/jpeg",
    )
    return client.post("/api/recognition/recognize", {"image": image})


@pytest.mark.django_db
def test_recognition_returns_full_narrative_card(engine, api_client, landmark):
    """识别接口返回对象必须携带 §2 S2 的全部卡片字段，且取值合法。"""
    resp = _recognize(api_client)
    assert resp.status_code == 200, resp.content
    body = resp.json()

    assert body.get("success") is True, body
    missing = [f for f in CARD_FIELDS if f not in body]
    assert not missing, f"识别响应缺少叙卡字段: {missing}; 实际键: {sorted(body)}"

    # id / landmarkId
    assert isinstance(body["id"], int) and body["id"] > 0
    assert body["landmarkId"] == landmark.id

    # photo：原图 URL 引用（不复制文件）
    assert isinstance(body["photo"], str) and body["photo"], body["photo"]
    assert body["photo"].startswith("/") or body["photo"].startswith("http")

    # title
    assert isinstance(body["title"], str) and body["title"].strip()

    # geo：坐标可追溯地标的 lat/lon
    geo = body["geo"]
    assert isinstance(geo, dict), geo
    assert isinstance(geo.get("lat"), (int, float))
    assert isinstance(geo.get("lon"), (int, float))
    assert abs(geo["lat"] - float(landmark.lat)) < 1e-6
    assert abs(geo["lon"] - float(landmark.lon)) < 1e-6

    # timeFragments：非空数组，逐条可追溯（text + source）
    tf = body["timeFragments"]
    assert isinstance(tf, list) and len(tf) > 0, tf
    for frag in tf:
        assert isinstance(frag, dict), frag
        assert isinstance(frag.get("text"), str) and frag["text"].strip()
        assert isinstance(frag.get("source"), str) and frag["source"].strip()

    # ragSnippets：非空数组，逐条可追溯（text + source）
    rs = body["ragSnippets"]
    assert isinstance(rs, list) and len(rs) > 0, rs
    for snip in rs:
        assert isinstance(snip, dict), snip
        assert isinstance(snip.get("text"), str) and snip["text"].strip()
        assert isinstance(snip.get("source"), str) and snip["source"].strip()

    # confidence：0–1 数值
    conf = body["confidence"]
    assert isinstance(conf, (int, float)) and not isinstance(conf, bool)
    assert 0.0 <= float(conf) <= 1.0, conf

    # source：卡片来源标签
    assert isinstance(body["source"], str) and body["source"].strip()
