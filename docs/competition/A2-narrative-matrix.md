# A2 叙事切面矩阵（Narrative Matrix）

> 定位：**结构草稿**，供展板可视化翻译。本文只做"切面 → 承载物 → 追溯路径"的映射，
> 不撰写文化解释、不编造史料；文化内容的最终解释权归人（SPEC §3.4 / §4.4）。
> 数据底盘：`runtime/index/qa_chunks.json`（144 chunks / 26 地标 / 8 类章节）、
> `ts_landmark`、`ts_narrative_card`、`ts_narrative_journal_card`、
> `ts_narrative_fragment`、`ts_narrative_fragment_pickup`、`ts_recognition`。

## 0. 矩阵怎么读

一张叙事卡片不是"字段清单"，而是**同一地点的多个独立叙事切面**同时被点亮。
行轴只收**独立数据源**（同一条记录派生的两个标签不占两行）：

| 轴 | 含义 |
|---|---|
| 行 = 叙事切面 | 9 个切面，每个对应一处**独立**的数据来源或系统机制 |
| 列 = 叙事层 | globe（未被讲述）/ landmark（正在被讲述）/ journal（已沉淀）/ fragment（陌生人拾取） |
| 格 = 该层是否真的消费这个切面 | `●` 直接承载 / `◐` 派生或间接 / `—` 不参与 |

格内缩写即追溯路径：

| 缩写 | 含义 | 定义位置 |
|---|---|---|
| `TF` | `timeFragments[]` | `services/narrative_service.py::_time_fragments` |
| `RS` | `ragSnippets[]` | `services/narrative_service.py::_rag_snippets` |
| `GEO` | `geo{lat,lon,place,country,region}` | `_geo` ← `ts_landmark` |
| `CF` | `confidence` | `build_narrative_card` ← 识别置信度 |
| `PH` | `photo` | 原图 URL 引用 / `ts_landmark.image_url` |
| `SC` | `sourceCard{...}` | `narrative_service.py::fragment_payload` |
| `ANON` | `anonymous=true` | 同上（投递者不进响应） |
| `PICK` | 单次拾取唯一约束 | `FragmentPickup.Meta.unique_together` |
| `QUOTA` | 同地标 3 条额度 | `fragment_limit()` |
| `TS` | 时间戳（卡片/手账/碎片） | 三张表的 `created_at` / `added_at` |

## 1. 切面清单（9 行，每行一处独立来源）

| # | 叙事切面 | 承载物 | 独立数据来源（真实路径） | 取值形态 |
|---|---|---|---|---|
| M1 | 纪年 | `TF.year` | `_time_fragments` ← 文章库历史沿革/概述句；抽不到年份即 `null`，不补写 | 整数年份（公元前为负）/ null |
| M2 | 章节 | `RS.section` | `ArticleIndex.search` 返回的 chunk 章节标签（8 类：概述/前言/历史沿革/地理位置/基本参数/参观信息/百科补充/更多介绍） | 章节名 |
| M3 | 检索相关度 | `RS.score` | `services/article_qa.py::ArticleIndex.search`（向量 + BM25 → RRF，k=60） | 0–0.0328 浮点（RRF 理论上界 2/(60+1)） |
| M4 | 地理 | `GEO.lat/lon/country/region` | `_geo` ← `ts_landmark.lat/lon/country/region` | 十进制度 + 地区标签 |
| M5 | 确信度 | `CF` | `build_narrative_card(confidence=…)` ← `recognition_service.py::_build_result` 的置信度 | 0–1 浮点 |
| M6 | 影像 | `PH` | 上传原图 URL；无上传时 `ts_landmark.image_url`（只存引用，不复制文件） | URL 字符串 |
| M7 | 匿名性 | `ANON` | `fragment_payload` 固定 `anonymous=true`；`NarrativeFragment` 无对外的投递者字段 | 布尔 + 无作者字段 |
| M8 | 单次拾取与额度 | `PICK` / `QUOTA` | `FragmentPickup`（`unique_together=(fragment,user)`）；`fragment_limit()` 默认 3 | 唯一约束 / 整数额度 |
| M9 | 时间刻度 | `TS` | `ts_narrative_card.created_at`（扩展字段 `createdAt`）、`ts_narrative_journal_card.added_at`、`ts_narrative_fragment.created_at` | ISO 时间戳 |

## 2. 矩阵主体

| 切面 \ 叙事层 | globe（未被讲述） | landmark（正在被讲述） | journal（已沉淀） | fragment（陌生人拾取·匿名） |
|---|---|---|---|---|
| **M1 纪年** | `—` 光点无时间数据 | `●` TF.year | `●` TF.year（只读快照） | `—` payload 不含 year，投递无按年筛选 |
| **M2 章节** | `—` | `●` RS.section | `●` RS.section（快照） | `—` payload 不含 section |
| **M3 检索相关度** | `—` | `●` RS.score | `●` RS.score | `●` SC.snippet = RS[0].text 截断 120 字 |
| **M4 地理** | `●` 光点坐标（`GET /api/landmarks/spots`） | `●` GEO | `◐` 经卡片携带 GEO | `●` fragment.landmarkId |
| **M5 确信度** | `—` | `●` CF | `◐` CF 随卡片冻结 | `◐` SC.confidence |
| **M6 影像** | `◐` 地标百科图 | `●` PH | `●` PH（只读） | `●` SC.photo |
| **M7 匿名性** | `—` | `—` 尚未投递 | `—` 手账是署名内容 | `●` ANON |
| **M8 单次拾取与额度** | `—` | `—` 额度在投递动作上 | `—` | `●` PICK + QUOTA |
| **M9 时间刻度** | `—` | `●` TS.createdAt（扩展字段） | `●` TS.addedAt | `●` TS.fragment.createdAt |

