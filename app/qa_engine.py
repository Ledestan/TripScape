import math
import re
import sqlite3
import sys
import traceback
from collections import Counter

sys.dont_write_bytecode = True

import faiss
import jieba
from sentence_transformers import SentenceTransformer


class BM25:
    """
    BM25 关键词检索算法

    计算查询与文档的相关性得分，主要用于弥补向量检索对专有名词不够敏感的问题。
    内部使用中文分词（jieba）进行词项统计，并采用经典的 BM25 公式计算得分。
    """

    def __init__(self, documents, k1=1.5, b=0.75):
        """
        初始化 BM25 模型

        参数：
            documents : list of str
                所有文档的文本列表
            k1 : float, optional
                控制词频饱和的调节参数（默认 1.5）
            b : float, optional
                控制文档长度归一化的调节参数（默认 0.75）
        """
        self.k1 = k1
        self.b = b
        self.doc_lengths = [len(doc) for doc in documents]
        self.avg_length = sum(self.doc_lengths) / len(documents)
        self.corpus_size = len(documents)

        # 对每个文档进行分词
        self.tokenized_docs = [list(jieba.cut(doc)) for doc in documents]

        # 计算每个词的 IDF（逆文档频率）值
        doc_count_per_token = Counter()
        for tokens in self.tokenized_docs:
            doc_count_per_token.update(set(tokens))

        self.idf = {}
        for token, doc_freq in doc_count_per_token.items():
            self.idf[token] = math.log(
                (self.corpus_size - doc_freq + 0.5) / (doc_freq + 0.5) + 1
            )

    def get_score(self, query, doc_idx):
        """
        计算查询与指定文档的 BM25 得分

        参数：
            query : str
                查询字符串
            doc_idx : int
                文档在文档列表中的索引

        返回：
            float
                该文档与查询的相关性得分
        """
        query_tokens = list(jieba.cut(query))
        doc_tokens = self.tokenized_docs[doc_idx]
        doc_len = self.doc_lengths[doc_idx]
        doc_freq = Counter(doc_tokens)

        score = 0.0
        for token in query_tokens:
            if token not in self.idf:
                continue
            tf = doc_freq.get(token, 0)
            numerator = tf * (self.k1 + 1)
            denominator = tf + self.k1 * (
                1 - self.b + self.b * (doc_len / self.avg_length)
            )
            score += self.idf[token] * (numerator / denominator)
        return score

    def search(self, query, top_k=3):
        """
        检索与查询最匹配的 top_k 个文档

        参数：
            query : str
                查询字符串
            top_k : int, optional
                返回的最大文档数（默认 3）

        返回：
            list of tuple (int, float)
                每个元素为 (文档索引, BM25得分)，按得分降序排列
        """
        scores = [(idx, self.get_score(query, idx)) for idx in range(self.corpus_size)]
        scores.sort(key=lambda x: x[1], reverse=True)
        return scores[:top_k]


def load_documents(db_path, enabled_only=True):
    """
    从 SQLite 数据库加载知识库数据

    参数：
        db_path : str
            数据库文件路径
        enabled_only : bool, optional
            是否只加载启用（enabled=1）的记录（默认 True）

    返回：
        list of dict
            文档列表，每个文档包含 id, question, keywords, answer, full_text 字段

    异常：
        ValueError: 数据库缺少必要表或列时抛出
    """
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # 检查表是否存在
    cursor.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='knowledge_base'"
    )
    if not cursor.fetchone():
        raise ValueError("数据库中没有 'knowledge_base' 表")

    # 获取表的所有列
    cursor.execute("PRAGMA table_info(knowledge_base)")
    all_columns = [col[1] for col in cursor.fetchall()]

    # 确保必要列存在
    required = ["id", "question", "keywords", "answer"]
    missing = [col for col in required if col not in all_columns]
    if missing:
        raise ValueError(f"缺少列：{missing}")

    # 构建查询语句
    select_columns = [
        col
        for col in all_columns
        if col in required or col in ["enabled", "created_at"]
    ]
    sql = f"SELECT {', '.join(select_columns)} FROM knowledge_base"
    if "enabled" in all_columns and enabled_only:
        sql += " WHERE enabled = 1"

    cursor.execute(sql)
    rows = cursor.fetchall()
    conn.close()

    # 构造文档列表
    documents = []
    for row in rows:
        row_dict = dict(zip(select_columns, row))
        doc = {
            "id": row_dict["id"],
            "question": row_dict.get("question") or "",
            "keywords": row_dict.get("keywords") or "",
            "answer": row_dict.get("answer") or "",
        }
        # 构建用于检索的全文，将问题、关键词、答案合并为一个文本
        full_text = (
            f"问题：{doc['question']}\n关键词：{doc['keywords']}\n答案：{doc['answer']}"
        )
        if doc["keywords"]:
            full_text += f"\n{doc['keywords']}"
        doc["full_text"] = full_text
        documents.append(doc)

    print(f"加载 {len(documents)} 条知识记录")
    return documents


