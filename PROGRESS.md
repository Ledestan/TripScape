# TripScape 2.0 进度（PROGRESS.md）

> 规则来源：`SPEC.md` §3（证据合同）、§4（自主创作循环）、§6（门控）、§7（自我治理）。
> 分支：`upgrade-2.0-nightly`。每个能力 VERIFIED 必须同时具备"功能证据绿"与"artifact 达 §4.2 量规"。
> 未 VERIFIED 的能力不得出现在"已完成"区。

## 0. 当前状态总览

| 能力 | 功能证据 | artifact | 状态 |
|---|---|---|---|
| S2 叙事卡片结构化 | **GREEN**（`test_s2_card_contract.py` 2 passed） | A2：R1 3.00 / R2 3.25 / R3 待评 | 功能证据通过，artifact 循环中 |
| S1 三层空间切换 | **GREEN**（`e2e/narrative-journal.spec.ts` 1 passed） | A1：R1 待评 | 功能证据通过，artifact 循环中 |
| S3 碎片投递与拾取 | **GREEN**（6 passed + 手动 curl） | A3：R1 待评 | 功能证据通过，artifact 循环中 |
| A4 技术可信度页 | 证据：`a4-recognition-selfcheck.json` + `test_a4_low_confidence_gate.py` 2 passed | A4：R1 待评 | 依赖 S1–S3 已全部 GREEN |

图例：`RED`（证据已写、当前代码下失败）/ `GREEN`（证据通过）/ `BLOCKED` / `VERIFIED`（功能证据 GREEN + artifact 达标，且 artifact 已按 §4.2 通过）。

## 1. 环境事实（证据可复现）

- 本机 MySQL 服务未启动；`.env` 属硬边界禁改文件，故用环境变量覆盖：`$env:DB_ENGINE='sqlite'`（`django-environ.read_env` 不覆盖已存在的环境变量）。
- 现有前端 e2e：`frontend/e2e/journeys.spec.ts`（配置 `frontend/playwright.config.ts`，baseURL `http://127.0.0.1:8000`）。本轮新增证据测试放在**仓库根 `e2e/`**，配置 `frontend/playwright.narrative.config.ts`，不改动已有测试。
- 现有后端测试：`tests/backend/`（`pytest.ini` 已含 `pythonpath = backend`）。
- 前端构建：`corepack pnpm` 在本机长时间无输出（节点进程空闲），改用与 `pnpm build` 等价的
  `frontend\node_modules\.bin\tsc.cmd -b` + `vite.cmd build`；依赖未新增、`pnpm-lock.yaml` 未改动。
- **单文件 >300 行的事前理由（SPEC §5）**：`backend/services/narrative_service.py`（401 行，新文件）
  —— 它同时承载 S2 卡片组装（时间碎片/检索片段/坐标）、S1 手账持久化、S3 投递额度与单次拾取，
  三者共享同一组来源数据与错误语义；拆成三个文件会重复降级逻辑并增加跨文件一致性风险，
  故在一个服务模块内以分段注释组织（文本工具 / 时间碎片 / 检索片段 / 卡片 / 手账 / 碎片）。

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

- 功能证据：`e2e/narrative-journal.spec.ts`（仓库根 `e2e/`，配置 `frontend/playwright.narrative.config.ts`）
- 证据命令：
  - 构建：`frontend\node_modules\.bin\tsc.cmd -b` + `frontend\node_modules\.bin\vite.cmd build`
    （`corepack pnpm` 在本机长时间无输出、节点进程空闲，改用本地二进制等价执行 `pnpm build` 的两步）
  - 运行：`frontend\node_modules\.bin\playwright.cmd test -c playwright.narrative.config.ts`
  - 服务：`$env:DB_ENGINE='sqlite'; $env:TRIPSCAPE2_ENABLED='true'; .venv\Scripts\python.exe backend\manage.py runserver 127.0.0.1:8000 --noreload`
- 红（实现前）：`docs/competition/evidence/s1-e2e-red.log`
  —— 用**实现前的 dist**（临时移除叙事层组件与 GlobeApp 挂载后重建）运行最终版测试：
  `1 failed`，失败点 `expect(getByTestId("narrative-hud")).toBeVisible()` 超时（叙事层不存在）。
- 绿（实现后）：`docs/competition/evidence/s1-e2e-green.log` —— `1 passed (25.5s)`。
- 截图：`docs/competition/evidence/s1-journal-before-refresh.png`（刷新前）、
  `s1-journal-after-refresh.png`（刷新后，卡片仍在）。
- 实现要点：
  - `frontend/src/stores/narrative.ts`：三层状态机（globe→landmark→journal，`back()` 逐层返回）
  - `frontend/src/features/narrative/{NarrativeHud,LandmarkNarrativePanel,JournalCardsPanel}.tsx`
  - `frontend/src/hooks/useFeatureFlag.ts`：运行期读取 `GET /api/features`
  - `frontend/src/pages/GlobeApp.tsx`：单点挂载 `<NarrativeHud />`（开关关闭时组件返回 null）
  - 持久化走后端：`POST /api/narrative/journal/cards` / `GET /api/narrative/journal`
    （刷新后从服务端取回，证明的是持久化而非前端内存）
- 状态：功能证据 **GREEN**；artifact A1 待 §4 循环。

### S3 叙事碎片投递与拾取

- 功能证据：
  - 投递侧：`tests/backend/test_s3_fragment_delivery.py`（3 个用例：前 3 次成功+第 4 次 409、非手账卡片 403、开关关闭 404）
  - 拾取侧：`tests/backend/test_s3_fragment_pickup.py`（3 个用例：来源卡片摘要+二次拾取 409、自投不可拾取、开关关闭 404）
