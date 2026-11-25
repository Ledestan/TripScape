"""A4 技术可信度证据 · 低置信度候选机制（SPEC §3.7）。

这不是新能力的测试，而是对**既有识别闸门**的可运行证据：
    settings.RECOG_CONFIDENCE_THRESHOLD（默认 0.35）
    -> recognition_service._build_result 判定 low_confidence
    -> 命中时**附带** candidates（top-3 去掉 top-1）
    -> 响应仍是 success=true、top-1 仍是默认结果；候选是附加区块
    -> 前端 MessageBar 据此把候选渲染成可点列表

注意：严格说这不是"拒答"——真正的拒答语义在问答侧（article_qa 的 UNKNOWN_ANSWER）。

断言：
1. 低于阈值：low_confidence=True，candidates 非空且字段完整，候选置信度均低于阈值；
2. 高于阈值：low_confidence=False，candidates 为空（不额外给候选）；
3. 识别响应仍保留 confidence，供卡片与看板使用。

识别引擎用测试替身注入（只替换"模型输出"，其余走真实服务与真实地标）。
"""

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile

# 与 settings.RECOG_CONFIDENCE_THRESHOLD 的默认值一致；同时从测试内直接读取
# settings，避免实现改动阈值后证据失配（阈值本身是配置，不是实现字段列表）。
from django.conf import settings


class _FakeEngine:
    def __init__(self, results):
        self._results = results

    def predict(self, image_bytes, top_k=3):  # noqa: ARG002
        return list(self._results)


@pytest.fixture
def two_landmarks(db):
    from apps.landmarks.models import Landmark

    first = Landmark.objects.create(
        target_id="LowConfA", name="低置信甲", lat=1.0, lon=2.0, intro="甲简介", image_url="/lmimg/A.jpg"
    )
    second = Landmark.objects.create(
        target_id="LowConfB", name="低置信乙", lat=3.0, lon=4.0, intro="乙简介", image_url="/lmimg/B.jpg"
    )
    return first, second


def _post(client):
    image = SimpleUploadedFile("a4.jpg", b"\xff\xd8\xff\xe0" + b"0" * 64, content_type="image/jpeg")
    return client.post("/api/recognition/recognize", {"image": image})


def _patch_engine(monkeypatch, results):
    import services.retrieval_engine as retrieval_engine

    monkeypatch.setattr(retrieval_engine, "get_engine", lambda: _FakeEngine(results))


@pytest.mark.django_db
def test_low_confidence_returns_candidates(monkeypatch, api_client, two_landmarks):
    """低于阈值 -> 拒答硬判，改给候选（含字段完整性与阈值一致性）。"""
    threshold = float(settings.RECOG_CONFIDENCE_THRESHOLD)
    first, second = two_landmarks
    _patch_engine(monkeypatch, [(first.target_id, threshold - 0.1), (second.target_id, threshold - 0.2)])

    resp = _post(api_client)
    assert resp.status_code == 200, resp.content
    body = resp.json()

    assert body["success"] is True
    assert body["confidence"] < threshold
    assert body["low_confidence"] is True
    assert isinstance(body["candidates"], list) and body["candidates"], body
    for cand in body["candidates"]:
        for field in ("landmark_id", "target_id", "name", "confidence", "image_url"):
            assert field in cand, f"候选缺少字段 {field}: {sorted(cand)}"
        assert float(cand["confidence"]) < threshold


@pytest.mark.django_db
def test_high_confidence_has_no_candidates(monkeypatch, api_client, two_landmarks):
    """高于阈值 -> 正常给出结果，不附加候选（避免噪声推荐）。"""
    threshold = float(settings.RECOG_CONFIDENCE_THRESHOLD)
    first, second = two_landmarks
    _patch_engine(monkeypatch, [(first.target_id, min(0.99, threshold + 0.5)), (second.target_id, 0.1)])

    resp = _post(api_client)
    assert resp.status_code == 200, resp.content
    body = resp.json()

    assert body["success"] is True
    assert body["confidence"] >= threshold
    assert body["low_confidence"] is False
    assert body["candidates"] == []