def build_vector_index(documents, model_name):
    """
    构建 FAISS 向量索引

    将文档全文编码为向量，使用内积相似度（归一化后等价于余弦相似度）。

    参数：
        documents : list of dict
            文档列表，需包含 'full_text' 字段
        model_name : str
            SentenceTransformer 模型名称

    返回：
        tuple (faiss.Index, SentenceTransformer)
            FAISS 索引对象和编码器模型
    """
    print("加载向量模型...")
    encoder = SentenceTransformer(model_name)

    texts = [doc["full_text"] for doc in documents]
    embeddings = encoder.encode(texts, convert_to_numpy=True, batch_size=32)

    # 归一化，使得内积等价于余弦相似度
    faiss.normalize_L2(embeddings)
    index = faiss.IndexFlatIP(embeddings.shape[1])
    index.add(embeddings)

    print(f"向量索引构建完成，共 {index.ntotal} 条")
    return index, encoder


def min_max_normalize(scores):
    """
    Min-Max 归一化，将分数映射到 [0, 1] 区间

    参数：
        scores : dict
            键为索引，值为原始分数

    返回：
        dict
            归一化后的分数，若输入为空则返回空字典
    """
    if not scores:
        return {}
    min_v, max_v = min(scores.values()), max(scores.values())
    if max_v == min_v:
        return {k: 1.0 for k in scores}
    return {k: (v - min_v) / (max_v - min_v) for k, v in scores.items()}


def hybrid_search(
    query, documents, vector_index, encoder, bm25_model, top_k, vector_weight
):
    """
    混合检索：向量检索 + BM25 关键词检索

    向量检索捕获语义相似性，BM25 强化精确关键词匹配，
    两者加权融合后按分数排序返回 Top-K 结果。

    参数：
        query : str
            查询字符串
        documents : list of dict
            文档列表
        vector_index : faiss.Index
            FAISS 向量索引
        encoder : SentenceTransformer
            编码器模型
        bm25_model : BM25
            BM25 检索模型
        top_k : int
            返回的最大结果数
        vector_weight : float
            向量检索的权重，BM25 权重为 1 - vector_weight

    返回：
        list of dict
            检索结果列表，每个元素包含 document, score, detail 字段
    """
    # 向量检索
    query_vec = encoder.encode([query], convert_to_numpy=True)
    faiss.normalize_L2(query_vec)
    vec_scores, vec_indices = vector_index.search(query_vec, top_k * 2)
    vec_scores = vec_scores[0]
    vec_indices = vec_indices[0]

    # BM25 检索
    bm25_candidates = bm25_model.search(query, top_k * 2)

    # 收集所有候选索引
    vec_dict = {idx: float(score) for idx, score in zip(vec_indices, vec_scores)}
    bm25_dict = {idx: score for idx, score in bm25_candidates if score > 0}
    all_indices = set(vec_dict.keys()) | set(bm25_dict.keys())
    if not all_indices:
        return []

    # 分别归一化
    norm_vec = min_max_normalize(vec_dict)
    norm_bm25 = min_max_normalize(bm25_dict)

    # 加权融合
    final_scores = {}
    for idx in all_indices:
        final_scores[idx] = vector_weight * norm_vec.get(idx, 0.0) + (
            1 - vector_weight
        ) * norm_bm25.get(idx, 0.0)

    # 排序取 Top-K
    sorted_items = sorted(final_scores.items(), key=lambda x: x[1], reverse=True)[
        :top_k
    ]

    results = []
    for idx, score in sorted_items:
        results.append(
            {
                "document": documents[idx],
                "score": score,
                "detail": {
                    "vec_score": norm_vec.get(idx, 0.0),
                    "bm25_score": norm_bm25.get(idx, 0.0),
                },
            }
        )
    return results


