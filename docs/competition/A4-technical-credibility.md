# A4 技术可信度页（Technical Credibility）

> 用途：支撑"文化叙事不硬编、识别可核查、碎片机制可验证"的伦理主张。
> 纪律：本页**每条声明都必须附代码位置、测试名或数据文件路径**；
> 不写无证据的性能/效果声明，不写"准确率很高""业界领先"这类不可核对的话。
> 文化内容的最终解释权归人（SPEC §3.7）。

## 0. 本页的写法（先声明纪律，再给证据）

| 允许写 | 禁止写 |
|---|---|
| "在本机、对 26 张地标图（其中 23 张不在索引内），top-1 命中 26/26" | "识别准确率 100%" |
| "RRF 分数理论上界 2/61 ≈ 0.032787，本次实测触及 0.032787" | "检索效果业界领先" |
| "低于 0.35 时附带候选列表，但仍以 top-1 为默认结果" | "低置信度会拒答（没说什么算低）" |
| "碎片在 (fragment, user) 上唯一" | "保证不会被重复拾取（没有约束）" |

## 1. 识别置信度：来源、自评、局限

### 1.1 管线与数据来源（全部可打开核对）

| 环节 | 实现 | 证据路径 |
|---|---|---|
| 图像 -> 向量 | DINOv2（ViT-S/14 权重本地化） | `backend/services/retrieval_engine.py`；权重 `models/dinov2/` |
| 向量 -> 最近邻 | FAISS 索引（本地文件） | `runtime/index/landmarks.faiss`（约 527 KB） |
| 索引 -> 地标元数据 | 351 条注册图元数据 | `runtime/index/landmarks.meta.json`（351 条）；`landmarks.manifest.json`（`count=351`） |
| 结果 -> 置信度与候选 | top-3 候选 + 阈值判定 | `backend/services/recognition_service.py::_build_result`（`confidence` / `low_confidence` / `candidates`） |

索引构建脚本：`scripts/register_landmarks.py`。**注意**：`landmarks.meta.json` 记录的 351 条
注册图路径中，有 **333 条在当前磁盘上已不存在**（meta 指向 `*_177.jpg` 等旧编号文件名，
而 `data/` 现为 `*_1.jpg` 等另一批文件），因此"用现在这份 `data/` 重建索引"并不可行，
本轮也不宣称索引可原地重建。

### 1.2 自评结果（跨批次自评，**不是泛化指标**）

评测协议（由脚本自动统计，不是人工口述）：每个地标取 `data/<target_id>/` 下按文件名排序的第 1 张，
共 **26 张**；其中**只有 3 张**（`HeavenTemple_1` / `Petra_1` / `Stonehenge_1`）与索引注册图同名，
**23 张是索引外照片**。因此本次更接近"跨批次小样本"，而不是"拿考题考自己"。

| 指标 | 数值 | 说明 |
|---|---|---|
| 评测图在索引内 / 索引外 | **3 / 23** | `evaluated_in_index=3`；重合由脚本比对 `meta.json` 文件名得出 |
| 索引注册图数 / 磁盘缺失路径 | **351 / 333** | `registered_images=351`、`meta_paths_missing_on_disk=333` |
| top-1 命中 | **26 / 26**（`top1_rate=1.0`） | 每类仅 1 张、无对抗样本，不能外推 |
| 置信度 min / median / max | **0.936256 / 0.999756 / 0.999984** | 中位由 `statistics.median` 计算（26 个值的中位） |
| 置信度分桶 | `<0.35`:0；`0.35–0.70`:0；`>=0.70`:26 | 评测图偏"干净"，不代表真实场景分布 |
| 单图耗时（本机 CPU，热态） | **首图 2401 ms**；其余 min **59 ms** / median **65 ms** / max **2401 ms** | 首图含首次推理预热；仅记录事实，不作性能承诺 |
| 引擎装载耗时（同进程） | **3.4 s** | `engine_load_seconds`：**包含** torch/faiss 首次导入与 `models/dinov2/` 本地权重加载，**不含**权重下载 |

证据文件：`docs/competition/evidence/a4-recognition-selfcheck.json`
（含 26 行逐图明细：`image` / `in_index` / `top1` / `hit` / `confidence` / `top3` / `elapsed_ms`）。
复现命令：

```powershell
$env:DB_ENGINE='sqlite'
.venv\Scripts\python.exe scripts\recognition_selfcheck.py
```

