"""行旅识景 TripScape / 问答索引构建脚本
创建日期：2025-10-08

解析地标文章目录并构建双路检索索引，完成:
    1. 解析 scripts/db/articles/*.md（YAML 元数据 + 章节结构）
    2. 按 ## 章节切分文本块（每块元数据：地标/标题/章节/Chunk ID）
    3. bge-small-zh 向量编码 -> 向量矩阵
    4. 写出分块 JSON + 向量 npy + 指纹清单（幂等，文章变化自动失效）

依赖:
    Python: >=3.10
    需求文件: requirements.txt
    依赖库:
        sentence-transformers    # bge-small-zh 向量
    模型:
        models/bge-small-zh/     # 项目内已有

用法（在项目根目录执行）:
    python scripts/build_qa_index.py                 # 文章指纹未变则跳过
    python scripts/build_qa_index.py --force-rebuild # 强制重建

可选参数:
    --articles <目录>   文章目录，默认 scripts/db/articles
    --chunk-size N      单块最大字符数，默认 500
    --force-rebuild     忽略指纹强制重建

输出:
    runtime/index/qa_chunks.json     分块与元数据
    runtime/index/qa_vectors.npy     向量矩阵（与分块行号对齐）
    runtime/index/qa_manifest.json   建库指纹（文章内容哈希）

注意:
    1. 文章增改后重跑本脚本（指纹变化自动重建，无需删除旧产物）。
    2. 分块策略：按章节边界切块，超长章节内再按句号细分，不跨章节。
"""

import argparse
import hashlib
import json
import re
import sys
import time
from pathlib import Path

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "backend"))

import os

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

import django

django.setup()


# ======================================================================
# 文章解析与分块
# ======================================================================
class ArticleChunker:
    """markdown 文章解析与章节分块。

    只认两级结构：YAML 头（--- 包裹）与 ## 章节标题；
    超长章节按句号边界二次切分，保证单块不超过 chunk_size。
    """

    def __init__(self, chunk_size: int = 500):
        self.chunk_size = chunk_size

    # ------------------------------------------------------------------
    def parse(self, md_path: Path) -> dict:
        """
        返回：
            {"meta": {...}, "sections": [(章节名, [行文本]), ...]}
        """
        text = md_path.read_text(encoding="utf-8")
        # YAML 头
        meta = {}
        m = re.match(r"^---\n(.*?)\n---\n", text, re.S)
        if m:
            for line in m.group(1).splitlines():
                if ":" in line:
                    k, v = line.split(":", 1)
                    meta[k.strip()] = v.strip()
            text = text[m.end():]

        # 章节切分（## 标题）
        sections = []
        cur_title, cur_lines = "前言", []
        for line in text.splitlines():
            if line.startswith("## "):
                if cur_lines:
                    sections.append((cur_title, cur_lines))
                cur_title, cur_lines = line[3:].strip(), []
            elif line.strip():
                cur_lines.append(line.strip())
        if cur_lines:
            sections.append((cur_title, cur_lines))
        return {"meta": meta, "sections": sections}

    # ------------------------------------------------------------------
    def chunk(self, md_path: Path) -> list:
        """
        返回：
            list of {"target_id", "name", "section", "text", "chunk_id"}
        """
        parsed = self.parse(md_path)
        meta = parsed["meta"]
        chunks = []
        cid = 0
        for sec_title, lines in parsed["sections"]:
            body = "\n".join(lines)
            # 超长章节按句号细分，不跨章节
            if len(body) > self.chunk_size:
                sents = re.split(r"(?<=[。！？])", body)
                buf = ""
                for s in sents:
                    if len(buf) + len(s) > self.chunk_size and buf:
                        c = self._mk(meta, sec_title, buf, cid)
                        if c:
                            chunks.append(c)
                        cid += 1
                        buf = s
                    else:
                        buf += s
                if buf.strip():
                    c = self._mk(meta, sec_title, buf, cid)
                    if c:
                        chunks.append(c)
                    cid += 1
            else:
                c = self._mk(meta, sec_title, body, cid)
                if c:
                    chunks.append(c)
                cid += 1
        return chunks

    def _mk(self, meta, section, text, cid):
        """
        返回：
            dict 或 None（短行全被过滤后正文为空时返回 None，该块不进索引——
            空块占坑会干扰章节定向检索）。
        """
        # 列表符（- / * / ·）与 markdown 标题（#）剥掉；过短行（<8 字，
        # 如标题残留/单词行）直接丢弃——它们进索引只会产生"长城"式垃圾答案
        lines = []
        for ln in text.splitlines():
            ln = re.sub(r"^[\s\-\*·]+", "", ln).strip()
            ln = re.sub(r"^#+\s*", "", ln).strip()
            if len(ln) >= 8:
                lines.append(ln)
        body = "\n".join(lines)
        if not body.strip():
            return None
        return {
            "target_id": meta.get("target_id", ""),
            "name": meta.get("name", ""),
            "region": meta.get("region", ""),
            "section": section,
            "text": body,
            "chunk_id": f"{meta.get('target_id', 'x')}#{cid}",
        }


