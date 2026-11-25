"""
行旅识景 TripScape / 地标故事测试
创建日期: 2026-11-25

校验预设地标故事（ts_landmark_story）的生成与读取，覆盖:
    1. 语料能组装出「整体介绍 + 时间轴 + 分节材料」，时间轴按年份升序
    2. 26 个地标都有预置故事（数量与语料覆盖一致）
    3. GET /api/narrative/story/{landmark_id} 返回结构化内容
    4. 地标不存在 / 没有预置故事时返回 404

依赖:
    Python: >=3.10
    需求文件: requirements.txt
    依赖库:
        pytest
        Django==5.2
        django-ninja

用法（在项目根目录执行）:
    python -m pytest tests/backend/test_narrative_story.py -v

注意:
    1. 只校验结构与顺序，不校验史实措辞（文化解释权归人）。
    2. 需要 runtime/index/qa_chunks.json；缺失时相关用例跳过。
"""

import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
QA_INDEX = ROOT / "runtime" / "index" / "qa_chunks.json"


@pytest.fixture
def story_landmark(db):
    """造一个与语料同名同 target_id 的地标，用于验证接口。"""
    from apps.landmarks.models import Landmark

    return Landmark.objects.create(
        target_id="EiffelTower",
        name="埃菲尔铁塔",
        country="法国",
        region="欧洲",
        lat=48.858,
        lon=2.294,
        intro="测试用简介",
    )


def test_corpus_builds_structured_story(db):
    """build_payload 只摘编原句，并给出升序时间轴。"""
    if not QA_INDEX.exists():
        pytest.skip("文章库未生成，先运行 scripts/build_qa_index.py")
    from services import narrative_story

    chunks = narrative_story.group_chunks()["EiffelTower"]
    payload = narrative_story.build_payload(None, chunks)

    assert payload["intro"], "整体介绍不能为空"
    assert payload["timeline"], "时间轴不能为空"
    years = [item["year"] for item in payload["timeline"]]
    assert years == sorted(years), "时间轴必须按年份升序"
    assert all(isinstance(item["text"], str) and item["text"] for item in payload["timeline"])
    assert any(section["items"] for section in payload["sections"])
    assert payload["source"]


@pytest.mark.django_db
def test_all_landmarks_have_story():
    """语料覆盖的每个地标都应能预置出故事（用测试库现造地标，不依赖种子命令）。"""
    if not QA_INDEX.exists():
        pytest.skip("文章库未生成")
    from apps.landmarks.models import Landmark
    from apps.narrative.models import LandmarkStory
    from services import narrative_story

    chunks = json.loads(QA_INDEX.read_text(encoding="utf-8"))
    targets = sorted({chunk["target_id"] for chunk in chunks})
    names = {chunk["target_id"]: chunk.get("name", chunk["target_id"]) for chunk in chunks}
    for target in targets:
        Landmark.objects.create(
            target_id=target,
            name=names[target],
            lat=0.0,
            lon=0.0,
            intro="测试用简介",
        )

    stats = narrative_story.refresh_stories()
    assert stats["skipped"] == 0
    assert LandmarkStory.objects.count() == len(targets)


@pytest.mark.django_db
def test_story_endpoint_returns_structured_payload(api_client, story_landmark):
    """接口返回整体介绍、时间轴与分节材料，而不是一段待解析的文本。"""
    from services import narrative_story

    narrative_story.refresh_stories()
    resp = api_client.get(f"/api/narrative/story/{story_landmark.id}")
    assert resp.status_code == 200, resp.content
    data = resp.json()["data"]
    assert data["title"] == "埃菲尔铁塔"
    assert data["intro"]
    assert data["timeline"] and data["timeline"][0]["year"] <= data["timeline"][-1]["year"]
    assert isinstance(data["sections"], list)
    assert data["source"]


@pytest.mark.django_db
def test_story_endpoint_404_for_unknown_landmark(api_client):
    """地标不存在时明确 404。"""
    resp = api_client.get("/api/narrative/story/999999")
    assert resp.status_code == 404


@pytest.mark.django_db
def test_story_endpoint_404_when_story_missing(api_client, landmark):
    """地标存在但没有预置故事时同样 404（fixture 的「测试塔」没有语料）。"""
    resp = api_client.get(f"/api/narrative/story/{landmark.id}")
    assert resp.status_code == 404
