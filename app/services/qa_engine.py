"""
模块名称：本地 RAG 检索问答服务

本模块由以下组件组成：
- BM25                  关键词检索算法，弥补向量检索对专有名词不敏感的问题
- KnowledgeBaseLoader   从 SQLite 加载知识库文档
- VectorIndexBuilder    构建 FAISS 向量索引
- HybridSearcher        向量检索 + BM25 混合检索
- AnswerFormatter       将检索结果格式化为用户可读的答案
- AIGuideRAG            完整 RAG 流程（单问题 / 复合问题）
- QASystem              对外问答主接口

命令行用法（在项目根目录执行）：
    python -m app.services.qa_engine <问题> [选项]

位置参数：
    question            必填，要提问的问题

可选参数：
    --top-k N           检索返回的最大结果数，默认 3
    --vector-weight W   向量检索权重（0~1），BM25 权重为 1-W，默认 0.6
    --threshold T       最低置信度阈值，默认 0.2

示例：
    python -m app.services.qa_engine "阿布辛贝神庙在哪里？"
    python -m app.services.qa_engine "天坛用途和门票" --top-k 5
    python -m app.services.qa_engine "埃菲尔铁塔高多少" --vector-weight 0.7

注意：必须以模块方式运行（-m），否则 `app.core.*` 无法被导入。
"""

import argparse
import math
import re
import sqlite3
import sys
import traceback
from collections import Counter
from pathlib import Path

sys.dont_write_bytecode = True

import faiss
import jieba
from sentence_transformers import SentenceTransformer

from app.core.config import DB_PATH, EMBEDDING_MODEL_PATH


