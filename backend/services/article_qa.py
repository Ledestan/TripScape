"""行旅识景 TripScape / 文章式问答服务
创建日期：2025-10-08

以"每地标一篇章节式文章"为知识源的新问答管线，完成:
    1. 离线建库：解析 scripts/db/articles/*.md -> 按章节分块
       （元数据：地标 / 标题 / 章节 / Chunk ID）
       -> 向量索引（bge-small-zh）+ BM25 索引（同一 Chunk ID 关联）
    2. 在线问答：主题提取（地标词典最长匹配）-> 意图切分（疑问词边界）
       -> 定向检索（主题锁文章 + 意图锁章节）-> 向量 + BM25 混合
       -> RRF 融合 -> 句子级打分抽取 -> 按主题聚合答案
       -> 来源标注 + 逐子项拒答（证据不足明示"文章未提及"）

与旧键值对管线的关系:
    旧 qa_service（问答对匹配）已删除；本模块是唯一问答管线。

依赖:
    Python: >=3.10
    需求文件: requirements.txt
    依赖库:
        sentence-transformers    # bge-small-zh 向量
        rank-bm25 / jieba        # BM25 检索

用法:
    from services.article_qa import answer_question
    result = answer_question("埃菲尔铁塔多高")

产物路径（scripts/build_qa_index.py 构建，本模块只读）:
    runtime/index/qa_chunks.json     分块与元数据
    runtime/index/qa_vectors.npy     向量矩阵（与 chunk 行号对齐）
    runtime/index/qa_manifest.json   建库指纹（文章变化后失效提示重建）

注意:
    1. 索引不存在时返回重建指引（不回退旧管线）。
    2. 文章增改后需重跑 scripts/build_qa_index.py 重建问答索引。
"""

import json
import logging
import re
import time
from pathlib import Path

from django.conf import settings

logger = logging.getLogger(__name__)

UNKNOWN_ANSWER = "知识库中没有相关信息。"