def format_answer(query, retrieved_results, threshold=0.2):
    """
    将检索结果格式化为用户友好的答案文本

    参数：
        query : str
            用户原始问题
        retrieved_results : list of dict
            检索结果列表
        threshold : float, optional
            最低置信度阈值，低于此值视为无匹配（默认 0.2）

    返回：
        str
            格式化的答案文本
    """
    # 检查是否有有效结果
    if not retrieved_results or retrieved_results[0]["score"] < threshold:
        return (
            "抱歉，本地知识库中暂时没有找到与您问题匹配的信息。请尝试更具体的关键词。"
        )

    # 纯地名查询（不含疑问词）优先展示"介绍"类记录
    question_words = [
        "多少",
        "哪里",
        "什么",
        "怎么",
        "如何",
        "哪",
        "几",
        "多",
        "吗",
        "呢",
        "吧",
    ]
    if not any(w in query for w in question_words):
        for res in retrieved_results:
            if "介绍" in res["document"].get("question", ""):
                retrieved_results.remove(res)
                retrieved_results.insert(0, res)
                break

    # 提取最佳结果
    best = retrieved_results[0]
    doc = best["document"]

    answer_text = doc.get("answer", "（暂无详细答案）")
    question_text = doc.get("question", "（无对应问题）")
    keywords_text = doc.get("keywords", "（无关键词）")

    # 构建输出
    result = f"{answer_text}\n"
    result += f"匹配问题：{question_text}\n"
    result += f"关键词：{keywords_text}"
    result += f"\n[置信度: {best['score']:.2%}]"

    return result