# ======================================================================
# BM25 关键词检索
# ======================================================================
class BM25:
    """
    BM25 关键词检索算法。

    计算查询与文档的相关性得分，主要用于弥补向量检索对专有名词不够敏感的问题。
    内部使用 jieba 进行中文分词，并采用经典 BM25 公式计算得分。
    """

    def __init__(self, documents, k1=1.5, b=0.75):
        """
        参数：
            documents : list of str
                所有文档的文本列表
            k1 : float
                控制词频饱和的调节参数，默认 1.5
            b : float
                控制文档长度归一化的调节参数，默认 0.75
        """
        self.k1 = k1
        self.b = b
        self.doc_lengths = [len(doc) for doc in documents]
        self.avg_length = sum(self.doc_lengths) / len(documents)
        self.corpus_size = len(documents)

        self.tokenized_docs = [list(jieba.cut(doc)) for doc in documents]

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
        计算查询与指定文档的 BM25 得分。

        参数：
            query : str
            doc_idx : int

        返回：
            float
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
        检索与查询最匹配的 top_k 个文档。

        返回：
            list of (int, float)，按 BM25 得分降序
        """
        scores = [(idx, self.get_score(query, idx)) for idx in range(self.corpus_size)]
        scores.sort(key=lambda x: x[1], reverse=True)
        return scores[:top_k]


# ======================================================================
# 知识库加载
# ======================================================================
class KnowledgeBaseLoader:
    """
    从 SQLite 数据库加载知识库文档。

    表名固定为 knowledge_base，必要列包括 id、question、keywords、answer。
    可选列 enabled、created_at 会被一并读取。
    """

    REQUIRED_COLUMNS = ["id", "question", "keywords", "answer"]
    OPTIONAL_COLUMNS = ["enabled", "created_at"]

    def __init__(self, db_path=DB_PATH):
        """
        参数：
            db_path : str 或 pathlib.Path
                数据库文件路径，默认 config.DB_PATH
        """
        self.db_path = str(db_path)

    def load(self, enabled_only=True):
        """
        加载知识库文档。

        参数：
            enabled_only : bool
                是否只加载 enabled=1 的记录，默认 True

        返回：
            list of dict，每个文档包含 id / question / keywords /
            answer / full_text 字段

        异常：
            ValueError: 数据库缺少必要表或列
        """
        conn = sqlite3.connect(self.db_path)
        try:
            cursor = conn.cursor()

            cursor.execute(
                "SELECT name FROM sqlite_master "
                "WHERE type='table' AND name='knowledge_base'"
            )
            if not cursor.fetchone():
                raise ValueError("数据库中没有 'knowledge_base' 表")

            cursor.execute("PRAGMA table_info(knowledge_base)")
            all_columns = [col[1] for col in cursor.fetchall()]

            missing = [c for c in self.REQUIRED_COLUMNS if c not in all_columns]
            if missing:
                raise ValueError(f"缺少列：{missing}")

            select_columns = [
                c
                for c in all_columns
                if c in self.REQUIRED_COLUMNS or c in self.OPTIONAL_COLUMNS
            ]
            sql = f"SELECT {', '.join(select_columns)} FROM knowledge_base"
            if "enabled" in all_columns and enabled_only:
                sql += " WHERE enabled = 1"

            cursor.execute(sql)
            rows = cursor.fetchall()
        finally:
            conn.close()

        documents = []
        for row in rows:
            row_dict = dict(zip(select_columns, row))
            doc = {
                "id": row_dict["id"],
                "question": row_dict.get("question") or "",
                "keywords": row_dict.get("keywords") or "",
                "answer": row_dict.get("answer") or "",
            }
            full_text = (
                f"问题：{doc['question']}\n"
                f"关键词：{doc['keywords']}\n"
                f"答案：{doc['answer']}"
            )
            if doc["keywords"]:
                full_text += f"\n{doc['keywords']}"
            doc["full_text"] = full_text
            documents.append(doc)

        print(f"加载 {len(documents)} 条知识记录")
        return documents


# ======================================================================
# 向量索引构建
# ======================================================================
class VectorIndexBuilder:
    """
    构建 FAISS 向量索引。

    将文档全文编码为向量，归一化后使用内积相似度（等价于余弦相似度）。
    """

    def __init__(self, model_name=EMBEDDING_MODEL_PATH, batch_size=32):
        """
        参数：
            model_name : str 或 pathlib.Path
                SentenceTransformer 模型路径，默认 config.EMBEDDING_MODEL_PATH
            batch_size : int
                编码时的批大小，默认 32
        """
        self.model_name = str(model_name)
        self.batch_size = batch_size

    def build(self, documents):
        """
        构建索引。

        参数：
            documents : list of dict，需包含 'full_text' 字段

        返回：
            (faiss.Index, SentenceTransformer)
        """
        print("加载向量模型...")
        encoder = SentenceTransformer(self.model_name)

        texts = [doc["full_text"] for doc in documents]
        embeddings = encoder.encode(
            texts, convert_to_numpy=True, batch_size=self.batch_size
        )

        faiss.normalize_L2(embeddings)
        index = faiss.IndexFlatIP(embeddings.shape[1])
        index.add(embeddings)

        print(f"向量索引构建完成，共 {index.ntotal} 条")
        return index, encoder


# ======================================================================
# 混合检索
# ======================================================================
class HybridSearcher:
    """
    向量检索 + BM25 混合检索器。

    向量检索捕获语义相似性，BM25 强化精确关键词匹配；
    两者分别归一化后按权重融合，返回 Top-K。
    """

    def __init__(
        self,
        documents,
        vector_index,
        encoder,
        bm25_model,
        vector_weight=0.6,
    ):
        """
        参数：
            documents : list of dict
            vector_index : faiss.Index
            encoder : SentenceTransformer
            bm25_model : BM25
            vector_weight : float
                向量检索权重（0~1），BM25 权重为 1 - vector_weight
        """
        self.documents = documents
        self.vector_index = vector_index
        self.encoder = encoder
        self.bm25 = bm25_model
        self.vector_weight = vector_weight

    @staticmethod
    def _min_max_normalize(scores):
        """
        Min-Max 归一化，将分数映射到 [0, 1]。

        参数：
            scores : dict，键为索引，值为原始分数

        返回：
            dict，若输入为空则返回空字典
        """
        if not scores:
            return {}
        min_v, max_v = min(scores.values()), max(scores.values())
        if max_v == min_v:
            return {k: 1.0 for k in scores}
        return {k: (v - min_v) / (max_v - min_v) for k, v in scores.items()}

    def search(self, query, top_k=3):
        """
        执行混合检索。

        参数：
            query : str
            top_k : int

        返回：
            list of dict，每个元素含 document / score / detail 字段
        """
        query_vec = self.encoder.encode([query], convert_to_numpy=True)
        faiss.normalize_L2(query_vec)
        vec_scores, vec_indices = self.vector_index.search(query_vec, top_k * 2)
        vec_scores = vec_scores[0]
        vec_indices = vec_indices[0]

        bm25_candidates = self.bm25.search(query, top_k * 2)

        vec_dict = {int(i): float(s) for i, s in zip(vec_indices, vec_scores)}
        bm25_dict = {int(i): s for i, s in bm25_candidates if s > 0}
        all_indices = set(vec_dict.keys()) | set(bm25_dict.keys())
        if not all_indices:
            return []

        norm_vec = self._min_max_normalize(vec_dict)
        norm_bm25 = self._min_max_normalize(bm25_dict)

        final_scores = {}
        for idx in all_indices:
            final_scores[idx] = self.vector_weight * norm_vec.get(idx, 0.0) + (
                1 - self.vector_weight
            ) * norm_bm25.get(idx, 0.0)

        sorted_items = sorted(final_scores.items(), key=lambda x: x[1], reverse=True)[
            :top_k
        ]

        results = []
        for idx, score in sorted_items:
            results.append(
                {
                    "document": self.documents[idx],
                    "score": score,
                    "detail": {
                        "vec_score": norm_vec.get(idx, 0.0),
                        "bm25_score": norm_bm25.get(idx, 0.0),
                    },
                }
            )
        return results


# ======================================================================
# 答案格式化
# ======================================================================
class AnswerFormatter:
    """
    将检索结果格式化为用户友好的答案文本。
    """

    QUESTION_WORDS = [
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

    def __init__(self, threshold=0.2):
        """
        参数：
            threshold : float
                最低置信度阈值，低于此值视为无匹配，默认 0.2
        """
        self.threshold = threshold

    def format(self, query, retrieved_results):
        """
        参数：
            query : str
            retrieved_results : list of dict

        返回：
            str
        """
        if not retrieved_results or retrieved_results[0]["score"] < self.threshold:
            return (
                "抱歉，本地知识库中暂时没有找到与您问题匹配的信息。"
                "请尝试更具体的关键词。"
            )

        # 纯地名查询（不含疑问词）优先展示"介绍"类记录
        if not any(w in query for w in self.QUESTION_WORDS):
            for res in retrieved_results:
                if "介绍" in res["document"].get("question", ""):
                    retrieved_results.remove(res)
                    retrieved_results.insert(0, res)
                    break

        best = retrieved_results[0]
        doc = best["document"]

        answer_text = doc.get("answer", "（暂无详细答案）")
        question_text = doc.get("question", "（无对应问题）")
        keywords_text = doc.get("keywords", "（无关键词）")

        return (
            f"{answer_text}\n"
            f"匹配问题：{question_text}\n"
            f"关键词：{keywords_text}\n"
            f"[置信度: {best['score']:.2%}]"
        )


# ======================================================================
# RAG 问答引擎
# ======================================================================
class AIGuideRAG:
    """
    本地 RAG 检索问答系统。

    支持单问题（直接检索）和复合问题（自动拆分、补全景点名、合并答案）。
    采用向量 + BM25 混合检索策略，兼顾语义理解和关键词精确匹配。

    使用示例：
        guide = AIGuideRAG()
        answer = guide.ask("阿布辛贝神庙在哪里？")
    """

    def __init__(
        self,
        db_path=DB_PATH,
        embedding_model=EMBEDDING_MODEL_PATH,
        enabled_only=True,
        top_k=3,
        vector_weight=0.6,
        score_threshold=0.2,
    ):
        """
        参数：
            db_path : str 或 pathlib.Path
                数据库文件路径，默认 config.DB_PATH
            embedding_model : str 或 pathlib.Path
                向量化模型路径，默认 config.EMBEDDING_MODEL_PATH
            enabled_only : bool
                是否只使用 enabled=1 的知识条目
            top_k : int
                检索返回的最大结果数
            vector_weight : float
                向量检索权重（0~1）
            score_threshold : float
                最低置信度阈值
        """
        self.top_k = top_k
        self.vector_weight = vector_weight
        self.score_threshold = score_threshold

        print("AI 导游初始化中...")

        self.loader = KnowledgeBaseLoader(db_path)
        self.documents = self.loader.load(enabled_only)
        if not self.documents:
            raise ValueError("没有加载到任何有效数据")

        full_texts = [doc["full_text"] for doc in self.documents]
        self.bm25 = BM25(full_texts)

        self.index_builder = VectorIndexBuilder(embedding_model)
        self.vector_index, self.encoder = self.index_builder.build(self.documents)

        self.searcher = HybridSearcher(
            documents=self.documents,
            vector_index=self.vector_index,
            encoder=self.encoder,
            bm25_model=self.bm25,
            vector_weight=self.vector_weight,
        )
        self.formatter = AnswerFormatter(self.score_threshold)

        print("初始化完成")

    # ------------------------------------------------------------------
    # 单问题检索
    # ------------------------------------------------------------------
    def _single_ask(self, query):
        """处理单问题检索。"""
        results = self.searcher.search(query, top_k=self.top_k)
        return self.formatter.format(query, results)

    # ------------------------------------------------------------------
    # 复合问题处理
    # ------------------------------------------------------------------
    @staticmethod
    def _split_questions(query):
        """
        将复合问题拆分为独立子句。

        按中文标点切分，非疑问片段合并到前一个片段。

        返回：
            list of str
        """
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

    @staticmethod
    def _extract_scenic_name(question):
        """
        从问题开头提取景点名称。

        通过常见分隔词定位景点名，找不到时取开头连续的汉字或英文串。

        返回：
            str 或 None
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

    @staticmethod
    def _complete_sub_question(sub_q, scenic_name):
        """
        为缺少景点名的子问题补全景点名，例如 "用途" → "天坛用途"。
        """
        if not scenic_name or scenic_name in sub_q:
            return sub_q
        return f"{scenic_name}{sub_q}"

    @staticmethod
    def _merge_answers(sub_questions, raw_answers, scenic_name):
        """
        将多个答案合并成连贯的自然语言。

        去除重复景点名前缀，按答案类型选择连接词，统一标点。
        """
        if not raw_answers:
            return ""

        if len(raw_answers) == 1:
            ans = raw_answers[0]
            return ans if ans.endswith(("。", "！", "？")) else ans + "。"

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

        raw_answers[0] = re.sub(r"[。！？！!?]+$", "", raw_answers[0]).strip()

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

        if scenic_name and not merged.startswith(scenic_name):
            if not re.match(r"^(位于|在|是|有|由)", merged):
                merged = f"{scenic_name}{merged}"

        merged = re.sub(r"[。！？]+\s*，", "，", merged)
        merged = re.sub(r"，+", "，", merged)
        merged = re.sub(r"。+", "。", merged)
        if not merged.endswith(("。", "！", "？")):
            merged += "。"

        return merged

    def _ask_multiple(self, query):
        """处理复合问题。"""
        sub_questions = self._split_questions(query)
        if len(sub_questions) <= 1:
            return self._single_ask(query)

        scenic_name = self._extract_scenic_name(sub_questions[0])
        formatted_answers = []

        for idx, sub_q in enumerate(sub_questions):
            if idx > 0 and scenic_name:
                enhanced_q = self._complete_sub_question(sub_q, scenic_name)
            else:
                enhanced_q = sub_q
            formatted_answers.append(self._single_ask(enhanced_q))

        if len(formatted_answers) == 1:
            return formatted_answers[0]
        return "\n\n".join(formatted_answers)

    # ------------------------------------------------------------------
    # 对外接口
    # ------------------------------------------------------------------
    def ask(self, query):
        """
        对外接口：接受用户问题，返回答案。

        自动判断是单问题还是复合问题，并调用相应处理逻辑。

        参数：
            query : str

        返回：
            str
        """
        if not query.strip():
            return "请输入有效的问题。"
        sub_qs = self._split_questions(query)
        if len(sub_qs) > 1:
            return self._ask_multiple(query)
        return self._single_ask(query)