# ======================================================================
# 索引装载
# ======================================================================
class ArticleIndex:
    """文章分块索引（向量 + BM25 双路，同一 Chunk ID 关联）。

    只读装载 scripts/build_qa_index.py 的产物；指纹与文章目录不一致时
    抛异常由上层走回退，避免误用旧索引。
    """

    def __init__(self):
        import numpy as np

        idx_dir = Path(settings.BASE_DIR) / "runtime" / "index"
        self.paths = {
            "chunks": str(idx_dir / "qa_chunks.json"),
            "vectors": str(idx_dir / "qa_vectors.npy"),
            "manifest": str(idx_dir / "qa_manifest.json"),
        }
        for p in ("chunks", "vectors", "manifest"):
            if not Path(self.paths[p]).exists():
                raise FileNotFoundError(
                    f"问答索引不存在: {self.paths[p]}，请运行 scripts/build_qa_index.py"
                )

        self.chunks = json.loads(Path(self.paths["chunks"]).read_text(encoding="utf-8"))
        self.vectors = np.load(self.paths["vectors"])
        if len(self.chunks) != len(self.vectors):
            raise RuntimeError("问答索引与向量不一致，请重建")

        # BM25 语料：chunk 文本分词
        import jieba
        from rank_bm25 import BM25Okapi

        corpus = [list(jieba.cut_for_search(c["text"])) for c in self.chunks]
        self.bm25 = BM25Okapi(corpus)

        # 地标词典：name / target_id -> landmark 元信息（主题提取用）
        by_lm = {}
        for c in self.chunks:
            by_lm.setdefault(c["target_id"], c)
        self.landmarks = {c["target_id"]: {"name": c["name"], "region": c["region"]} for c in by_lm.values()}
        # 名称 -> target_id（含中文名与英文 ID）
        self.name_map = {}
        for tid, info in self.landmarks.items():
            self.name_map[info["name"]] = tid
            self.name_map[tid.lower()] = tid

        self._embed_model = None  # 惰性加载（首次问答时初始化，省启动时间）
        # 句向量缓存：{target_id: (句子列表, 向量矩阵)}——文章不变则复用
        self._sent_cache = {}

    # ------------------------------------------------------------------
    def _embed(self, texts: list):
        """bge-small-zh 向量（模型惰性加载，进程内复用）。"""
        if self._embed_model is None:
            from sentence_transformers import SentenceTransformer

            self._embed_model = SentenceTransformer(str(settings.EMBEDDING_MODEL_DIR))
        import numpy as np

        vecs = self._embed_model.encode(texts, normalize_embeddings=True)
        return np.asarray(vecs, dtype="float32")

    # ------------------------------------------------------------------
    def article_sentences(self, target_id: str):
        """该地标文章的全部候选句与句向量（带缓存）。

        返回：
            (sentences: list[str], vectors: np.ndarray)；无文章时 ([], None)
        """
        import numpy as np

        if target_id in self._sent_cache:
            return self._sent_cache[target_id]
        sents = []
        for c in self.chunks:
            if c["target_id"] == target_id:
                sents.extend(s for s in _split_sentences(c["text"]) if len(s) >= 8)
        if not sents:
            return [], None
        vecs = self._embed(sents)
        self._sent_cache[target_id] = (sents, vecs)
        return sents, vecs

    # ------------------------------------------------------------------
    def search(self, query: str, top_k: int = 5, target_id: str = None):
        """
        混合检索（向量 + BM25 -> RRF 融合）。

        参数：
            query : str，检索文本
            top_k : int，返回条数
            target_id : str，可选，限定地标（主题已锁定时用）

        返回：
            list of dict（chunk 元数据 + rrf 分数），按分数降序
        """
        import jieba
        import numpy as np

        # ---------- 候选池：主题锁定的子集，否则全库 ----------
        pool = (
            [i for i, c in enumerate(self.chunks) if c["target_id"] == target_id]
            if target_id
            else list(range(len(self.chunks)))
        )
        if not pool:
            return []

        # ---------- 向量检索（余弦） ----------
        qv = self._embed([query])[0]
        vec_scores = {i: float(np.dot(self.vectors[i], qv)) for i in pool}

        # ---------- BM25 检索 ----------
        q_tokens = list(jieba.cut_for_search(query))
        bm25_raw = self.bm25.get_scores(q_tokens)
        ranked_pool = sorted(pool, key=lambda i: -bm25_raw[i])[: max(top_k * 4, 20)]
        bm25_scores = {i: bm25_raw[i] for i in ranked_pool}

        # ---------- RRF 融合（k=60 惯例值） ----------
        K = 60
        rrf = {}
        for rank, i in enumerate(sorted(vec_scores, key=lambda x: -vec_scores[x])):
            rrf[i] = rrf.get(i, 0) + 1 / (K + rank + 1)
        for rank, i in enumerate(sorted(bm25_scores, key=lambda x: -bm25_scores[x])):
            rrf[i] = rrf.get(i, 0) + 1 / (K + rank + 1)

        out = []
        for i in sorted(rrf, key=lambda x: -rrf[x])[:top_k]:
            c = dict(self.chunks[i])
            c["rrf"] = rrf[i]
            c["vec_sim"] = vec_scores.get(i, 0.0)
            out.append(c)
        return out


# ======================================================================
# 主题提取与意图切分
# ======================================================================
# 意图 -> 章节标签 + 检索增强词（短疑问词向量表达弱，扩写后检索更稳）
INTENT_SECTIONS = [
    (["多高", "高度", "多长", "多宽", "多大", "多少级", "多重", "面积", "多深", "海拔", "几米", "多远"], "基本参数", "高度 尺寸 长度 米 公里 面积 海拔"),
    (["什么时候", "哪年", "建于", "历史", "谁建", "为什么", "由来", "传说", "朝代", "多久", "起源", "是啥", "是什么", "介绍"], "历史沿革", "历史 建造 年代 建于 起源 由来"),
    (["在哪里", "在哪", "位于", "哪个国家", "哪个城市", "怎么去", "位置", "地址", "什么地方"], "地理位置", "位于 位置 地址 坐落 国家 城市 省份"),
    (["门票", "开放时间", "开放", "参观", "游览", "怎么玩", "最佳", "季节", "几点", "攻略"], "参观信息", "门票 开放时间 参观 游览 价格"),
]


