"""
行旅识景 TripScape / 地标故事测试
创建日期: 2026-11-25

校验「一个地标一篇故事」的产物与接口，覆盖:
    1. stories/ 每篇文档的结构（front-matter、标题、出处、正文长度）
    2. 故事篇数与文章库地标数一致，避免遗漏或多出
    3. GET /api/narrative/story/{landmark_id} 返回该地标的故事正文
    4. 地标不存在时返回 404，地标没有故事时也返回 404

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
    1. 只校验结构与非空，不校验史实措辞（文化解释权归人）。
    2. 故事由 scripts/build_landmark_stories.py 生成，失败通常意味着没有重新生成。
"""

import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
STORY_DIR = ROOT / "stories"
QA_INDEX = ROOT / "runtime" / "index" / "qa_chunks.json"


@pytest.mark.parametrize("path", sorted(STORY_DIR.glob("*.md")), ids=lambda p: p.stem)
def test_story_document_structure(path):
    """每篇故事必须有 front-matter、一级标题与不少于 300 字正文。"""
    text = path.read_text(encoding="utf-8")
    assert text.startswith("---\n"), f"{path.name} 缺少 front-matter"
    assert "\n---\n" in text, f"{path.name} front-matter 未闭合"
    assert "\n# " in text, f"{path.name} 缺少一级标题"
    assert "## 出处" in text, f"{path.name} 缺少出处区块"
    body = text.split("\n---\n", 1)[1]
    assert len(body.strip()) >= 300, f"{path.name} 正文过短"


def test_story_count_matches_article_corpus():
    """故事篇数与文章库覆盖的地标数一致（不依赖数据库种子）。"""
    if not QA_INDEX.exists():
        pytest.skip("文章库未生成，先运行 scripts/build_qa_index.py")
    chunks = json.loads(QA_INDEX.read_text(encoding="utf-8"))
    targets = {chunk["target_id"] for chunk in chunks}
    assert len(list(STORY_DIR.glob("*.md"))) == len(targets)


@pytest.mark.django_db
def test_story_endpoint_returns_markdown(api_client):
    """接口返回的正文必须包含该地标名，且来自 stories/ 文档。"""
    from apps.landmarks.models import Landmark

    landmark = Landmark.objects.create(
        target_id="EiffelTower",
        name="埃菲尔铁塔",
        country="法国",
        region="欧洲",
        lat=48.858,
        lon=2.294,
        intro="测试用简介",
    )
    resp = api_client.get(f"/api/narrative/story/{landmark.id}")
    assert resp.status_code == 200, resp.content
    data = resp.json()["data"]
    assert "埃菲尔铁塔" in data["markdown"]
    assert data["filename"].endswith(".md")
    assert data["source"]


@pytest.mark.django_db
def test_story_endpoint_404_for_unknown_landmark(api_client):
    """地标不存在时明确 404，不返回空故事。"""
    resp = api_client.get("/api/narrative/story/999999")
    assert resp.status_code == 404


@pytest.mark.django_db
def test_story_endpoint_404_when_story_missing(api_client, landmark):
    """地标存在但没有故事文档时同样 404（fixture 的「测试塔」没有故事）。"""
    resp = api_client.get(f"/api/narrative/story/{landmark.id}")
    assert resp.status_code == 404