# ======================================================================
# 问答系统主接口
# ======================================================================
class QASystem:
    """
    问答系统主接口（仅使用 RAG 检索）。
    """

    def __init__(
        self,
        use_rag=True,
        db_path=DB_PATH,
        embedding_model=EMBEDDING_MODEL_PATH,
        top_k=3,
        vector_weight=0.6,
        score_threshold=0.2,
    ):
        """
        参数：
            use_rag : bool
                是否启用 RAG 检索（默认 True），若为 False 则直接报错
            db_path / embedding_model / top_k / vector_weight / score_threshold
                透传给 AIGuideRAG，默认走 config
        """
        self.use_rag = use_rag
        self.rag_engine = None

        if not use_rag:
            raise ValueError("本系统仅支持 RAG 检索模式，请设置 use_rag=True")

        try:
            self.rag_engine = AIGuideRAG(
                db_path=db_path,
                embedding_model=embedding_model,
                enabled_only=True,
                top_k=top_k,
                vector_weight=vector_weight,
                score_threshold=score_threshold,
            )
            print("RAG 检索引擎加载成功")
        except Exception as e:
            print(f"RAG 引擎加载失败: {e}")
            self.rag_engine = None

    def get_answer(self, question):
        """
        主入口：获取问题答案。

        参数：
            question : str

        返回：
            dict，包含 answer 和 source 字段
        """
        if self.rag_engine is None:
            return {
                "answer": "RAG 引擎未初始化，请检查配置或日志。",
                "source": "rag",
            }

        try:
            answer = self.rag_engine.ask(question)
            return {"answer": answer, "source": "rag"}
        except Exception as e:
            print(f"RAG 检索失败: {e}")
            return {"answer": f"RAG 检索出错: {e}", "source": "rag"}