> **局限（必须随图一起展示）**：每类只有 1 张图、无对抗样本；23/26 是索引外照片，但仍属
> 同一批采集风格。26/26 不能外推为对任意照片的准确率。真实场景分布需要人工标注集，
> 本轮未构造，因此本页**不提供任何泛化准确率数字**。

## 2. 低置信度候选机制（默认结果 + 附加候选，不是"拒答"）

### 2.1 机制链路

```
settings.RECOG_CONFIDENCE_THRESHOLD (默认 0.35)
  -> recognition_service._build_result(): low_confidence = confidence < threshold
  -> 命中时**额外附带**候选：candidates = top-3 去掉 top-1（landmark_id/target_id/name/confidence/image_url）
  -> 响应仍是 success=true，top-1 仍作为默认结果返回；候选是"另外可能是什么"的附加区块
  -> 前端 MessageBar 在 low_confidence 时把候选渲染成可点的列表（细节见下）
```

> 措辞纠正：本机制**不是**"拒答"或"不硬判"，而是"给出默认结果 + 附加候选"。
> 真正的拒答语义在问答侧（`services/article_qa.py` 的 `UNKNOWN_ANSWER` / "文章未提及"），不在识别侧。

| 环节 | 代码位置 |
|---|---|
| 阈值定义 | `backend/config/settings/base.py`（`RECOG_CONFIDENCE_THRESHOLD=(float, 0.35)`，`.env` 可覆盖） |
| 判定与候选 | `backend/services/recognition_service.py`（`low_confidence = float(confidence) < settings.RECOG_CONFIDENCE_THRESHOLD`；候选组装） |
| 响应字段 | 同上：`"low_confidence"`、`"candidates"` |
| 前端呈现 | `frontend/src/features/qa/MessageBar.tsx`（`m.low_confidence && m.candidates?.length` 时渲染候选） |

### 2.2 可运行证据

| 测试 | 断言 | 结果 |
|---|---|---|
| `tests/backend/test_a4_low_confidence_gate.py::test_low_confidence_returns_candidates` | 注入 `threshold-0.1` 的置信度：`low_confidence=True`、`candidates` 非空、候选字段完整、候选置信度均 < 阈值 | PASSED |
| `tests/backend/test_a4_low_confidence_gate.py::test_high_confidence_has_no_candidates` | 注入 `threshold+0.5`：`low_confidence=False`、`candidates == []` | PASSED |

日志：`docs/competition/evidence/a4-low-confidence-green.log`（`2 passed`）。
说明：该测试是对**既有闸门**的核验，不新增能力；它替换的只有"模型输出"，判定与响应仍走真实服务与真实地标。

## 3. 文化内容不硬编：卡片文字从哪来

| 声明 | 证据 |
|---|---|
| `timeFragments` 来自文章库真实句，不是手写文案 | `backend/services/narrative_service.py::_time_fragments`（章节限于 历史沿革/概述/前言） |
| 句子无年份时 `year=null`，**不补写年份** | 同函数：`_extract_year` 抽不到即 `None` |
| 索引缺失时降级为地标简介原句（`source=db:ts_landmark.intro`） | 同函数降级分支；`ragSnippets` 同理（`section="intro"`、`score=null`） |
| `ragSnippets` 是真实混合检索结果（向量 + BM25 + RRF） | `backend/services/article_qa.py::ArticleIndex.search`（`K=60`） |
| 卡片字段集与真实响应对齐 | `docs/competition/A2-card-schema.snapshot.json`（`fieldOrder` 9 键 + `extensionFields.createdAt`） |
| 数据底盘规模 | `runtime/index/qa_chunks.json`：144 chunks / 26 地标 / 8 类章节 |

> 本页不解释任何地标的历史含义——四类降级分支只保证"没有数据时不编"，
> 不保证"有数据时解释正确"，后者由人负责。

## 4. 碎片：匿名投递与单次拾取

