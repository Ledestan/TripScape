# TripScape 2.0 执行计划（plan.md）

> 依据：`SPEC.md`（唯一行为基准、验收合同、创作治理规则）。
> 分支：`upgrade-2.0-nightly`（禁止 push main；每完成一项 VERIFIED 能力必须 commit）。
> 本文只写"做什么 / 改哪些文件 / 用哪条命令证明 / 产出哪个 artifact"，
> 不写产品方向的自由发挥。S1–S3 之外的模块不重构。

## 0. 执行排序（按依赖，而非 SPEC 编号）

| 序 | 能力 | 理由 |
|---|---|---|
| 1 | **S2 叙事卡片结构化** | S1 的"加入手账"与 S3 的"投递/拾取"都以叙事卡片为数据单元；卡片字段契约不先成立，后两者没有可验证对象。 |
| 2 | **S1 三层空间切换** | 依赖 S2 的卡片；globe → landmark → journal 的状态机与持久化是 S3 的入口。 |
| 3 | **S3 叙事碎片投递与拾取** | 依赖 S1 的手账卡片（journal 中已存在的卡片才能投递）。 |
| 4 | **A4 技术可信度页** | 跨能力 artifact，需 S1–S3 的测试名/代码位置/数据路径全部落定后才能"每条声明附证据"。 |

artifact 顺序：A2（随 S2）→ A1（随 S1）→ A3（随 S3）→ A4（收尾）。
每个 artifact 在**对应能力功能证据变绿之后**才启动 §4 Creator–Critic 循环。

## 1. 前置与公共改动（不含业务能力）

| 项 | 内容 | 说明 |
|---|---|---|
| 分支 | `git checkout -b upgrade-2.0-nightly` | §5 硬边界 |
| 特性开关 | `backend/config/settings/base.py` 新增 `TRIPSCAPE2_ENABLED`（`env` 默认 `False`） | §5"所有新行为用 feature flag `tripScape2` 包住，默认关闭"。新 API 在开关关闭时一律 404，不改变现有默认行为 |
| 开关发现 | `backend/api/features.py`：`GET /api/features` 返回 `{"tripScape2": bool}` | 前端运行期读取开关，避免把开关编译进 dist |
| 前端读开关 | `frontend/src/hooks/useFeatureFlag.ts` | 只在开关为真时挂载叙事层 UI |
| 新增应用 | `backend/apps/narrative/`（models + migrations/0001_initial） | 叙事卡片 / 手账加入记录 / 叙事碎片 / 拾取记录；沿用 Django migrations 既有策略，不改迁移机制 |
| 新增服务 | `backend/services/narrative_service.py` | 卡片组装（时间碎片、RAG 检索片段）、手账持久化、投递限额、单次拾取 |
| 新增 API | `backend/api/narrative.py`，并在 `backend/api/__init__.py` 挂载 `/api/narrative` | 全部端点开关门控 |
| 现有 API 增量 | `backend/api/recognition.py`：开关开启时把卡片字段并入识别响应 | 纯增量键，开关关闭时响应与现在逐字节一致 |

**数据库**：仅新增 4 张 `ts_narrative_*` 表（Django migration），不删除、不修改种子数据，不改现有表结构。

## 2. S2 叙事卡片结构化（先做）

### 2.1 触碰文件
- `backend/apps/narrative/models.py`（`NarrativeCard`：id/landmark/photo/title/geo/time_fragments/rag_snippets/confidence/source/provider_user/created_at）
- `backend/services/narrative_service.py`（`build_narrative_card`：`timeFragments` 取自文章库 `runtime/index/qa_chunks.json` 的"历史沿革/概述"句（含年份的真实史料句），`ragSnippets` 取自 `services/article_qa.ArticleIndex.search` 的真实检索结果；索引缺失时降级为 `Landmark.intro` 的真实句子，**不编造文化内容**）
- `backend/api/recognition.py`（开关开启时把卡片字段并入响应：`id/landmarkId/photo/title/geo/timeFragments/ragSnippets/confidence/source`）
- `backend/api/narrative.py`（`POST /api/narrative/card/{landmark_id}`：按地标取卡片，供叙事层与 e2e 使用）

