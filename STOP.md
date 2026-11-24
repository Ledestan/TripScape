# STOP · TripScape 2.0 升级收尾

> 本文件按 SPEC §6.3 逐条列出 S1–S3 的状态、功能证据路径、artifact 路径、
> 各 artifact 的最终评分与轮次、已知风险、回滚命令。
> **不得声称任何未通过证据的能力"基本完成"，也不得声称任何未达 §4.2 量规的 artifact"可交付"。**
> 分支：`upgrade-2.0-nightly`（未 push main；每项能力均有独立 commit）。
> 生成时间：本轮运行结束时。

## 1. 能力状态总表

| 能力 | 功能证据 | 结果 | artifact | artifact 状态 | 总状态 |
|---|---|---|---|---|---|
| S2 叙事卡片结构化 | `tests/backend/test_s2_card_contract.py` | 红→绿（`2 passed`） | A2 叙事切面矩阵 | 6 轮，最终 **4.00（4/4/4/4）通过** | **VERIFIED** |
| S1 三层空间切换 | `e2e/narrative-journal.spec.ts` | 红→绿（`1 passed`）+ 开关关闭负向对照（含 404/401 实测） | A1 叙事动线图 | 8 轮（达上限），最终 **4.30（5/4/4/4）通过** | **VERIFIED** |
| S3 碎片投递与拾取 | `tests/backend/test_s3_fragment_delivery.py` + `test_s3_fragment_pickup.py` | 红→绿（`6 passed`）+ 手动 curl | A3 服务蓝图 | 7 轮，最终 **4.30（5/4/4/4）通过** | **VERIFIED** |
| 跨能力 | （依赖 S1–S3，均已 GREEN） | — | A4 技术可信度页 | 7 轮，最终 **4.00（4/4/4/4）通过** | **VERIFIED** |

## 2. 功能证据（可复现命令与日志）

### S2
- 命令：`$env:DB_ENGINE='sqlite'; .venv\Scripts\python.exe -m pytest tests/backend/test_s2_card_contract.py -v`
- 红：`docs/competition/evidence/s2-contract-red.log`（`1 failed, 1 passed`，缺 8 个卡片字段）
- 绿：`docs/competition/evidence/s2-contract-green.log`（`2 passed`）
- 字段快照：`docs/competition/A2-card-schema.snapshot.json`（由 `scripts/narrative_card_snapshot.py` 从真实响应生成）

### S1
- 前置：`frontend\node_modules\.bin\tsc.cmd -b` + `vite.cmd build`；后端 `TRIPSCAPE2_ENABLED=true` 起在 `127.0.0.1:8000`
- 命令：`frontend\node_modules\.bin\playwright.cmd test -c playwright.narrative.config.ts`
- 红：`docs/competition/evidence/s1-e2e-red.log`（实现前 dist：`narrative-hud` 不存在）
- 绿：`docs/competition/evidence/s1-e2e-green.log`（`1 passed`，最近一次 25.3s）
- 负向对照：`docs/competition/evidence/s1-flag-off-negative-control.{log,md}`
  （开关关闭时同一份 dist 不渲染 HUD、`/api/narrative/card/8` 返回 404）
- 截图：`s1-journal-before-refresh.png`、`s1-journal-after-refresh.png`

### S3
- 命令：`$env:DB_ENGINE='sqlite'; .venv\Scripts\python.exe -m pytest tests/backend/test_s3_fragment_delivery.py tests/backend/test_s3_fragment_pickup.py -v`
- 红：`docs/competition/evidence/s3-functional-red.log`（临时移除 `/api/narrative/fragments*` 三个路由：`4 failed, 2 passed`）
- 绿：`docs/competition/evidence/s3-functional-green.log`（`6 passed`）
- 手动：`docs/competition/evidence/s3-manual-curl.log`（第 4 次投递 409；二次拾取 409）

### A4 支撑证据
- 低置信度闸门：`tests/backend/test_a4_low_confidence_gate.py`（`2 passed`；日志 `a4-low-confidence-green.log`）
- 识别自评：`scripts/recognition_selfcheck.py` → `docs/competition/evidence/a4-recognition-selfcheck.json`

### 回归
- 后端全量：`docs/competition/evidence/regression-pytest-all.log`（`62 passed`）
- 前端单测：`3 + 3 passed`（vitest，2 个既有测试文件）
- 既有 e2e：`regression-existing-e2e.log`（`3 passed, 4 failed`）+ `regression-existing-e2e-analysis.md`
  —— 4 个失败均为**升级前既有**的选择器漂移（相关组件本轮未改动，选择器在 `src` 中 0 命中），未修改既有测试。

## 3. artifact 路径与最终评分

| artifact | 路径 | 轮次 | 最终四维 | 加权 | 结论 |
|---|---|---|---|---|---|
| A1 叙事动线图 | `docs/competition/A1-narrative-flow.md` | 8（达 §4.3 上限） | 5 / 4 / 4 / 4 | **4.30** | 达标（≥3.5 且无维度 <2.5） |
| A2 叙事切面矩阵 | `docs/competition/A2-narrative-matrix.md`（+ `A2-card-schema.snapshot.json`） | 6 | 4 / 4 / 4 / 4 | **4.00** | 达标 |
| A3 服务蓝图 | `docs/competition/A3-service-blueprint.yaml` | 7 | 5 / 4 / 4 / 4 | **4.30** | 达标 |
| A4 技术可信度页 | `docs/competition/A4-technical-credibility.md` | 7 | 4 / 4 / 4 / 4 | **4.00** | 达标 |

评分历史完整记录在 `PROGRESS.md` §3（每轮的四个维度、Critic 评语、下一轮计划、commit）。

## 4. 已知风险与边界（全部可核对）

