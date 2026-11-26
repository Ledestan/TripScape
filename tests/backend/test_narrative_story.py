"""
行旅识景 TripScape / 地标页面预置测试
创建日期: 2026-11-25

校验「一个地标一个页面文件」的生成与读取，覆盖:
    1. 页面文件结构（整体介绍 / 时间轴升序 / 分节材料 / 卡片材料）
    2. content/landmarks 覆盖了文章库里的全部地标
    3. GET /api/narrative/story/{id} 与 /card/{id} 都只读文件，不触发分词与向量索引
    4. 地标不存在 / 没有页面文件时返回 404

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
    2. 「不触发分词」用的是故障注入：把问答索引替换成必抛异常的桩。
"""

import json
from pathlib import Path
import pytest

ROOT = Path(__file__).resolve().parents[2]
PAGES_DIR = ROOT / "backend" / "content" / "landmarks"
QA_INDEX = ROOT / "runtime" / "index" / "qa_chunks.json"


@pytest.fixture
def page_landmark(db):
    """造一个与已生成页面同 target_id 的地标，用于验证接口。"""
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


def test_page_files_cover_corpus_targets():
    """页面文件数量与文章库覆盖的地标数一致。"""
    if not QA_INDEX.exists():
        pytest.skip("文章库未生成，先运行 scripts/build_qa_index.py")
    chunks = json.loads(QA_INDEX.read_text(encoding="utf-8"))
    targets = {chunk["target_id"] for chunk in chunks}
    files = list(PAGES_DIR.glob("*.json"))
    assert len(files) == len(targets)
    assert {path.stem for path in files} == targets


@pytest.mark.parametrize("path", sorted(PAGES_DIR.glob("*.json")), ids=lambda p: p.stem)
def test_page_structure(path):
    """每个页面文件都要有整体介绍、升序时间轴与出处。"""
    page = json.loads(path.read_text(encoding="utf-8"))
    assert page["landmark"], f"{path.name} 缺少地标名"
    assert page["intro"].strip(), f"{path.name} 缺少整体介绍"
    assert page["timeline"], f"{path.name} 缺少时间轴"
    years = [item["year"] for item in page["timeline"] if item["year"] is not None]
    assert years == sorted(years), f"{path.name} 时间轴未按年份升序"
    assert all(item["text"] for item in page["timeline"])
    # 页面本身不再展示出处与摘录；snippets 仅供识别卡片的文献字段
    assert page["snippets"], f"{path.name} 缺少卡片用的文献字段"
    assert len(page["sections"]) >= 2, f"{path.name} 分节太少"


@pytest.mark.django_db
def test_story_endpoint_returns_structured_payload(api_client, page_landmark):
    """接口返回整体介绍、时间轴与分节材料，直接来自页面文件。"""
    resp = api_client.get(f"/api/narrative/story/{page_landmark.id}")
    assert resp.status_code == 200, resp.content
    data = resp.json()["data"]
    assert data["title"] == "埃菲尔铁塔"
    assert data["intro"]
    assert (
        data["timeline"] and data["timeline"][0]["year"] <= data["timeline"][-1]["year"]
    )
    assert isinstance(data["sections"], list) and len(data["sections"]) >= 2


@pytest.mark.django_db
def test_card_endpoint_does_not_touch_qa_index(api_client, page_landmark, monkeypatch):
    """卡片与故事都不应触发问答索引（jieba 分词只服务 /api/qa）。"""
    from services import article_qa

    def explode(*args, **kwargs):
        raise AssertionError("打开地标不应构建问答索引（jieba 只用于问答）")

    monkeypatch.setattr(article_qa, "get_index", explode)

    card = api_client.get(f"/api/narrative/card/{page_landmark.id}")
    assert card.status_code == 200, card.content
    assert card.json()["data"]["ragSnippets"], "卡片应带预置文献摘录"

    story = api_client.get(f"/api/narrative/story/{page_landmark.id}")
    assert story.status_code == 200, story.content


@pytest.mark.django_db
def test_story_endpoint_404_for_unknown_landmark(api_client):
    """地标不存在时明确 404。"""
    resp = api_client.get("/api/narrative/story/999999")
    assert resp.status_code == 404


@pytest.mark.django_db
def test_story_endpoint_404_when_page_missing(api_client, landmark):
    """地标存在但没有页面文件时同样 404（fixture 的「测试塔」没有页面）。"""
    resp = api_client.get(f"/api/narrative/story/{landmark.id}")
    assert resp.status_code == 404