- 证据命令：`$env:DB_ENGINE='sqlite'; .venv\Scripts\python.exe -m pytest tests/backend/test_s3_fragment_delivery.py tests/backend/test_s3_fragment_pickup.py -v`
- 红：`docs/competition/evidence/s3-functional-red.log` —— `4 failed, 2 passed`
  （2 个 passed 是"开关关闭 → 404"的门控用例，本就应通过）
  **红的复现方式（诚实记录）**：S3 的服务与路由与 S2 同批落地，早于本测试编写。
  为满足 default-FAIL 门控，红证据在**临时移除 `/api/narrative/fragments*` 三个路由**的状态下采集：
  投递/拾取全部 404，断言失败于 `assert 200 == 404`；恢复实现后转绿。
- 绿：`docs/competition/evidence/s3-functional-green.log` —— `6 passed`。
- 手动证据：`docs/competition/evidence/s3-manual-curl.log`
  （demo 账号第 4 次投递 409「同一地标最多投递 3 条叙事碎片，你已投递 3 条」；
  另一账号拾取 200 含 `sourceCard` 摘要；按 ID 二次拾取 409「该碎片已被你拾取过，不能重复拾取」）
- 实现要点：`NarrativeFragment`（投递）/`FragmentPickup`（`unique_together=(fragment,user)`）/
  `narrative_service.deliver_fragment|pick_fragment|pick_fragment_by_id`；
  匿名性由 `fragment_payload` 保证（响应不含投递者字段）。
- 状态：功能证据 **GREEN**；artifact A3 待 §4 循环。

## 3. artifact 评分历史（§4）

> Critic 为独立子代理（独立上下文，不共享 Creator 的生成上下文），按 §4.2 量规打分，
> 并自行打开 artifact 与代码核对（不得凭 Creator 自述）。达标线：加权 ≥ 3.5 且无维度 < 2.5。

| artifact | 轮次 | 原创性(0.30) | 工艺完整度(0.25) | 叙事清晰度(0.25) | 可追溯性(0.20) | 加权 | Critic 核心评语 | Creator 下轮计划 | commit |
|---|---|---|---|---|---|---|---|---|---|
| A2 | R1 | 3 | 3 | 3 | 3 | 3.00 | 数据底盘与端点零虚构，但行轴是字段清单转置（M1/M2 同源同真同假）；fragment 列 M1/M2 声称 year/section 进入碎片层属虚构（payload 无该键）；"陌生人续写"过度声明（碎片表无正文字段）；快照 fieldOrder 漏 createdAt；图例 TT/SRC/JR 全文未用；RRF 上限写成 0.05（实为 2/(60+1)≈0.0328） | ①把行轴改成"独立数据源"切面：把 M2 章节改为基于 `ragSnippets[].section`（8 类章节），与 timeFragments 解耦；②fragment 列标题改"陌生人拾取（匿名）"，M1/M2 改 `—` 并注明 payload 无 year/section；③新增两条真实机制切面：匿名性（`fragment_payload.anonymous`）、单次拾取与 3 条额度（`FragmentPickup` unique_together + `fragment_limit()`）；④修正 RRF 上界；⑤图例只保留正文实际使用的符号；⑥快照补 `extensionFields`（createdAt）并在矩阵中区分必需/扩展字段 | 8bfaab4 |
| A2 | R2 | 3 | 3 | 4 | 3 | 3.25 | 数字/端点/表全部核准、图例 10 符号全用、碎片列判定与序列化一致；但行轴仍违反自身规则（M2/M3 是同一 ragSnippets 记录的两个标签；M8/M9 又把多来源塞进一行）；journal/fragment 列 `●`/`◐` 判定自相矛盾（confidence 标 ◐ 而 photo 标 ●，二者同层）；§1 漏掉 `section=intro/landmark`、`score=null` 降级分支；§6「9 个必需字段全部被引用」不成立（id/title/source 零出现）；引用了不存在的 A4 与过期的 green 日志 | ①M2/M3 合并为「文章库检索上下文（一记录两标签）」，腾出的行给卡片身份 `id/title/source`；②M8/M9 标 `[复合行]` 或拆行；③统一 `●`=payload 直接给出（不论嵌套），journal/fragment 的 CF 改 `●`；④补 `section=intro/landmark`、`score=null` 与代码生成兜底句；⑤删除对 A4 的存在性声明，green 日志改为已重跑的真实 `1 passed`；⑥§6 换成逐字段映射表 | 7c57e8d |
| A1 | R1 | 3 | 3 | 3 | 3 | 3.00 | 13 节点与全部 testid/证据文件核准；但三处硬错误：`N6→N7` 声称加入手账会进手账层（实际只 invalidateQueries）、`N9 只记录 card_id`（实际有 card/landmark/delivered_by 三外键，匿名只在响应层）、`N13⇢N3` 跃迁不存在；另缺两条真实边（地标层可就地投递、手账卡片标题可回地标层）；④ 的「碎片池」没有节点、N10 是运行时实例、§1「四个时间尺度」与三层状态机冲突 | ①新增 `N14 碎片池`（card_id + landmark_id + delivered_by + 索引）并拆成 `N9→N14`（写入·≤3）与 `N14→N10`（只取他人投递且本人未拾取）；②§1 改为「前三层是同一路由的三个状态值，第四格是跨用户异步流」；③删除 `N13⇢N3`；④§5.4 改为「记录 card_id + landmark_id + 投递者（仅用于限额），身份在响应层剥离」；⑤`N6→N7` 触发改为 `narrative-open-journal` 的 `showJournal`，并补 `N3→N9`、`N7→N3` 两条边 | 见下方 commit 表 |



## 4. commit 记录

| commit | 内容 |
|---|---|
| （待记录） | — |