class AIGuideRAG:
    """
    本地 RAG 检索问答系统

    支持单问题（直接检索）和复合问题（自动拆分、补全景点名、合并答案）。
    采用向量+BM25混合检索策略，兼顾语义理解和关键词精确匹配。

    使用示例：
        guide = AIGuideRAG()
        answer = guide.ask("阿布辛贝神庙在哪里？")
    """

    def __init__(
        self,
        db_path="data/landmark.db",
        embedding_model="./models/bge-small-zh",
        enabled_only=True,
        top_k=3,
        vector_weight=0.6,
        score_threshold=0.2,
    ):
        """
        初始化 RAG 问答系统

        参数：
            db_path : str
                数据库文件路径
            embedding_model : str
                向量化模型名称
            enabled_only : bool
                是否只使用启用（enabled=1）的知识条目
            top_k : int
                检索返回的最大结果数
            vector_weight : float
                向量检索权重（0~1），BM25 权重自动为 1 - vector_weight
            score_threshold : float
                最低置信度阈值
        """
        self.top_k = top_k
        self.vector_weight = vector_weight
        self.score_threshold = score_threshold

        print("AI 导游初始化中...")
        self.documents = load_documents(db_path, enabled_only)
        if not self.documents:
            raise ValueError("没有加载到任何有效数据")

        full_texts = [doc["full_text"] for doc in self.documents]
        self.bm25 = BM25(full_texts)
        self.vector_index, self.encoder = build_vector_index(
            self.documents, embedding_model
        )
        print("初始化完成")

    def _single_ask(self, query):
        """
        处理单问题检索

        参数：
            query : str
                用户问题

        返回：
            str
                格式化后的答案
        """
        results = hybrid_search(
            query=query,
            documents=self.documents,
            vector_index=self.vector_index,
            encoder=self.encoder,
            bm25_model=self.bm25,
            top_k=self.top_k,
            vector_weight=self.vector_weight,
        )
        return format_answer(query, results, self.score_threshold)

    def _split_questions(self, query):
        """
        将复合问题拆分为独立子句

        按中文句号、问号、感叹号、分号切分，并识别完整问题片段。
        非疑问片段会合并到前一个片段。

        参数：
            query : str
                用户原始问题

        返回：
            list of str
                拆分后的子问题列表
        """
        # 按标点符号切分
        parts = re.split(r"([。？?！!；;])", query)
        sentences = []
        buffer = ""
        for part in parts:
            if part in "。？?！!；;":
                buffer += part
                if buffer.strip():
                    sentences.append(buffer.strip())
                buffer = ""
            else:
                buffer += part
        if buffer.strip():
            sentences.append(buffer.strip())

        # 判断是否为完整问题
        question_markers = [
            "吗",
            "呢",
            "怎么",
            "如何",
            "什么",
            "哪",
            "几",
            "多",
            "多少",
            "哪里",
            "何时",
            "为啥",
            "为什么",
            "是否",
            "有",
            "干啥",
            "干嘛",
            "啥",
        ]
        noun_questions = [
            "用途",
            "门票",
            "地址",
            "历史",
            "简介",
            "开放时间",
            "交通",
            "怎么去",
        ]

        valid = []
        for s in sentences:
            if len(s) < 2:
                continue
            is_question = (
                any(m in s for m in question_markers)
                or len(s) <= 6
                or any(n in s for n in noun_questions)
                or s.endswith(("？", "?"))
            )
            if is_question:
                valid.append(s)
            else:
                if valid:
                    valid[-1] += s
                else:
                    valid.append(s)
        return valid

    def _extract_scenic_name(self, question):
        """
        从问题开头提取景点名称

        通过匹配景点名与常见分隔词（位于、是、介绍等）来定位。
        如果无法匹配，则取第一个连续的汉字或英文字符串。

        参数：
            question : str
                问题字符串

        返回：
            str or None
                提取到的景点名，若不存在则返回 None
        """
        separators = (
            "位于|在|是|介绍|门票|高度|长度|面积|历史|用途|做什么|干什么"
            "|怎么|如何|多长|多高|多少|什么时候|建于|为什么|什么"
            "|在哪|在哪里|有哪些|是谁"
        )
        match = re.match(rf"^([^，,。.、？?！!；;]+?)(?:{separators})", question)
        if match:
            return match.group(1).strip()
        match = re.match(r"^([\u4e00-\u9fa5a-zA-Z]+)", question)
        if match:
            return match.group(1).strip()
        return None

    def _complete_sub_question(self, sub_q, scenic_name):
        """
        为缺少景点名的子问题补全景点名

        例如："用途" -> "天坛用途"

        参数：
            sub_q : str
                子问题
            scenic_name : str
                景点名称

        返回：
            str
                补全后的子问题
        """
        if not scenic_name or scenic_name in sub_q:
            return sub_q
        if sub_q.startswith("的"):
            return f"{scenic_name}{sub_q}"
        return f"{scenic_name}{sub_q}"

    def _merge_answers(self, sub_questions, raw_answers, scenic_name):
        """
        将多个答案合并成连贯的自然语言

        去除重复景点名前缀，根据答案类型选择合适的连接词，
        并统一标点符号。

        参数：
            sub_questions : list of str
                子问题列表
            raw_answers : list of str
                对应的答案列表
            scenic_name : str
                景点名称

        返回：
            str
                合并后的自然语言回答
        """
        if not raw_answers:
            return ""

        if len(raw_answers) == 1:
            ans = raw_answers[0]
            return ans if ans.endswith(("。", "！", "？")) else ans + "。"

        # 去除后续答案中的景点名前缀
        if scenic_name:
            for i in range(1, len(raw_answers)):
                ans = raw_answers[i]
                if ans.startswith(scenic_name):
                    raw_answers[i] = ans[len(scenic_name) :].lstrip("，,、的")
                else:
                    for pat in (
                        rf"^{scenic_name}是",
                        rf"^{scenic_name}位于",
                        rf"^{scenic_name}在",
                        rf"^{scenic_name}的",
                    ):
                        m = re.match(pat, ans)
                        if m:
                            raw_answers[i] = ans[m.end() :].lstrip("，,、")
                            break

        # 去除第一个答案末尾的标点
        raw_answers[0] = re.sub(r"[。！？！!?]+$", "", raw_answers[0]).strip()

        # 根据答案数量选择连接方式
        if len(raw_answers) == 2:
            if ("位于" in raw_answers[0] or "在" in raw_answers[0]) and (
                "用途" in sub_questions[1]
                or "做什么" in sub_questions[1]
                or "干啥" in sub_questions[1]
            ):
                merged = f"{raw_answers[0]}，主要用于{raw_answers[1]}"
            else:
                merged = f"{raw_answers[0]}，{raw_answers[1]}"
        else:
            merged = "；".join(raw_answers[:-1]) + f"；以及{raw_answers[-1]}"

        # 加上景点名前缀（如果尚未出现且不是以判断词开头）
        if scenic_name and not merged.startswith(scenic_name):
            if not re.match(r"^(位于|在|是|有|由)", merged):
                merged = f"{scenic_name}{merged}"

        # 清理标点符号，避免重复
        merged = re.sub(r"[。！？]+\s*，", "，", merged)
        merged = re.sub(r"，+", "，", merged)
        merged = re.sub(r"。+", "。", merged)
        if not merged.endswith(("。", "！", "？")):
            merged += "。"

        return merged

    def _ask_multiple(self, query):
        """
        处理复合问题（包含多个子句）

        流程：拆分子问题 → 提取景点名 → 补全缺少景点名的子问题 → 逐个检索 → 合并答案

        参数：
            query : str
                用户原始问题

        返回：
            str
                合并后的答案
        """
        sub_questions = self._split_questions(query)
        if len(sub_questions) <= 1:
            return self._single_ask(query)

        scenic_name = self._extract_scenic_name(sub_questions[0])
        formatted_answers = []  # 存储每个子问题的完整格式化结果

        for idx, sub_q in enumerate(sub_questions):
            if idx > 0 and scenic_name:
                enhanced_q = self._complete_sub_question(sub_q, scenic_name)
            else:
                enhanced_q = sub_q

            # 调用单问题检索，获取完整格式化回答
            ans = self._single_ask(enhanced_q)
            formatted_answers.append(ans)

        # 如果只有一个有效答案，直接返回（避免多余分隔）
        if len(formatted_answers) == 1:
            return formatted_answers[0]

        # 合并多个完整答案
        merged = "\n\n".join(formatted_answers)  # HTML 水平分隔线
        return merged

    def ask(self, query):
        """
        对外接口：接受用户问题，返回答案

        自动判断是单问题还是复合问题，并调用相应处理逻辑。

        参数：
            query : str
                用户问题

        返回：
            str
                答案文本
        """
        if not query.strip():
            return "请输入有效的问题。"
        sub_qs = self._split_questions(query)
        if len(sub_qs) > 1:
            return self._ask_multiple(query)
        return self._single_ask(query)