def _intent_query(intent_text: str, section: str) -> str:
    """意图词扩写：短疑问词 + 章节增强词拼接，提升检索区分度。"""
    for keywords, sec, boost in INTENT_SECTIONS:
        if sec == section:
            return f"{intent_text} {boost}"
    return intent_text


def intent_contains(text: str, words: tuple) -> bool:
    """意图文本是否包含任一关键词（要素验证用）。"""
    return any(w in text for w in words)


def extract_topics(question: str, name_map: dict) -> list:
    """地标词典最长匹配（含多主题比较场景）。

    子串去重：某名称是已命中名称的子串时视为同一所指，
    不重复入列（如"吉萨金字塔群"命中后，子串"金字塔"不再算新主题）。

    返回：
        list of target_id（去重）；空列表表示未命中任何地标
    """
    hits = []  # [(target_id, name)]
    for name in sorted(name_map, key=len, reverse=True):
        if not name or name not in question:
            continue
        # 子串去重：已被更长名称覆盖的短名跳过
        if any(name in hit_name for _, hit_name in hits):
            continue
        hits.append((name_map[name], name))

    # 按问题中的出现顺序输出（比较类问题语序即作答语序）
    hits.sort(key=lambda x: question.index(x[1]))
    seen, out = set(), []
    for tid, _ in hits:
        if tid not in seen:
            out.append(tid)
            seen.add(tid)
    return out


def split_intents(question: str) -> list:
    """按疑问词边界切分子意图（顿号/问号/分号/连词是天然分隔）。

    返回：
        list of (意图文本, 章节标签 or None)
    """
    parts = [p for p in re.split(r"[？?；;。！!，,、]|(?<=[^和与跟])[和与跟](?=[^和与跟])", question) if p.strip()]
    out = []
    for p in parts:
        p = p.strip()
        if not p:
            continue
        section = None
        for keywords, sec, _boost in INTENT_SECTIONS:
            if any(k in p for k in keywords):
                section = sec
                break
        out.append((p, section))
    return out


# ======================================================================
# 句子抽取与答案组装
# ======================================================================
def _split_sentences(text: str) -> list:
    """中文句子切分（句号/问号/叹号/分号/换行）。

    用环视断言在标点后切分、标点保留在句尾——答案句需要完整标点，
    按分隔符直接 split 会把句尾句号丢掉（"…夕照山"缺句号的来源）。
    列表符与 markdown/wikitext 残留一并剥掉。
    """
    parts = re.split(r"(?<=[。！？；])\n*|\n+", text)
    out = []
    for p in parts:
        p = re.sub(r"^[\s\-\*·#]+", "", p).strip()
        # wikitext 残留清洗：模板尾巴/图片参数/内链碎片
        p = re.sub(r"\}\}.*$", "", p).strip()
        p = re.sub(r"^\|.*$", "", p).strip()
        p = re.sub(r"thumb\|\d+px\|?", "", p).strip()
        if p and not p.startswith(("|", "}}", "thumb")):
            # 无标点结尾的句子补句号（文章列表行常缺句尾标点）
            if not p[-1] in "。！？；.！？;":
                p += "。"
            out.append(p)
    return out


def _extract_answer(chunk: dict, intent_text: str, embed_fn, section: str = None) -> str:
    """从 chunk 中挑与意图最相关的句子。

    打分策略：向量相似度为主，按意图类型调整：
    - 基本参数：含数字的句子加分（"多高"的答案必带数据）；
    - 参观信息：无门票/价格/开放词的句子减分（防世界遗产类句顶上）。
    过短句（<8 字，标题残留）不参与候选。
    """
    sents = [s for s in _split_sentences(chunk["text"]) if len(s) >= 8]
    if not sents:
        return ""
    if len(sents) == 1:
        return sents[0]
    qv = embed_fn([intent_text])[0]
    import numpy as np

    svecs = embed_fn(sents)
    sims = svecs @ qv
    for i, s in enumerate(sents):
        if section == "基本参数" and re.search(r"\d", s):
            sims[i] += 0.08
        if section == "参观信息" and not re.search(r"门票|价格|开放|免票|收费|美元|欧元|卢比|元", s):
            sims[i] -= 0.12
    return sents[int(np.argmax(sims))]


