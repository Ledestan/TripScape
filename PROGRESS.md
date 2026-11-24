# TripScape 2.0 进度（PROGRESS.md）

> 规则来源：`SPEC.md` §3（证据合同）、§4（自主创作循环）、§6（门控）、§7（自我治理）。
> 分支：`upgrade-2.0-nightly`。每个能力 VERIFIED 必须同时具备"功能证据绿"与"artifact 达 §4.2 量规"。
> 未 VERIFIED 的能力不得出现在"已完成"区。

## 0. 当前状态总览

| 能力 | 功能证据 | artifact | 状态 |
|---|---|---|---|
| S2 叙事卡片结构化 | FAIL（未开始） | A2 未开始 | NOT STARTED |
| S1 三层空间切换 | FAIL（未开始） | A1 未开始 | NOT STARTED |
| S3 碎片投递与拾取 | FAIL（未开始） | A3 未开始 | NOT STARTED |
| A4 技术可信度页 | 依赖 S1–S3 | A4 未开始 | NOT STARTED |

图例：`RED`（证据已写、当前代码下失败）/ `GREEN`（证据通过）/ `BLOCKED` / `VERIFIED`（功能证据 GREEN + artifact 达标）。

## 1. 环境事实（证据可复现）

- 本机 MySQL 服务未启动；`.env` 属硬边界禁改文件，故用环境变量覆盖：`$env:DB_ENGINE='sqlite'`（`django-environ.read_env` 不覆盖已存在的环境变量）。
- 现有前端 e2e：`frontend/e2e/journeys.spec.ts`（配置 `frontend/playwright.config.ts`，baseURL `http://127.0.0.1:8000`）。本轮新增证据测试放在**仓库根 `e2e/`**，配置 `frontend/playwright.narrative.config.ts`，不改动已有测试。
- 现有后端测试：`tests/backend/`（`pytest.ini` 已含 `pythonpath = backend`）。

## 2. 能力执行记录

### S2 叙事卡片结构化

- 功能证据：`tests/backend/test_s2_card_contract.py`（2 个用例：契约成立 + 开关关闭时新字段不出现）
- 证据命令：`$env:DB_ENGINE='sqlite'; .venv\Scripts\python.exe -m pytest tests/backend/test_s2_card_contract.py -v`
- 红（先写证据，实现前）：`docs/competition/evidence/s2-contract-red.log`
  —— 在 `HEAD=be57b70` 的独立 worktree 上运行：`1 failed, 1 passed`，
  失败原因"识别响应缺少叙卡字段: id/landmarkId/photo/title/geo/timeFragments/ragSnippets/source"。
- 绿（实现后）：`docs/competition/evidence/s2-contract-green.log` —— `2 passed`。
- 字段快照：`docs/competition/A2-card-schema.snapshot.json`（由 `scripts/narrative_card_snapshot.py`
  从真实 HTTP 响应生成；EiffelTower 卡片 timeFragments=3 / ragSnippets=3）。
- 实现要点：`apps/narrative`（4 表，Django migration）、`services/narrative_service.py`
  （时间碎片取自文章库真实章节句、RAG 片段取自 `ArticleIndex.search` 真实检索）、
  `api/recognition.py`（开关开启时并入字段集）、`api/features.py`（`GET /api/features`）。
- 状态：功能证据 **GREEN**；artifact A2 待 §4 循环。

### S1 三层空间切换

- 功能证据：`e2e/narrative-journal.spec.ts`
- 结果：**待执行**

### S3 叙事碎片投递与拾取

- 功能证据：`tests/backend/test_s3_fragment_delivery.py`、`tests/backend/test_s3_fragment_pickup.py`
- 结果：**待执行**

## 3. artifact 评分历史（§4）

| artifact | 轮次 | 原创性(0.30) | 工艺完整度(0.25) | 叙事清晰度(0.25) | 可追溯性(0.20) | 加权 | Critic 核心评语 | Creator 下轮计划 | commit |
|---|---|---|---|---|---|---|---|---|---|
| — | — | — | — | — | — | — | 尚未启动（等待功能证据） | — | — |

## 4. commit 记录

| commit | 内容 |
|---|---|
| （待记录） | — |
