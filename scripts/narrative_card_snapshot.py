"""叙事卡片字段快照导出（S2 功能证据附表，SPEC §3.3）。

用途：把 **真实 HTTP 响应** 的字段结构固化为 `docs/competition/A2-card-schema.snapshot.json`，
使"卡片字段集"可被人复核，且能检测实现漂移（字段增删/类型变化/数组变空）。

用法:
    $env:DB_ENGINE='sqlite'
    .venv\\Scripts\\python.exe scripts\\narrative_card_snapshot.py [--landmark EiffelTower]

说明:
    1. 只调用已有端点（GET /api/narrative/card/{landmark_id}），不直接读模型，
       保证快照与对外契约同源。
    2. 示例文本取自仓库内真实数据（文章库/地标简介），脚本只做**截断**，
       不撰写、不改写任何文化内容（文化内容最终解释权归人）。
    3. 快照里不含运行时随机 id；仅保留结构与真实字段取值类型。
"""

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "backend"))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
os.environ.setdefault("DB_ENGINE", "sqlite")

import django  # noqa: E402

django.setup()

from django.test import Client  # noqa: E402
from django.test.utils import override_settings  # noqa: E402

OUT = ROOT / "docs" / "competition" / "A2-card-schema.snapshot.json"
TEXT_LIMIT = 60

# SPEC §2 S2 固定字段集（与 tests/backend/test_s2_card_contract.py 独立维护，互为校验）
CARD_FIELDS = [
    "id",
    "landmarkId",
    "photo",
    "title",
    "geo",
    "timeFragments",
    "ragSnippets",
    "confidence",
    "source",
]

FIELD_DOC = {
    "id": ("integer", "叙事卡片主键（ts_narrative_card.id）"),
    "landmarkId": ("integer", "地标主键（ts_landmark.id），与识别结果的 landmark_id 一致"),
    "photo": ("string", "原图 URL 引用（不复制文件；无上传图时为地标百科图）"),
    "title": ("string", "卡片标题：地标名｜国家（取自 ts_landmark）"),
    "geo": ("object", "地理绑定：lat/lon/place/country/region，全部取自 ts_landmark"),
    "timeFragments": ("array", "时间碎片（非空）：文章库历史沿革/概述的真实史料句"),
    "ragSnippets": ("array", "RAG 检索片段（非空）：ArticleIndex.search 的真实混合检索结果"),
    "confidence": ("number", "识别置信度，0 ≤ confidence ≤ 1"),
    "source": ("string", "卡片来源标签（识别引擎名 / landmark）"),
}

# SPEC 必需字段之外、实现额外返回的字段（不得混入 fieldOrder）
EXTENSION_DOC = {
    "createdAt": "ISO 时间戳（ts_narrative_card.created_at）；A2 矩阵 M10 时间刻度切面使用，不属 SPEC 必需字段",
}


def _trim(value):
    """深拷贝并截断长文本（只截断，不改写）。"""
    if isinstance(value, str):
        return value if len(value) <= TEXT_LIMIT else value[:TEXT_LIMIT] + "…"
    if isinstance(value, list):
        return [_trim(v) for v in value]
    if isinstance(value, dict):
        return {k: _trim(v) for k, v in value.items()}
    return value


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--landmark", default="EiffelTower", help="地标 target_id")
    args = parser.parse_args()

    from apps.landmarks.models import Landmark

    landmark = Landmark.objects.filter(target_id=args.landmark).first()
    if landmark is None:
        raise SystemExit(f"地标不存在: {args.landmark}（不虚构地标，请先确认种子数据）")

    with override_settings(TRIPSCAPE2_ENABLED=True):
        resp = Client().get(f"/api/narrative/card/{landmark.id}")
    if resp.status_code != 200:
        raise SystemExit(f"端点返回 {resp.status_code}: {resp.content[:300]!r}")

    data = resp.json()["data"]
    missing = [f for f in CARD_FIELDS if f not in data]
    if missing:
        raise SystemExit(f"响应缺少字段，拒绝写快照：{missing}")

    fields = {}
    for name in CARD_FIELDS:
        type_name, doc = FIELD_DOC[name]
        entry = {"type": type_name, "required": True, "doc": doc}
        if name in ("timeFragments", "ragSnippets"):
            items = data[name] or []
            entry["minItems"] = 1
            entry["observedItems"] = len(items)
            if items:
                entry["itemFields"] = sorted({k for k in items[0]})
        if name == "geo":
            entry["observedKeys"] = sorted(data["geo"])
        if name == "confidence":
            entry["range"] = [0, 1]
            entry["observed"] = data["confidence"]
        fields[name] = entry

    snapshot = {
        "artifact": "A2-card-schema.snapshot",
        "generatedAt": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "spec": "SPEC.md §2 S2（固定字段集）/ §3.3（契约测试 + 字段快照）",
        "source": {
            "endpoint": "GET /api/narrative/card/{landmark_id}",
            "recognitionFieldSource": "POST /api/recognition/recognize（tripScape2 开启时并入同一字段集）",
            "landmark": {
                "id": landmark.id,
                "targetId": landmark.target_id,
                "name": landmark.name,
                "country": landmark.country,
                "region": landmark.region,
            },
            "dataProvenance": {
                "timeFragments": "runtime/index/qa_chunks.json（文章库章节句）或 db:ts_landmark.intro",
                "ragSnippets": "services/article_qa.ArticleIndex.search（向量+BM25+RRF）或 db:ts_landmark.intro",
                "geo/title/photo": "db:ts_landmark（lat/lon/name/country/region/image_url）",
            },
        },
        "fieldOrder": CARD_FIELDS,
        "fields": fields,
        "extensionFields": {
            name: {"doc": doc, "present": name in data}
            for name, doc in EXTENSION_DOC.items()
        },
        "constraints": [
            "timeFragments 与 ragSnippets 必须为非空数组",
            "confidence 必须为 0–1 数值",
            "photo 必须为 URL 字符串引用，不复制文件",
            "landmarkId 必须与识别响应 landmark_id 一致",
        ],
        "sampleNote": "以下示例值由脚本截断自真实响应，未改写文本；文化内容解释权归人",
        "sample": _trim({k: data[k] for k in CARD_FIELDS}),
    }

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(snapshot, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"snapshot written: {OUT.relative_to(ROOT)}")
    print(json.dumps({"fieldOrder": CARD_FIELDS, "timeFragments": len(data["timeFragments"]),
                      "ragSnippets": len(data["ragSnippets"]), "confidence": data["confidence"]},
                     ensure_ascii=False))


if __name__ == "__main__":
    main()