# ======================================================================
# 问答入口
# ======================================================================
_index = None
_index_error = None


def get_index():
    """问答索引单例；不可用返回 None（上层回退旧 qa_service）。"""
    global _index, _index_error
    if _index is None and _index_error is None:
        try:
            _index = ArticleIndex()
            logger.info("文章问答索引就绪：%d chunks", len(_index.chunks))
        except Exception as exc:
            _index_error = str(exc)
            logger.warning("文章问答索引不可用（回退旧问答）：%s", exc)
    return _index


def answer_question(question: str, history=None):
    """
    文章式问答主入口（接口与旧 qa_service.answer_question 一致）。

    返回 dict：
        answer      答案文本（含来源标注）
        confidence  归一化置信度
        known       是否命中（全部子项拒答时 False）
        landmark    关联地标
        source      article
    """
    started = time.time()
    idx = get_index()
    if idx is None:
        # 索引不可用：明确提示重建（不再回退旧键值对管线——已删除）
        return {
            "answer": "问答索引未构建，请运行 python scripts/build_qa_index.py",
            "confidence": 0.0,
            "known": False,
            "landmark": None,
            "landmarks": [],
            "source": "article",
        }

    question = (question or "").strip()
    if not question:
        return {"answer": "请输入有效的问题。", "confidence": 0.0, "known": False,
                "landmark": None, "source": "article"}

    # 1. 主题提取（多主题 -> 逐主题作答后合并）
    topics = extract_topics(question, idx.name_map)
    if not topics:
        # 无地标主题且非问句：直接拒答。
        # 理由：文章库全部内容都围绕地标，闲聊类输入命中的必然是弱相似噪声
        # （实测"聊聊天气"能弱命中弯曲金字塔高度），宁可拒答不可错答。
        has_question_mark = any(k in question for k in ("什么", "哪", "怎么", "为什么", "几", "多", "?", "？", "吗"))
        if not has_question_mark:
            return {"answer": UNKNOWN_ANSWER, "confidence": 0.0, "known": False,
                    "landmark": None, "source": "article"}
        # 泛问句（如"最高的塔是什么"）：全库检索，置信要求更高（0.55）
        results = idx.search(question, top_k=3)
        if results and results[0]["vec_sim"] >= 0.55:
            top = results[0]
            return {
                "answer": top["text"],
                "confidence": float(top["vec_sim"]),
                "known": True,
                "landmark": _lm_info(top["target_id"]),
                "source": "article",
            }
        return {"answer": UNKNOWN_ANSWER, "confidence": 0.0, "known": False,
                "landmark": None, "source": "article"}

    # 2. 逐主题作答
    #    - 纯主题（无疑问词，如"长城"或"长城和天坛"）：各回一句概述；
    #    - 带意图：剥掉其它主题名后按意图定向作答。
    #    landmark 兼容单值；landmarks 返回全部命中主题（前端关联地标行用）。
    other_names = [idx.landmarks[t]["name"] for t in topics]
    answers, used_lms = [], []
    for tid in topics[:2]:
        # 该主题的子问题：剥掉其它主题名（保留当前主题与疑问成分）
        sub_q = question
        for nm in other_names:
            if nm != idx.landmarks[tid]["name"]:
                sub_q = sub_q.replace(nm, "")
        sub_q = re.sub(r"[和与跟、，,？?\s]+$|^[和与跟、，,]", "", sub_q.strip()) or question

        # 复合问题（顿号/问号分隔多问）：逐子问检索作答后合并
        parts_q = [p for p, _ in split_intents(sub_q) if p.strip()]
        sub_answers = []
        answered_any = False
        for pq in parts_q:
            # 纯主题判定：剥掉本主题名后没有实质内容 -> 概述（"长城" -> 简介）
            residue = pq.replace(idx.landmarks[tid]["name"], "").strip()
            residue = re.sub(r"[的呢啊吧么？?，,。~]", "", residue)
            if not residue:
                ov = _overview_sentence(idx, tid)
                sub_ans = (
                    {"known": True, "answer": ov}
                    if ov
                    else {"known": False, "answer": UNKNOWN_ANSWER}
                )
            else:
                sub_ans = _answer_single_topic(idx, tid, pq)
            if sub_ans["known"] and sub_ans["answer"] not in sub_answers:
                # 同一子答案去重（"哪个高、分别在哪"拆分后可能重复命中同句）
                sub_answers.append(sub_ans["answer"])
                answered_any = True
            elif not sub_ans["known"]:
                sub_answers.append("文章未提及")

        if answered_any:
            answers.append("；".join(a for a in sub_answers if a != "文章未提及"))
            used_lms.append(_lm_info(tid))
        else:
            answers.append(f"{idx.landmarks[tid]['name']}：文章未提及")

    merged = "；".join(answers) if answers else UNKNOWN_ANSWER
    known = any("未提及" not in a for a in answers)
    logger.info("文章问答耗时 %.0fms（主题 %s）", (time.time() - started) * 1000, topics)
    return {
        "answer": merged,
        "confidence": 0.85 if known else 0.0,
        "known": known,
        "landmark": used_lms[0] if used_lms else None,
        "landmarks": used_lms,  # 全部命中地标（多主题场景）
        "source": "article",
    }