class QASystem:
    """
    问答系统主接口（仅使用 RAG 检索）
    """

    def __init__(self, use_rag=True):
        """
        初始化问答系统

        参数：
            use_rag : bool, optional
                是否启用 RAG 检索（默认 True），若为 False 则直接报错
        """
        self.use_rag = use_rag
        self.rag_engine = None

        if not use_rag:
            raise ValueError("本系统仅支持 RAG 检索模式，请设置 use_rag=True")

        try:
            self.rag_engine = AIGuideRAG(
                db_path="data/landmark.db",
                enabled_only=True,
                top_k=3,
                vector_weight=0.6,
                score_threshold=0.2,
            )
            print("RAG 检索引擎加载成功")
        except Exception as e:
            print(f"RAG 引擎加载失败: {e}")
            self.rag_engine = None

    def get_answer(self, question):
        """
        主入口：获取问题答案

        仅使用 RAG 检索，若 RAG 未启用或检索失败则返回错误信息。

        参数：
            question : str
                用户问题

        返回：
            dict
                包含 answer 和 source 字段
                - answer: 答案文本
                - source: 答案来源（固定为 "rag"）
        """
        if self.rag_engine is None:
            return {"answer": "RAG 引擎未初始化，请检查配置或日志。", "source": "rag"}

        try:
            answer = self.rag_engine.ask(question)
            # 检查是否返回了兜底回复（未找到匹配）
            if "本地知识库中暂时没有找到" not in answer:
                return {"answer": answer, "source": "rag"}
            else:
                # 兜底信息也直接返回，但来源仍为 rag
                return {"answer": answer, "source": "rag"}
        except Exception as e:
            print(f"RAG 检索失败: {e}")
            return {"answer": f"RAG 检索出错: {e}", "source": "rag"}


if __name__ == "__main__":
    """
    用法: python app/qa_engine.py <问题>
    """
    if len(sys.argv) < 2:
        print("用法: python app/qa_engine.py <问题>")
        sys.exit(1)

    query = " ".join(sys.argv[1:])
    try:
        qa = QASystem(use_rag=True)
        result = qa.get_answer(query)
        print(result["answer"])
    except Exception as e:
        print(f"错误: {e}")
        traceback.print_exc()