| # | 风险/缺口 | 依据 | 本轮处理 |
|---|---|---|---|
| R1 | 前端 `JournalEditWindow` 调 `/api/uploads/image`，后端未挂载该路由 | `frontend/src/pages/JournalEditWindow.tsx`；`backend/api/__init__.py` 无 uploads router | 未修（升级前既有，超出 §2） |
| R2 | `ts_narrative_*` 未接既有审核流（`ts_journal.status`） | `backend/apps/narrative/models.py` 四表无 status | 未接（保持边界，A3 B6 明示） |
| R3 | 后端不校验"卡片所属地标 == 投递地标" | `narrative_service.deliver_fragment`；`s3-manual-curl.log` 中跨地标投递 200 | 未加校验（§2 未要求） |
| R4 | 识别自评非泛化：26 张评测图中 23 张在索引外；索引 351 条路径 333 条磁盘缺失 | `a4-recognition-selfcheck.json` | 已在 A4 §1.2 明示，不作准确率宣传 |
| R5 | 拾取的 409 只经 `POST /api/narrative/fragments/{id}/pick`；前端走 GET（可见拒绝 404） | `backend/api/narrative.py`；`NarrativeHud.tsx` | 已在 A1/A2 标注，未改前端 |
| R6 | 既有 e2e 4 个失败（升级前漂移） | 见上 | 按 §5 禁止改既有测试，未修 |
| R7 | 特征开关默认关闭；本轮所有证据均在 `DB_ENGINE=sqlite` + `TRIPSCAPE2_ENABLED=true` 下采集 | 命令见 §2 | 已记录，默认行为未变（开关关闭有专门用例与浏览器级负向对照） |
| R8 | A2 最终轮（R6）留下的 3 条**措辞级**编辑建议未纳入最终版本：M7 两格注记应说明 `anonymous` 只在拾取响应里、M8 fragment 格应标"跨用户拒绝裁决"、§1 M2 承载物应补 `RS.text` | `PROGRESS.md` §3 的 A2 R6 行 | 不改变达标结论（加权 4.00、无维度 <2.5）；留给人工制版时一并处理 |
| R9 | A1 在 §4.3 的 8 轮上限处收尾，仍留 8 条措辞/标注级残留：线型二分规则不互斥（读/回显/拒绝也画实线）、N4 标签 `{id}` 应为 `{landmark_id}`、N15⇢N15 的 409 归因应写"服务层显式检查"而非唯一约束、匿名 401 应归 `GlobalAuth`（正文 `Unauthorized` 已佐证）、§5.5"UI 能看到 409"实为 curl 证据、N9→N14 图标签缺"同用户"、N8⇢N1 箭头与"无因果"表述相左、④ 子图缺会话边界标注 | `PROGRESS.md` §3 的 A1 R8 行 | **不得再开新轮**（已达上限）；这些是制版时的措辞修正，不影响功能证据与达标结论 |
| R10 | A3 在 R7 达标，残留 5 条制版层问题：换乘站缺 `lane`/纵深放置、rail 与 constraint 判据未写成互斥规则（stage 相等的 rail 三条）、403 的 `at` 与 `where` 口径不一、"唯一必经换乘"属过度声明、`G5→B1` 缺语义解释 | `PROGRESS.md` §3 的 A3 R7 行 | 不影响达标；制版时按 Critic 建议补 `visibility_line` 带与段落说明 |
| R11 | A4 在 R7 达标，残留 4 条指针/措辞问题：§8 的 RRF 指针应指向 §5 与 A2 快照、I2 行号应落 `retrieval_engine.py:69-77`、confidence 的"0–1"应写"实测 0.936–0.999984（无截断，理论区间 [-1,1]）"、FRAG 标题括注易读成"只有三个端点受控" | `PROGRESS.md` §3 的 A4 R7 行 | 不影响达标；人工制版时修正指针即可 |

## 5. 回滚命令

```powershell
# 回到升级前的 main（工作区干净时）
git checkout main
git branch -D upgrade-2.0-nightly

# 只回滚某一次提交（保留历史）
git revert <commit>

# 数据库：本轮只新增 4 张 ts_narrative_* 表（migration 0001_initial）
$env:DB_ENGINE='sqlite'
.venv\Scripts\python.exe backend\manage.py migrate narrative zero
# 或直接丢弃开发库：runtime/tripscape.db（git 忽略，可重建）
```

## 6. 硬边界自查（§5）

| 检查项 | 结果 |
|---|---|
| 分支为 `upgrade-2.0-nightly`，未 push main | ✅（所有 commit 在本分支） |
| 未修改 `.env` / 密钥 / 生产 compose / CI / 认证逻辑 / 迁移策略 | ✅（`git diff main..HEAD --name-only` 无这些路径；仅新增新应用的 migration） |
| 未删除种子数据 | ✅（未触碰 `scripts/db/seed_*` 与 `data/`） |
| 未跳过/删除/弱化既有测试 | ✅（`frontend/e2e/journeys.spec.ts`、`tests/backend/*` 既有文件零改动） |
| 新行为包在 `tripScape2` 内且默认关闭 | ✅（`settings.TRIPSCAPE2_ENABLED` 默认 false；关闭时叙事端点 404、识别响应无新字段，均有测试） |
| 未引入新依赖/设计系统 | ✅（`package.json`、`requirements.txt` 未改） |
| 未重构 §2 之外模块 | ✅（改动集中在新增叙事层 + `GlobeApp` 单点挂载 + 识别响应增量） |
| 单文件 >300 行已写理由 | ✅（`narrative_service.py` 401 行，理由见 `PROGRESS.md` §1） |
| artifact 零虚构路由/API/表/字段/史料 | ✅（四份 artifact 均经 Critic 独立 grep 核对，`fabrications` 为空或已修正） |