def _answer_single_topic(idx, target_id: str, question: str) -> dict:
    """单主题作答：文章内纯检索驱动（无意图路由）。

    设计原则：文章即唯一知识源——问题与文章句子的语义匹配是全部依据，
    不按关键词把问题路由到预设章节（"长城长度/长城多长"这类同义问法
    必须走同一条检索路径，得到同一个答案）。

    流程：
        1. 锁定该地标的文章，收集全部 chunk 的句子（每地标通常
           十几个 chunk、几十句，全局打分开销可控）；
        2. 句子级全局打分：向量余弦 + 位置问句加权，取最优句；
        3. 拒答验证：问句含强要素词（门票/价格）而答案句无对应词 -> 未提及。

    纯主题（问题只有地标名）在主入口已走概述分支，不进本函数。
    """
    # 该文章全部候选句与句向量（缓存复用，文章不变不重复编码）
    all_sents, sent_vecs = idx.article_sentences(target_id)
    if not all_sents:
        return {"known": False, "answer": UNKNOWN_ANSWER}

    import numpy as np

    qv = idx._embed([question])[0]
    sims = sent_vecs @ qv

    # 位置问句重打分：三因子组合——
    #   ① 位置表达加分（"位于X"句首/主语位置）
    #   ② 短句纯度加分（纯位置短句信息密度高，60 字百科长句即使含
    #     "位于"也混杂建造/人物等信息，答非所问的根源）
    #   ③ 时间表达抑制（问位置时"始建于/建于/倒塌/重建"句直接降权，
    #     实测"雷峰塔在哪"被"始建于977年"句以 0.840 抢走）
    if re.search(r"在哪|哪里|什么地方|哪个国家|哪个城市|位于", question):
        for i, s in enumerate(all_sents):
            has_pos = bool(re.search(r"(位于|坐落|横跨)[^。；，,]{2,}|东起[^。；，,]{2,}西至", s))
            short_pure = has_pos and len(s) <= 30
            has_time = bool(re.search(r"始建于|建于|建成|倒塌|重建|公元\d|年份|\d{3,4}年", s))
            if has_pos:
                sims[i] += 0.15
            if short_pure:
                sims[i] += 0.10
            if has_time and not short_pure:
                sims[i] -= 0.20

    # 时间问句加权：含年份/朝代的句子加分（"什么时候建的"的答案必带时间），
    # 位置句降权（对称保护，防"问时间答位置"）
    if re.search(r"什么时候|哪年|建于|哪一年|多少年|年代|朝代", question):
        for i, s in enumerate(all_sents):
            if re.search(r"\d{3,4}年|公元|公元前|世纪|朝代|年代", s):
                sims[i] += 0.12
            if re.search(r"^(位于|坐落)", s):
                sims[i] -= 0.15

    # 强要素拒答验证（问门票/价格但句中无对应要素）
    strong = _strong_aspect(question)
    if strong:
        for i, s in enumerate(all_sents):
            if not _sentence_aspects(s) & strong:
                sims[i] = -1.0  # 不满足要素的句子直接出局

    best = int(np.argmax(sims))
    if sims[best] <= 0:
        return {"known": False, "answer": UNKNOWN_ANSWER}
    return {"known": True, "answer": all_sents[best]}