# ======================================================================
# 命令行入口
# ======================================================================
def _parse_args(argv=None):
    parser = argparse.ArgumentParser(
        prog="python -m app.services.qa_engine",
        description="本地 RAG 问答命令行工具。",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "示例：\n"
            '  python -m app.services.qa_engine "阿布辛贝神庙在哪里？"\n'
            '  python -m app.services.qa_engine "天坛用途和门票" --top-k 5\n'
            '  python -m app.services.qa_engine "埃菲尔铁塔高多少" --vector-weight 0.7\n'
        ),
    )
    parser.add_argument("question", help="要提问的问题")
    parser.add_argument(
        "--top-k",
        type=int,
        default=3,
        help="检索返回的最大结果数，默认 3",
    )
    parser.add_argument(
        "--vector-weight",
        type=float,
        default=0.6,
        help="向量检索权重（0~1），BM25 权重为 1-W，默认 0.6",
    )
    parser.add_argument(
        "--threshold",
        type=float,
        default=0.2,
        help="最低置信度阈值，默认 0.2",
    )
    return parser.parse_args(argv)


def main(argv=None):
    args = _parse_args(argv)

    try:
        qa = QASystem(
            use_rag=True,
            top_k=args.top_k,
            vector_weight=args.vector_weight,
            score_threshold=args.threshold,
        )
        result = qa.get_answer(args.question)
        print(result["answer"])
    except Exception as e:
        print(f"错误: {e}")
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