### 2.2 功能证据（先红后绿）
- 文件：`tests/backend/test_s2_card_contract.py`（新增，独立于实现：字段清单硬编码在测试内，**不从实现 import 字段列表**）
- 断言：识别接口返回对象含 §2 S2 全部 9 个字段；`timeFragments`、`ragSnippets` 为非空数组；`confidence` ∈ [0,1]；`photo` 为原图 URL（不复制文件）
- 命令：`$env:DB_ENGINE='sqlite'; .venv\Scripts\python.exe -m pytest tests/backend/test_s2_card_contract.py -v`
- 附：`docs/competition/A2-card-schema.snapshot.json`（真实响应字段快照，由 `scripts/narrative_card_snapshot.py` 生成）
- 红→绿证据：`docs/competition/evidence/s2-contract-red.log` / `s2-contract-green.log`

### 2.3 竞赛 artifact
- `docs/competition/A2-narrative-matrix.md`：叙事切面矩阵骨架；维度只能来自卡片字段、RAG 检索来源标签（`section`/`target_id`/`source`）、地标种子字段（`region/country/intro`）。不写史料解释。
- §4 循环：≥3 轮，Critic 按 §4.2 四维打分；每轮 commit + `PROGRESS.md` 记分。

## 3. S1 三层空间切换

### 3.1 触碰文件
- `frontend/src/stores/narrative.ts`（层状态机：`globe → landmark → journal`，含"返回"路径与当前地标）
- `frontend/src/features/narrative/NarrativeHud.tsx`（globe 层：地标入口列表 + 进入地标层）
- `frontend/src/features/narrative/LandmarkNarrativePanel.tsx`（landmark 层：卡片展示 + "加入手账"）
- `frontend/src/features/narrative/JournalCardsPanel.tsx`（journal 层：只读卡片列表）
- `frontend/src/pages/GlobeApp.tsx`（**仅在开关为真时**挂载 `<NarrativeHud />`，单点插入）
- `backend/api/narrative.py`：`POST /api/narrative/journal/cards`（加入手账，只读持久化）、`GET /api/narrative/journal`（刷新后取回）
- `backend/apps/narrative/models.py`：`JournalCard`（user × card 唯一，只读）

### 3.2 功能证据（先红后绿）
- 文件：`e2e/narrative-journal.spec.ts`（仓库根 `e2e/`，符合 §3.1；新增，不改动 `frontend/e2e/journeys.spec.ts`）
- 配置：`frontend/playwright.narrative.config.ts`（`testDir: ../e2e`，复用 frontend 依赖与既有 baseURL）
- 流程：登录 demo → globe → 点击地标（叙事层地标入口）→ landmark 层 → "加入手账" → journal 层断言卡片 → **刷新页面** → 再进 journal 层断言卡片仍在 → 逐层"返回"断言回到 globe
- 截图：`docs/competition/evidence/s1-journal-before-refresh.png`、`s1-journal-after-refresh.png`
- 命令（需先起开发服务器，见 §6）：
  `pnpm --dir frontend exec playwright test -c playwright.narrative.config.ts`
- 日志：`docs/competition/evidence/s1-e2e-red.log` / `s1-e2e-green.log`

### 3.3 竞赛 artifact
- `docs/competition/A1-narrative-flow.md`（附 Mermaid 源 + 由代码结构导出的节点/边表）：globe → landmark → journal → 碎片回投；每个节点标注路由/组件/端点出处。
- §4 循环：≥3 轮；每轮 commit + `PROGRESS.md` 记分。

## 4. S3 叙事碎片投递与拾取

### 4.1 触碰文件
- `backend/apps/narrative/models.py`：`NarrativeFragment`（card/landmark/delivered_by/created_at/anonymous=True）、`FragmentPickup`（fragment × user 唯一）
- `backend/services/narrative_service.py`：`deliver_fragment`（同用户同地标上限 3，第 4 次抛 409+明确消息）、`pick_fragment`（随机取未被本人拾取的；显式 re-pick 抛 409）、`fragment_payload`（来源卡片摘要，不含投递者身份）
- `backend/api/narrative.py`：
  - `POST /api/narrative/fragments`（投递）
  - `GET  /api/narrative/fragments/pick?landmark_id=`（拾取一条未拾取碎片）
  - `POST /api/narrative/fragments/{id}/pick`（显式拾取，用于证明"第二次拾取被拒绝"）