# ======================================================================
# 索引构建
# ======================================================================
class QaIndexBuilder:
    """向量编码与索引产物写出（产物路径集中管理）。"""

    def __init__(self, out_dir: Path):
        self.paths = {
            "chunks": str(out_dir / "qa_chunks.json"),
            "vectors": str(out_dir / "qa_vectors.npy"),
            "manifest": str(out_dir / "qa_manifest.json"),
        }
        out_dir.mkdir(parents=True, exist_ok=True)

    # ------------------------------------------------------------------
    def fingerprint(self, article_dir: Path) -> str:
        """文章目录内容指纹（文件名 + 内容哈希）。"""
        h = hashlib.sha256()
        for f in sorted(article_dir.glob("*.md")):
            h.update(f.name.encode())
            h.update(f.read_bytes())
        return h.hexdigest()[:16]

    # ------------------------------------------------------------------
    def load_or_build(self, article_dir: Path, chunker: ArticleChunker, force_rebuild: bool):
        import numpy as np

        fp = self.fingerprint(article_dir)
        if not force_rebuild and Path(self.paths["manifest"]).exists():
            old = json.loads(Path(self.paths["manifest"]).read_text(encoding="utf-8"))
            if old.get("fingerprint") == fp:
                print(f"文章指纹未变（{fp}），索引可复用；--force-rebuild 可强制重建")
                return
            print("文章已变化，开始重建问答索引 ...")

        print("\n========== 解析文章并分块 ==========")
        all_chunks = []
        for f in sorted(article_dir.glob("*.md")):
            all_chunks += chunker.chunk(f)
        if not all_chunks:
            raise RuntimeError(f"{article_dir} 下没有可解析的文章")
        print(f"共 {len(all_chunks)} 个分块（来自 {len(list(article_dir.glob('*.md')))} 篇文章）")

        print("\n========== 向量编码（bge-small-zh） ==========")
        t_start = time.time()
        from django.conf import settings as dj_settings
        from sentence_transformers import SentenceTransformer

        model = SentenceTransformer(str(dj_settings.EMBEDDING_MODEL_DIR))
        vectors = model.encode(
            [c["text"] for c in all_chunks], normalize_embeddings=True, show_progress_bar=False
        )
        vectors = np.asarray(vectors, dtype="float32")

        Path(self.paths["chunks"]).write_text(
            json.dumps(all_chunks, ensure_ascii=False, indent=1), encoding="utf-8"
        )
        np.save(self.paths["vectors"], vectors)
        Path(self.paths["manifest"]).write_text(
            json.dumps({"fingerprint": fp, "count": len(all_chunks)}, ensure_ascii=False),
            encoding="utf-8",
        )
        print(f"向量维度 {vectors.shape}，已保存至 runtime/index/")
        print(f"[耗时] 向量编码: {time.time() - t_start:.2f} 秒")


# ======================================================================
# 命令行入口
# ======================================================================
def _parse_args(argv=None):
    parser = argparse.ArgumentParser(
        prog="python scripts/build_qa_index.py",
        description="地标文章问答索引构建（幂等，文章变化自动重建）。",
        epilog="示例：\n  python scripts/build_qa_index.py\n  python scripts/build_qa_index.py --force-rebuild\n",
    )
    parser.add_argument("--articles", default=str(ROOT / "scripts" / "db" / "articles"), help="文章目录")
    parser.add_argument("--chunk-size", type=int, default=500, help="单块最大字符数，默认 500")
    parser.add_argument("--force-rebuild", action="store_true", help="强制重建")
    return parser.parse_args(argv)


def main(argv=None):
    overall_start = time.time()
    args = _parse_args(argv)

    article_dir = Path(args.articles)
    if not article_dir.exists():
        raise SystemExit(f"错误: 文章目录不存在 {article_dir}，请先运行 scripts/build_articles.py")

    chunker = ArticleChunker(chunk_size=args.chunk_size)
    builder = QaIndexBuilder(ROOT / "runtime" / "index")
    builder.load_or_build(article_dir, chunker, args.force_rebuild)

    print("\n" + "=" * 50)
    print(f"所有步骤完成，总运行时间: {time.time() - overall_start:.2f} 秒")


if __name__ == "__main__":
    main()