| 机制 | 实现 | 证据 |
|---|---|---|
| 投递额度（同**用户** × 同地标 ≤ 3） | `fragment_limit()`（读 `TRIPSCAPE2_MAX_FRAGMENTS_PER_LANDMARK`；按 `delivered_by + landmark` 计数） | `backend/services/narrative_service.py`；测试 `tests/backend/test_s3_fragment_delivery.py`（前 3 次 200，第 4 次 409） |
| 单次拾取（同碎片 ≤ 1 次/人） | 数据库唯一约束 + 服务层显式拒绝 | `backend/apps/narrative/models.py::FragmentPickup`（`unique_together=(fragment, user)`）；`narrative_service.pick_fragment_by_id`；测试 `tests/backend/test_s3_fragment_pickup.py` |
| 匿名性（响应不含投递者） | `fragment_payload()` 固定 `anonymous=true`，无投递者字段 | `backend/services/narrative_service.py`；测试 `test_s3_fragment_pickup.py`（断言无 `deliveredBy/user`） |
| 随机拾取排除自投 | `_unpicked_queryset` 排除 `delivered_by=user`；**按 ID 拾取不排除**（`pick_fragment_by_id` 无此校验） | `narrative_service._unpicked_queryset`；测试 `test_own_fragment_is_not_pickable`（仅覆盖随机拾取） |
| 只能投递手账中的卡片 | 服务层校验 `JournalCard` 存在 | `narrative_service.deliver_fragment`（403）；测试 `test_deliver_rejects_card_not_in_journal` |
| 手动复核 | 真实 HTTP 序列 | `docs/competition/evidence/s3-manual-curl.log`（200/200/200/409 + 拾取 200 + 二次拾取 409） |

## 5. 已知缺口与风险（诚实清单）

| # | 缺口 | 影响 | 是否本轮处理 |
|---|---|---|---|
| K1 | 前端 `JournalEditWindow` 调 `/api/uploads/image`，后端未挂载该路由（升级前既有） | 用户上传手账图会 404；叙事卡片 `photo` 回退地标百科图 | 否（超出 §2 范围，已写入 A3 `known_gaps` K1） |
| K2 | `ts_narrative_*` 未接既有审核流（`ts_journal.status`） | 叙事层内容没有 pending/approved 审核状态 | 否（属既有治理链路职责） |
| K3 | **服务层未校验"卡片所属地标 == 投递地标"** | 跨地标投递当前可行（`s3-manual-curl.log` 即：源卡片 landmarkId=1 投到 landmark 8 得 200）；前端只传卡片自身 landmarkId，属 UI 约定而非实现约束 | 否（§2 未要求该校验，不加） |
| K4 | 地标现建的卡片 `confidence=0.0` | 前端显示"置信 0%"，代表"未识别，不宣称确信" | 设计如此，已在 A2 M4 注明 |
| K5 | 自评非泛化（26 张里 23 张在索引外） | 不能对外宣称准确率 | 已在 §1.2 显著标注 |
| K6 | 引擎装载 3.4 s（含 torch/faiss 首次导入与本地权重加载）；首图 2401 ms（含首次推理预热） | 首个识别请求偏慢 | 记录事实，未优化（§5 禁引重型依赖） |

## 6. 声明 → 证据索引（供评审逐条抽查）

| 声明 | 证据类型 | 路径 |
|---|---|---|
| 识别用 DINOv2 + FAISS 检索式管线 | 代码 | `backend/services/retrieval_engine.py` |
| 索引规模 351 张注册图（其中 333 条路径在磁盘已缺失） | 数据文件 | `runtime/index/landmarks.manifest.json`、`landmarks.meta.json` |
| 跨批次自评 top-1 = 26/26，置信度 min/median/max，评测图 3 张在索引内 / 23 张在外 | 实测报告 | `docs/competition/evidence/a4-recognition-selfcheck.json` |
| 低置信度附带候选（顶部仍返回 top-1） | 测试 + 代码 | `tests/backend/test_a4_low_confidence_gate.py`、`recognition_service.py` |
| RRF 分数理论上界 2/61 ≈ 0.032787，实测触及 0.032787 | 数据 + 代码 | `docs/competition/A2-card-schema.snapshot.json`（`sample.ragSnippets[0].score`）、`backend/services/article_qa.py`（K=60） |
| 卡片字段集与真实响应对齐 | 快照 | `docs/competition/A2-card-schema.snapshot.json` |
| 时间碎片/检索片段不编造 | 代码 + 数据 | `narrative_service.py`、`runtime/index/qa_chunks.json` |
| 同地标 ≤ 3 条投递 | 测试 | `tests/backend/test_s3_fragment_delivery.py` |
| 单次拾取唯一 | 测试 + 表约束 | `tests/backend/test_s3_fragment_pickup.py`、`apps/narrative/models.py` |
| 叙事三层流程可走通 | e2e | `e2e/narrative-journal.spec.ts`、`evidence/s1-e2e-green.log` |

## 7. 本页不声称的内容

- 不声称识别在真实场景的准确率（未构造人工标注集）；
- 不声称性能/并发指标（只有单图热态耗时的事实记录）；
- 不声称文化解释的正确性（只保证"无数据不编"）；
- 不声称审核治理已覆盖叙事层（K2 明示缺口）。
