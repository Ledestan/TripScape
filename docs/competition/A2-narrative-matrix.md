# A2 叙事切面矩阵（Narrative Matrix）

> 定位：**结构草稿**，供展板可视化翻译使用。本文只做"切面 → 承载物 → 追溯路径"的映射，
> 不撰写任何文化解释、不编造史料；文化内容的最终解释权归人（SPEC §3.4 / §4.4）。
> 数据来源：`runtime/index/qa_chunks.json`（144 chunks / 26 地标 / 8 类章节）、
> `ts_landmark`、`ts_narrative_card`、`ts_narrative_fragment`、`ts_recognition`。

## 0. 矩阵怎么读

一张叙事卡片不是"字段清单"，而是**同一地点的多个叙事切面**同时被点亮：

| 轴 | 含义 | 系统承载 |
|---|---|---|
| 行（切面） | 这张照片可以被讲述的 8 个维度 | 卡片字段 / 检索来源标签 / 种子字段 |
| 列（叙事层） | 切面在哪一层被消费 | globe / landmark / journal / fragment 四层 |
| 格 | 该层是否真的读这个切面 | `●` 直接承载、`◐` 间接派生、`—` 不参与 |

格子里的缩写就是**追溯路径**：`TF`=timeFragments、`RS`=ragSnippets、`GEO`=geo、
`CF`=confidence、`PH`=photo、`TT`=title、`SRC`=source、`SC`=sourceCard、`JR`=journal 条目。

## 1. 切面清单（8 维，全部可追溯）

| # | 叙事切面 | 卡片字段 / 数据列 | 数据来源（真实路径） | 取值形态 |
|---|---|---|---|---|
| M1 | 纪年切面 | `timeFragments[].year` | 文章库章节句（`qa_chunks.json`: section ∈ 历史沿革/概述/前言）；缺失时 `year=null`，不补写 | 整数年份（公元前为负）/ null |
| M2 | 章节切面 | `timeFragments[].section` | 同上章节标签（历史沿革/概述/前言） | 章节名 |
| M3 | 检索切面 | `ragSnippets[].score` + `.section` | `services/article_qa.ArticleIndex.search`（向量 + BM25 → RRF） | 0–0.05 浮点相关度 |
| M4 | 地理切面 | `geo.lat / geo.lon / geo.country / geo.region` | `ts_landmark.lat/lon/country/region` | 十进制度 + 地区标签 |
| M5 | 确信度切面 | `confidence`（+ 识别响应的 `low_confidence` / `candidates[]`） | `services/recognition_service.py::_build_result`、`ts_recognition.confidence` | 0–1 浮点 |
| M6 | 影像切面 | `photo`（原图 URL 引用，不复制文件） | 上传原图 URL；无上传时回退 `ts_landmark.image_url` | URL 字符串 |
| M7 | 续写切面 | `sourceCard.snippet`（碎片附带的来源卡片摘要） | `ts_narrative_fragment` → `ts_narrative_card.rag_snippets[0]` | 截断 120 字 |
| M8 | 时间刻度切面 | 卡片 `createdAt`、手账 `addedAt`、碎片 `createdAt` | `ts_narrative_card.created_at` / `ts_narrative_journal_card.added_at` / `ts_narrative_fragment.created_at` | ISO 时间戳 |

## 2. 矩阵主体

| 切面 \ 叙事层 | globe（未被讲述） | landmark（正在被讲述） | journal（已沉淀） | fragment（陌生人续写） |
|---|---|---|---|---|
| **M1 纪年** | `—` 光点尚无时间数据 | `●` TF.year | `●` TF.year（只读快照） | `◐` 随卡片筛选进入碎片 |
| **M2 章节** | `—` | `●` TF.section | `●` TF.section | `◐` SC.snippet 的章节归属 |
| **M3 检索** | `—` | `●` RS.score / RS.section | `●` RS 快照 | `●` SC.snippet = RS[0].text |
| **M4 地理** | `●` 光点坐标（`/api/landmarks/spots`） | `●` GEO（卡片绑定坐标） | `◐` 手账条目经卡片携带 GEO | `●` 碎片绑定 `landmark_id` |
| **M5 确信度** | `—` | `●` CF + 候选列表（低置信度） | `◐` CF 随卡片冻结 | `◐` SC.confidence |
| **M6 影像** | `◐` 地标百科图 | `●` PH（原图 URL 引用） | `●` PH 只读 | `●` SC.photo |
| **M7 续写** | `—` | `◐` 拾取入口（拾取返回 SC.snippet） | `—` | `●` SC.id/title/photo/landmarkId/confidence/snippet |
| **M8 时间刻度** | `—` | `●` card.createdAt | `●` addedAt | `●` fragment.createdAt |

## 3. 切面 × 可用标签（供展板配图选择）

| 切面 | 观感关键词（结构描述，非史料结论） | 视觉承载建议 |
|---|---|---|
| M1 | 纵深：同一地点的多个年份锚点 | 竖向时间刻度尺，碎片按 year 排布 |
| M2 | 层次：不同章节讲不同尺度的事 | 同心环 / 分栏，章节名作环标 |
| M3 | 距离：检索相关度决定"讲哪一句" | 由中心向外的亮度衰减 |
| M4 | 定位：坐标把叙事钉在地球上 | 经纬网格 + 单一亮点 |
| M5 | 确信：系统敢不敢说"这是它" | 明度/透明度 = 置信度 |
| M6 | 物证：照片是唯一不可替换的输入 | 卡片主视觉位 |
| M7 | 流动：叙事离开作者，被陌生人接住 | 从卡片射出的箭头/粒子 |
| M8 | 沉淀：时间戳记录叙事被续写的时刻 | 边缘时间戳条 |

## 4. 已知缺口（诚实标注，不用文案填补）

| 缺口 | 现状 | 处理 |
|---|---|---|
| 部分地标无文章库章节 | 26 个种子地标均有文章；`timeFragments` 仍可能落到 `db:ts_landmark.intro`（`year=null`） | 矩阵按"有无纪年"分色，不伪造年份 |
| `ragSnippets[].score` 量纲 | RRF 分数（约 0.03），非概率 | 展板只做相对排序表达，不写成"准确率" |
| M3 的语义质量 | 依赖 `runtime/index` 与 bge-small-zh 模型 | 在 A4 说明索引来源与重建方式 |
| 文化解释 | 本矩阵不含任何解释性结论 | 由人完成最终解释与措辞 |

## 5. 与卡片契约的一致性

- 矩阵引用的每个字段都在 `docs/competition/A2-card-schema.snapshot.json` 的 `fieldOrder` 内；
- 矩阵没有引入快照之外的卡片字段；
- 矩阵没有引入代码中不存在的路由/表：涉及的端点为 `GET /api/narrative/card/{landmark_id}`、
  `GET /api/landmarks/spots`、`GET /api/narrative/journal`、`GET /api/narrative/fragments/pick`。