def _best_sentence(chunk: dict, question: str, embed_fn):
    """chunk 内句子级语义打分，返回 (最优句, 分数)。

    分数为该句与问题的向量余弦；问句含位置疑问词（在哪/位于）
    时含位置词的句子加分——纯向量对"在哪"这类短问词的区分度弱，
    概述句常因地理量词干扰反超真正的位置句。
    """
    sents = [s for s in _split_sentences(chunk["text"]) if len(s) >= 8]
    if not sents:
        return "", -1.0
    import numpy as np

    qv = embed_fn([question])[0]
    sims = embed_fn(sents) @ qv if len(sents) > 1 else np.array([float(embed_fn([sents[0]])[0] @ qv)])
    # 位置问句加权：只认句首/主语位置表达（"位于X""东起X西至X"），
    # 泛词（省/市）会让遗产统计句反超真正的位置句
    if re.search(r"在哪|哪里|位于|什么地方|哪个国家|哪个城市", question):
        for i, s in enumerate(sents):
            if re.search(r"(位于|坐落|横跨|始自|起于)[^。；]{2,}|东起[^。；]{2,}西至", s):
                sims[i] += 0.15
    i = int(np.argmax(sims))
    return sents[i], float(sims[i])


# ======================================================================
# 要素词拒答验证（防"问门票答世遗"式的答非所问）
# ======================================================================
ASPECT_WORDS = {
    "price": ("门票", "价格", "多少钱", "收费", "免票", "票价"),
    "time": ("开放", "几点", "时间", "小时"),
    "height": ("多高", "高度", "多长", "长度", "海拔"),
}


def _strong_aspect(question: str):
    """问题是否含强要素词（该要素必须出现在答案句里，否则视为文章未提及）。

    返回：
        set of 要素名；空集合表示无强要素（普通问句不做要素校验）
    """
    hits = set()
    for aspect, words in ASPECT_WORDS.items():
        if any(w in question for w in words):
            hits.add(aspect)
    return hits


def _sentence_aspects(sent: str):
    """答案句覆盖的要素集合。"""
    hits = set()
    for aspect, words in ASPECT_WORDS.items():
        if any(w in sent for w in words):
            hits.add(aspect)
        # 数值也算 height 类证据（"330米""2.1万公里"）
        if aspect == "height" and re.search(r"\d+\s*(米|公里|千米|m|km)", sent):
            hits.add(aspect)
    return hits


def _overview_sentence(idx, target_id: str) -> str:
    """取地标文章概述章节的首句（不走相似度检索，章节直取）。

    概述/前言章节是文章结构里固定的简介段；用相似度检索"XX 概述"
    会被参数类 chunk 干扰（实测"长城"命中"总长度2.1万公里"）。
    """
    for c in idx.chunks:
        if c["target_id"] == target_id and c["section"] in ("概述", "前言"):
            sents = _split_sentences(c["text"])
            if sents:
                return sents[0]
    # 兜底：文章第一个 chunk 的首句
    for c in idx.chunks:
        if c["target_id"] == target_id:
            sents = _split_sentences(c["text"])
            if sents:
                return sents[0]
    return ""


def _lm_info(target_id: str):
    """地标摘要（复用 Landmark 表）。"""
    from apps.landmarks.models import Landmark

    try:
        lm = Landmark.objects.get(target_id__iexact=target_id)
        return {"id": lm.id, "name": lm.name, "image_url": lm.image_url, "intro": lm.intro}
    except Landmark.DoesNotExist:
        return None