- 前端：`JournalCardsPanel` 增加"投递"按钮；`LandmarkNarrativePanel` 增加"拾取碎片"按钮（开关门控）

### 4.2 功能证据（先红后绿）
- 投递侧：`tests/backend/test_s3_fragment_delivery.py` —— 前 3 次成功，第 4 次返回明确错误码/错误消息
- 拾取侧：`tests/backend/test_s3_fragment_pickup.py` —— 同一碎片对同一用户第二次拾取被拒绝；拾取返回体含来源卡片摘要字段
- 命令：`$env:DB_ENGINE='sqlite'; .venv\Scripts\python.exe -m pytest tests/backend/test_s3_fragment_delivery.py tests/backend/test_s3_fragment_pickup.py -v`
- 手动证据：`docs/competition/evidence/s3-manual-curl.log`（curl 投递 4 次 + 拾取 2 次，含状态码与响应体）
- 日志：`docs/competition/evidence/s3-*-red.log` / `s3-*-green.log`

### 4.3 竞赛 artifact
- `docs/competition/A3-service-blueprint.yaml`：叙事流通层结构草稿（前台行为/后台触点/支持流程），每个节点附 `source` 追溯（路由/API/表/服务函数）
- §4 循环：≥3 轮；每轮 commit + `PROGRESS.md` 记分。

## 5. 跨能力 artifact A4

- `docs/competition/A4-technical-credibility.md`：置信度来源（`services/retrieval_engine.py`、`runtime/index/landmarks.manifest.json`）、低置信度拒答（`RECOG_CONFIDENCE_THRESHOLD` + 候选列表 + 测试名）、单次拾取与匿名投递机制（表唯一约束 + 服务函数 + 测试名）。每条声明附代码位置/测试名/数据路径；禁止无证据的性能声明。
- §4 循环：≥3 轮；每轮 commit + `PROGRESS.md` 记分。

## 6. 运行环境（证据可复现命令）

MySQL 服务在本机未启动；`.env` 属 §5 禁改文件，因此**用环境变量覆盖**（`django-environ` 的 `read_env` 不覆盖已存在的环境变量）：

```powershell
# 后端测试
$env:DB_ENGINE='sqlite'; .venv\Scripts\python.exe -m pytest tests/backend -v

# 开发服务器（e2e 用；dist 由 pnpm build 产出）
$env:DB_ENGINE='sqlite'; $env:TRIPSCAPE2_ENABLED='true'
.venv\Scripts\python.exe backend\manage.py runserver 127.0.0.1:8000 --noreload

# 前端构建 + e2e
corepack pnpm --dir frontend build
corepack pnpm --dir frontend exec playwright test -c playwright.narrative.config.ts
```

## 7. 门控与停止条件（执行时逐条兑现）

1. 功能证据默认 FAIL；先写测试，跑出红日志存档，再实现。
2. 红未变绿不得标记 VERIFIED；不得启动对应 artifact 的 §4 循环。
3. 同一测试修复超过 3 次 → 写 `BLOCKED.md`（失败日志/已试方案/回滚点），停止该能力。
4. artifact 到 8 轮仍未达 §4.2 量规 → 写 `BLOCKED_CREATIVE.md`（完整评分历史），停止该 artifact，不停止其他 artifact。
5. 触发 §5 任一硬边界 → 写 `ESCALATE.md` 并停。
6. 全部结束写 `STOP.md`（S1–S3 状态、证据路径、artifact 路径、最终评分与轮次、已知风险、回滚命令），不夸大、不"基本完成"。
7. 全程 `PROGRESS.md` 记录：能力编号、证据命令与结果、artifact 路径、四维评分、Critic 评语、下一轮改动、commit hash。

## 8. 明确不做（越界预防）

- 不改 `.env`、密钥、生产 compose、CI 配置、认证逻辑、迁移策略；
- 不改写/删除 `frontend/e2e/journeys.spec.ts`、`tests/backend/*` 已有文件；
- 不引入新依赖（前端复用现有 Radix/Tailwind 组件，后端仅用已装 Django/Ninja）；
- 不重构 §2 之外模块；单文件改动 >300 行前先写理由到 `PROGRESS.md`；
- 不在 artifact 中写任何代码里不存在的路由/API/表/字段/史料。