**读法**：从左到右，格子由空到密——空间先"被点名"（M4/M6），再"被讲述"（M1/M2/M3/M5），
再"被沉淀"（journal 全列复现），最后"被陌生人接住"（M3/M4/M6/M7/M8/M9 进入碎片层）。
M1/M2 在 fragment 列刻意留空：陌生人不该看到纪年与章节归属（匿名碎片只给摘要），
这是**设计上的边界**，不是数据缺失。

## 3. 机制切面（数据库级证据，供展板做"可信度"小图）

| 机制 | 实现 | 约束/取值 |
|---|---|---|
| 投递额度 | `narrative_service.fragment_limit()` | 同用户 × 同地标 ≤ 3（第 4 次 409） |
| 单次拾取 | `FragmentPickup.Meta.unique_together = (fragment, user)` | 第二次拾取 409 |
| 匿名 | `fragment_payload()` 固定 `anonymous=true`，无投递者键 | 响应体不可反查作者 |
| 卡片只读 | `JournalCard` 无更新端点，仅 `POST /api/narrative/journal/cards` 追加 | 手账不提供改写 |

## 4. 切面 × 观感（供展板配图，均为结构描述，非史料结论）

| 切面 | 观感关键词 | 视觉承载建议 |
|---|---|---|
| M1 | 纵深：同一地点的多个年份锚点 | 竖向刻度尺，按 year 排布 |
| M2 | 层次：不同章节讲不同尺度的事 | 分栏/环带，章节名作环标 |
| M3 | 距离：相关度决定"讲哪一句" | 由中心向外的亮度衰减 |
| M4 | 定位：坐标把叙事钉在地球上 | 经纬网格 + 单一亮点 |
| M5 | 确信：系统敢不敢说"这是它" | 明度/透明度 = 置信度 |
| M6 | 物证：照片是唯一不可替换的输入 | 卡片主视觉位 |
| M7 | 隐身：叙事离开作者时作者消失 | 卡片背面留白/无署名 |
| M8 | 稀缺：一次只能被一个人接住 | 单一出口 + 一次性闸门 |
| M9 | 沉淀：时间戳记录被续写的时刻 | 边缘时间戳条 |

## 5. 缺口与边界（诚实标注）

| 项 | 现状 | 处理 |
|---|---|---|
| 无纪年地标 | `timeFragments` 可能落到 `db:ts_landmark.intro`（`year=null`） | 按"有无纪年"分色，不伪造年份 |
| `RS.score` 量纲 | RRF 分数（理论 ≤ 0.0328），非概率 | 只做相对排序，不写成"准确率" |
| 检索质量 | 依赖 `runtime/index` 与 bge-small-zh 模型 | 索引来源与重建方式见 A4 |
| 低置信度候选 | `low_confidence` / `candidates[]` 属**识别响应**字段，不在卡片 payload 内 | 展板在"识别"侧标注，不画进卡片列 |
| 文化解释 | 本矩阵不含解释性结论 | 由人完成最终措辞 |

## 6. 与卡片契约的一致性

- SPEC 必需字段 9 个（`fieldOrder`）全部被矩阵引用，且与
  `docs/competition/A2-card-schema.snapshot.json` 的 `fieldOrder` 逐字一致；
- `createdAt` 是**扩展字段**（`as_card()` 额外返回，快照 `extensionFields` 记录），
  M9 明确标注"扩展字段"，不冒充 SPEC 必需字段；
- 矩阵不引入快照之外的卡片字段；引用的端点为 `GET /api/narrative/card/{landmark_id}`、
  `GET /api/landmarks/spots`、`GET /api/narrative/journal`、`GET /api/narrative/fragments/pick`，
  表为 `ts_landmark` / `ts_narrative_card` / `ts_narrative_journal_card` /
  `ts_narrative_fragment` / `ts_narrative_fragment_pickup` / `ts_recognition`。

## 7. 层与前端落地的对应（避免把 API 载荷当成界面）

四列对应 S1 交付的三层状态机与碎片拾取入口（`data-testid` 可在 e2e 中核对）：

| 列 | 前端载体 | 状态值 |
|---|---|---|
| globe | `features/narrative/NarrativeHud.tsx` | `layer = "globe"` |
| landmark | `features/narrative/LandmarkNarrativePanel.tsx` | `layer = "landmark"` |
| journal | `features/narrative/JournalCardsPanel.tsx` | `layer = "journal"` |
| fragment | 同上两个面板内的投递/拾取按钮（`narrative-deliver` / `narrative-pick`） | 不单独成层 |

组件未落地前，本表只声明**结构对应关系**，不声明界面已存在；UI 证据见 A1 与
`e2e/narrative-journal.spec.ts` 的红/绿日志。
