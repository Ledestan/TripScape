"""行旅识景 TripScape
创建日期：2025-10-08

检索式识别与文章式问答的单元测试，覆盖:
    1. 问答：主题提取 / 意图切分 / 复合问题 / 拒答（索引不可用回退）
    2. 识别：索引指纹一致性 / 引擎降级路径

依赖:
    需求文件: requirements.txt
    依赖库: 无额外依赖（索引不存在时测回退路径，存在时测真链路）

用法:
    pytest tests/backend/test_retrieval_qa.py -v
"""

import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "backend"))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

django_setup_done = False
try:
    import django

    django.setup()
    django_setup_done = True
except Exception:
    pass

pytestmark = pytest.mark.django_db


# ======================================================================
# 问答：主题提取与意图切分（纯函数，不依赖索引）
# ======================================================================
class TestIntentParsing:
    """主题提取与意图切分的规则行为。"""

    NAME_MAP = {"埃菲尔铁塔": "EiffelTower", "eiffeltower": "EiffelTower", "长城": "GreatWall"}

    def test_single_topic(self):
        from services.article_qa import extract_topics

        assert extract_topics("埃菲尔铁塔多高", self.NAME_MAP) == ["EiffelTower"]

    def test_multi_topic_comparison(self):
        from services.article_qa import extract_topics

        # 比较类问题：两个主题都应命中，且按出现顺序
        assert extract_topics("埃菲尔铁塔和长城哪个更高", self.NAME_MAP) == [
            "EiffelTower",
            "GreatWall",
        ]

    def test_longest_match_wins(self):
        from services.article_qa import extract_topics

        # 名称按长度降序匹配，短名不抢长名
        nm = {"金字塔": "Giza", "吉萨金字塔群": "GizaPyramids"}
        assert extract_topics("吉萨金字塔群在哪里", nm) == ["GizaPyramids"]

    def test_split_by_pauses(self):
        from services.article_qa import split_intents

        # 顿号分隔的复合问题（旧版拆不了的用例）
        parts = split_intents("埃菲尔铁塔多高、什么时候建的")
        assert len(parts) == 2
        assert parts[0][1] == "基本参数"
        assert parts[1][1] == "历史沿革"

    def test_split_by_question_marks(self):
        from services.article_qa import split_intents

        parts = split_intents("埃菲尔铁塔多高？什么时候建的？")
        assert len(parts) == 2

    def test_unknown_intent_no_section(self):
        from services.article_qa import split_intents

        parts = split_intents("随便聊聊")
        assert parts[0][1] is None


# ======================================================================
# 问答：索引可用时的端到端行为（索引缺失则跳过）
# ======================================================================
class TestArticleQa:
    """文章问答主入口行为（依赖 runtime/index 问答索引）。"""

    def _index_ready(self):
        if not django_setup_done:
            return False
        from django.conf import settings

        d = Path(settings.BASE_DIR) / "runtime" / "index"
        return (d / "qa_chunks.json").exists() and (d / "qa_vectors.npy").exists()

    def test_single_fact_question(self):
        if not self._index_ready():
            pytest.skip("问答索引未构建")
        from services.article_qa import answer_question

        r = answer_question("埃菲尔铁塔有多高")
        assert r["known"] is True
        assert "330" in r["answer"]

    def test_compound_question(self):
        if not self._index_ready():
            pytest.skip("问答索引未构建")
        from services.article_qa import answer_question

        r = answer_question("埃菲尔铁塔多高、什么时候建的")
        assert r["known"] is True
        # 两个子项都应被回答
        assert "330" in r["answer"] and "1889" in r["answer"]

    def test_refuse_when_not_in_article(self):
        if not self._index_ready():
            pytest.skip("问答索引未构建")
        from services.article_qa import answer_question

        r = answer_question("泰姬陵门票多少钱")
        # 文章没有门票章节：应拒答且明示"未提及"
        assert "未提及" in r["answer"] or r["known"] is False

    def test_refuse_smalltalk(self):
        if not self._index_ready():
            pytest.skip("问答索引未构建")
        from services.article_qa import answer_question

        r = answer_question("随便聊聊天气")
        assert r["known"] is False

    def test_fallback_when_no_index(self, monkeypatch, tmp_path):
        # 索引路径指向空目录 -> 触发旧管线回退，服务不中断
        if not django_setup_done:
            pytest.skip("Django 未初始化")
        from django.conf import settings as dj_settings
        from services import article_qa

        monkeypatch.setattr(
            article_qa, "get_index", lambda: None, raising=True
        )
        r = article_qa.answer_question("埃菲尔铁塔有多高")
        # 回退旧管线：返回结构完整即可（known 与知识库内容有关）
        assert "answer" in r and "known" in r


# ======================================================================
# 识别：索引与引擎行为
# ======================================================================
class TestRetrievalEngine:
    """检索引擎装载与降级路径。"""

    def test_index_consistency_or_absent(self):
        """索引存在时元数据必须对齐；不存在时 get_engine 返回 None。

        用模块级单例会被其它测试的库状态干扰（单例缓存了旧连接），
        这里直接现场实例化校验文件一致性。
        """
        if not django_setup_done:
            pytest.skip("Django 未初始化")
        idx_dir = Path("runtime/index")
        faiss_file = idx_dir / "landmarks.faiss"
        if not faiss_file.exists():
            from services.retrieval_engine import get_engine

            assert get_engine() is None
            return
        import json

        import faiss

        index = faiss.read_index(str(faiss_file))
        meta = json.loads((idx_dir / "landmarks.meta.json").read_text(encoding="utf-8"))
        assert index.ntotal == len(meta), f"索引 {index.ntotal} 与元数据 {len(meta)} 不一致，请重跑 register_landmarks.py"

    def test_predict_shape(self):
        if not django_setup_done:
            pytest.skip("Django 未初始化")
        from services.retrieval_engine import get_engine

        eng = get_engine()
        if eng is None:
            pytest.skip("识别索引未构建")
        # 用一张精选注册图实测（data/valid 训练集已裁撤）
        from django.conf import settings

        data = Path(settings.BASE_DIR) / "data"
        sample = next(
            iter(
                sorted(p for d in data.iterdir() if d.is_dir() and d.name not in ("train", "_rejected", "valid", "_pending") for p in d.glob("*.jpg"))
            ),
            None,
        )
        if sample is None:
            pytest.skip("精选注册图不存在")
        res = eng.predict(sample.read_bytes(), top_k=3)
        assert 1 <= len(res) <= 3
        tid, conf = res[0]
        assert isinstance(tid, str) and 0.0 <= conf <= 1.0
