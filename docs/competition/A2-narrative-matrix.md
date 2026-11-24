# A2 叙事切面矩阵（Narrative Matrix）

> 定位：**结构草稿**，供展板可视化翻译。本文只做"切面 → 承载物 → 追溯路径"的映射，
> 不撰写文化解释、不编造史料；文化内容的最终解释权归人（SPEC §3.4 / §4.4）。
> 数据底盘：`runtime/index/qa_chunks.json`（144 chunks / 26 地标 / 8 类章节）、
> `ts_landmark`、`ts_narrative_card`、`ts_narrative_journal_card`、
> `ts_narrative_fragment`、`ts_narrative_fragment_pickup`。
> （`ts_recognition` 只在识别时写入（`recognition_service.py::_build_result`），
> 本矩阵与 A4 都不读这张表：A4 的置信度分桶来自 `scripts/recognition_selfcheck.py` 的评测集，
> 不是 `ts_recognition` 的运行期记录，故不列底盘。）

## 0. 矩阵怎么读

一张叙事卡片不是"字段清单"，而是**同一地点的多个叙事切面**同时被点亮。

**行轴规则（本版严格执行，避免"伪多维"）**

1. 一行 = **一处独立来源**，或**一处独立机制**；同一记录派生的多个标签必须合并为一行并注明"一记录两标签"。
2. 同一语义簇的多个字段（如卡片身份 `id/landmarkId/title/source`、地理 `lat/lon/place/country/region`）
   合并为一行并标 **[复合行]**。
3. 一行内并列**同簇但不同来源**的条目（如三级降级、两个影像来源、三个时间列）必须显式标 **[复合行]**。
4. **机制行的判定按列的性质分两种**：
   - **作者侧三列（globe/landmark/journal）** 判 `●` 的判据 = **该层界面上存在触发该机制的动作控件**
     （值不一定在 payload 里）。例：landmark 与 journal 都有投递控件，故 M9 在这两列是 `●`。
   - **fragment 是非 layer 的跨用户通道，没有独立控件**，其判定按**响应值**：
     `anonymous` 字段、`sourceCard` 字段、`remaining` 回报等。
   这条规则专门用来避免"机制行判定看心情"。

| 轴 | 含义 |
|---|---|
| 行（切面） | 10 个切面：4 个单一来源/机制行（M4/M7/M8/M9）+ 1 个"一记录两标签"行（M2）+ 5 个复合行（M1/M3/M5/M6/M10） |
| 列（叙事通道） | **三个叙事层**：globe（未被讲述）/ landmark（正在被讲述）/ journal（已沉淀）；**外加一个非 layer 的通道**：fragment（陌生人拾取·匿名）。代码里 `NarrativeLayer` 只有三值，fragment 是跨用户异步通道，不是第四层 |
| 格（判定） | `●` 该层**直接承载**该切面（payload 给出值，或该层的动作/控件被该机制直接裁决） / `◐` 只给出部分或派生值 / `—` 不承载。**只有结构化字段计入承载**：正文里的偶发数字（例如 `snippet` 恰好含年份）不算 M1 承载 |

> 机制行（M7/M8/M9）的值不一定是 payload 字段：它们的"直接承载"体现在**该层有动作控件**
> 且该动作被约束裁决（例如地标层面板有拾取按钮，拾取写入受唯一约束；
> 投递按钮的响应回报 `remaining`）。判定依据写在格内注记里，不靠读者猜。

格内缩写即追溯路径：

| 缩写 | 含义 | 定义位置 |
|---|---|---|
| `TF` | `timeFragments[]` | `services/narrative_service.py::_time_fragments` |
| `RS` | `ragSnippets[]`（同一条记录同时带 section 与 score） | `services/narrative_service.py::_rag_snippets` |
| `GEO` | `geo{lat,lon,place,country,region}` | `_geo` ← `ts_landmark` |
| `CF` | `confidence` | `build_narrative_card` ← 识别置信度 |
| `PH` | `photo` | 原图 URL 引用 / `ts_landmark.image_url` |
| `ID` | `id` + `landmarkId` + `title` + `source` | `NarrativeCard.as_card()` |
| `SC` | `sourceCard{...}` | `narrative_service.py::fragment_payload` |
| `ANON` | `anonymous=true` | 同上（投递者不进响应） |
| `PICK` | 单次拾取唯一约束 + 409 裁决 | `FragmentPickup.Meta.unique_together` / `pick_fragment_by_id` |
| `QUOTA` | 同地标 3 条额度 + `remaining` 回报 | `fragment_limit()` / `deliver_fragment` |
| `TS` | 时间戳（卡片 `createdAt` / 手账 `addedAt` / 碎片 `createdAt`） | 三张表的 `created_at` / `added_at` |

## 1. 切面清单（10 行，含取值与降级分支）

| # | 叙事切面 | 承载物 | 独立来源（真实路径） | 取值形态（含降级） |
|---|---|---|---|---|
| M1 | 纪年 **[复合行：三级回落]** | `TF.year` | `_time_fragments` ← 文章库历史沿革/概述/前言句 → 地标简介 → 兜底句 | 整数年份（公元前为负）/ `null`（句无年份）；索引/文章缺失时回退 `db:ts_landmark.intro`；再无则代码生成句（`source=db:ts_landmark`，非史料） |
| M2 | 文章库检索上下文 **[一记录两标签]** | `RS.section` + `RS.score` | `ArticleIndex.search`（向量 + BM25 → RRF，k=60） | 章节名（8 类）；索引不可用时 `section="intro"`、`score=null`；无简介时 `section="landmark"`、`score=null`；`score` 理论上界 `2/61 = 0.032787` |
| M3 | 地理 **[复合行：五个键同源]** | `GEO.lat/lon/place/country/region` | `_geo` ← `ts_landmark.lat/lon/country/region`；`place`←`ts_landmark.name` | 十进制度 + 地区标签（无 country/region 时为空串） |
| M4 | 确信度 | `CF` | `_attach_narrative_card()`（`api/recognition.py`）把 `_build_result` 的置信度传入 `build_narrative_card(confidence=…)` | 0–1 浮点；地标现建的卡片为 `0.0`（未识别即不宣称确信） |
| M5 | 影像 **[复合行：两个来源]** | `PH` | ① 上传原图 URL（`photo_url` 参数）② 无上传 URL 时 `ts_landmark.image_url` | URL 字符串（只存引用，不复制文件） |
| M6 | 卡片身份与命名 **[复合行]** | `id` + `landmarkId` + `title` + `source` | `NarrativeCard.as_card()`；`title`←`_title`（地标名｜国家）；`source`←识别引擎名或 `landmark` | 整数 / 整数 / 字符串 / 字符串 |
| M7 | 匿名性 | `ANON` | `fragment_payload` 固定 `anonymous=true`；库内 `delivered_by` 只用于额度与自投排除 | 布尔 + 响应无作者键 |
| M8 | 单次拾取 | `PICK` | `FragmentPickup`（`unique_together=(fragment,user)`）+ `pick_fragment_by_id` 显式 409 | 唯一约束 / 二次拾取 409（值不在 payload，由拒绝裁决） |
| M9 | 投递额度 | `QUOTA` | `fragment_limit()`（读 `TRIPSCAPE2_MAX_FRAGMENTS_PER_LANDMARK`，默认 3） | 整数额度 / 第 4 次 409 / 成功响应回报 `remaining` |
| M10 | 时间刻度 **[复合行：三张表]** | `TS` | `ts_narrative_card.created_at`（扩展字段 `createdAt`）、`ts_narrative_journal_card.added_at`、`ts_narrative_fragment.created_at` | ISO 时间戳（三个来源分属三张表） |

## 2. 矩阵主体

| 切面 \ 叙事通道 | globe（未被讲述·layer） | landmark（正在被讲述·layer） | journal（已沉淀·layer） | fragment（陌生人拾取·跨用户通道，非 layer） |
|---|---|---|---|---|
| **M1 纪年** | `—` 光点无时间数据 | `●` TF.year | `●` TF.year（只读快照） | `—` payload 无 year，投递无按年筛选 |
| **M2 检索上下文** | `—` | `●` RS.section + RS.score | `●` RS.section + RS.score（快照） | `◐` 只经 SC.snippet 露出正文，无 section/score |
| **M3 地理** | `●` 光点 lat/lon（`GET /api/landmarks/spots`） | `●` GEO（含 place/country/region） | `●` GEO（`as_card()` 同层给出） | `—` payload 无坐标；`SC.landmarkId` 是地标主键，不是地理值 |
| **M4 确信度** | `—` 光点只给坐标/热度，没有识别置信度 | `●` CF（卡片 payload 直接给出） | `●` CF（`as_card()` 同层给出） | `●` `SC.confidence`（与 photo 同层） |
| **M5 影像** | `◐` 地标百科图（非卡片 photo） | `●` PH（上传 URL 或地标图） | `●` PH | `●` `SC.photo`（与 confidence 同层） |
| **M6 身份与命名** | `◐` 地标 id/name，非卡片身份 | `●` ID（id/landmarkId/title/source） | `●` ID | `◐` `SC.id` + `SC.title` + `SC.landmarkId`，**缺 card `source`** |
| **M7 匿名性** | `—` 尚未投递，没有"作者"可言 | `●` ANON（投递控件 `narrative-deliver` 存在；投递后响应固定 `anonymous=true`） | `●` ANON（手账面板有"匿名投递"控件；投递响应同样剥离身份） | `●` ANON（响应值判定：payload 固定 `anonymous=true`） |
| **M8 单次拾取** | `—` 无拾取入口 | `●` PICK（地标层面板有 `narrative-pick` → `GET .../pick`：写入由"未拾取"过滤裁决，重复拾取不可见；**409 只经 `POST /api/narrative/fragments/{id}/pick`**，前端未接线） | `—` 手账面板没有拾取入口 | `●` PICK（响应值 + 唯一约束：同碎片第二次拾取在 POST 路径被 409 拒绝，GET 路径靠未拾取过滤） |
| **M9 投递额度** | `—` 无投递入口 | `●` QUOTA（地标层面板有"投递到此处"，额度在此结算） | `●` QUOTA（手账面板有"匿名投递"，额度在此结算） | `●` QUOTA（投递响应回报 `deliveredCount/remaining`） |
| **M10 时间刻度** | `—` 光点无时间戳 | `●` TS.createdAt（扩展字段） | `●` TS.addedAt（+ 卡片 createdAt） | `●` TS.fragment.createdAt |

**读法**：从左到右，格子由空到密——空间先"被点名"（M3/M5），再"被讲述"（M1/M2/M4/M6），
再"被沉淀"（journal 列几乎全满），最后"被陌生人接住"（M2/M6 降为部分值，M4/M5/M7/M8/M9/M10 直接承载）。
两处 **刻意留空** 是设计边界而不是数据缺失：
- M1/M3 在 fragment 通道留空——匿名碎片不给纪年、不给坐标（只给来源卡片的 `landmarkId` 主键）；
- M8 在 globe/journal 留空——拾取入口只在地标层面板里，globe 与 journal 没有拾取控件。

## 3. 机制切面（数据库级证据，供展板做"可信度"小图）

| 机制 | 实现 | 约束/取值 |
|---|---|---|
| 投递额度 | `narrative_service.fragment_limit()` | 同用户 × 同地标 ≤ 3（第 4 次 409，消息含额度；成功响应回报 `deliveredCount/remaining`） |
| 单次拾取 | `FragmentPickup.Meta.unique_together = (fragment, user)` | 第二次拾取 409（唯一约束 + 服务层显式拒绝）。注意：409 只经 `POST /api/narrative/fragments/{id}/pick` 触发；前端拾取走 `GET .../pick`，其可见拒绝形式是 404（不重复拾取） |
| 匿名 | `fragment_payload()` 固定 `anonymous=true`，无投递者键 | 响应体不可反查作者；库内 `delivered_by` 仅用于额度与自投排除 |
| 卡片只读 | `JournalCard` 无更新端点，仅 `POST /api/narrative/journal/cards` 追加 | 手账不提供改写 |

## 4. 切面 × 观感（供展板配图，均为结构描述，非史料结论）

| 切面 | 观感关键词 | 视觉承载建议 |
|---|---|---|
| M1 | 纵深：同一地点的多个年份锚点 | 竖向刻度尺，按 year 排布 |
| M2 | 距离：相关度决定"讲哪一句" | 由中心向外的亮度衰减 + 章节环带 |
| M3 | 定位：坐标把叙事钉在地球上 | 经纬网格 + 单一亮点 |
| M4 | 确信：系统敢不敢说"这是它" | 明度/透明度 = 置信度 |
| M5 | 物证：照片是唯一不可替换的输入 | 卡片主视觉位 |
| M6 | 命名：这张卡片叫什么、来自哪台引擎 | 卡片角标 |
| M7 | 隐身：叙事离开作者时作者消失 | 卡片背面留白/无署名 |
| M8 | 稀缺：一次只能被一个人接住 | 单一出口 + 一次性闸门 |
| M9 | 限额：同一个人不能把一处地点讲满 | 三个格子的进度条 |
| M10 | 沉淀：时间戳记录被续写的时刻 | 边缘时间戳条 |

## 5. 缺口与边界（诚实标注）

| 项 | 现状 | 处理 |
|---|---|---|
| 无纪年地标 | `timeFragments` 可能落到 `db:ts_landmark.intro`（`year=null`），或最终兜底为代码生成句 | 按"有无纪年"分色；兜底句标注 `source=db:ts_landmark`，不当史料 |
| 索引不可用 | `ragSnippets` 的 `section` 可能是 `intro` / `landmark`，`score` 为 `null` | 展板对 `score=null` 的格子不加亮度 |
| `RS.score` 量纲 | RRF 分数（理论上界 `2/61 = 0.032787`，快照实测最高 0.032787），非概率 | 只做相对排序，不写成"准确率" |
| 低置信度候选 | `low_confidence` / `candidates[]` 只存在于**识别响应**（`POST /api/recognition/recognize`），卡片 payload 不含 | 展板在"识别"侧单独标注，不画进卡片列 |
| 上传端点缺口 | 前端 `JournalEditWindow` 调 `/api/uploads/image`，后端当前未挂载该路由（升级前既有缺口） | `photo` 无上传 URL 时回退 `ts_landmark.image_url`；A4 如实说明，不在本轮修 |
| 文化解释 | 本矩阵不含解释性结论 | 由人完成最终措辞 |

## 6. 与卡片契约的逐字段对照

SPEC 必需字段（`fieldOrder`，9 个）在矩阵中的落点：

| SPEC 字段 | 矩阵行 | 说明 |
|---|---|---|
| `id` | M6 | 卡片身份（复合行） |
| `landmarkId` | M6 | 卡片身份（复合行，`as_card()` 中为独立键） |
| `photo` | M5 | 影像切面（两个来源） |
| `title` | M6 | 身份与命名 |
| `geo` | M3 | 地理切面 |
| `timeFragments` | M1 | 纪年切面（`section` 作为标签随行） |
| `ragSnippets` | M2 | 检索切面（`section` + `score` 一记录两标签） |
| `confidence` | M4 | 确信度切面 |
| `source` | M6 | 卡片来源（识别引擎名 / `landmark`） |

- 9 个必需字段全部有落点；字段名在 §0 缩写表与 §1「承载物」列中给出
  （`CF`=`confidence`、`PH`=`photo`、`GEO`=`geo` 等），可逐条对照快照 `fieldOrder`；
- `createdAt` 是**扩展字段**（`as_card()` 额外返回，快照 `extensionFields` 记录），
  仅用于 M10，且表中明确标注"扩展字段"，不冒充 SPEC 必需字段。

## 7. 层与前端落地的对应（避免把 API 载荷当成界面）

| 列 | 前端载体（文件存在，已在 e2e 中验证三层） | 状态值 | e2e 是否覆盖 |
|---|---|---|---|
| globe（layer） | `frontend/src/features/narrative/NarrativeHud.tsx` | `layer = "globe"` | 是（`narrative-layer-globe`） |
| landmark（layer） | `frontend/src/features/narrative/LandmarkNarrativePanel.tsx` | `layer = "landmark"` | 是（`narrative-layer-landmark`、`narrative-card-title`、`narrative-add-to-journal`） |
| journal（layer） | `frontend/src/features/narrative/JournalCardsPanel.tsx`；层头部（含 `narrative-back`）在 `NarrativeHud.tsx` | `layer = "journal"` | 是（`narrative-layer-journal`、`narrative-journal-card`） |
| fragment（**通道，非 layer**） | 地标层面板的"投递到此处/拾取碎片"与手账面板的"匿名投递"按钮（共用同一块面板，故 fragment 与 landmark 列在界面上有重叠） | 无独立 `layer` 值 | **否**——`narrative-deliver` / `narrative-pick` 目前只在组件中，S3 证据是 pytest（`tests/backend/test_s3_fragment_*.py`）+ 手动 curl |

- `e2e/narrative-journal.spec.ts` 的绿日志：`docs/competition/evidence/s1-e2e-green.log`（`1 passed`）；
  红日志：`s1-e2e-red.log`（实现前 HUD 不存在）。
- 叙事动线与层关系的完整图见 `docs/competition/A1-narrative-flow.md`。
- 技术可信度（置信度来源、低置信度拒答、单次拾取机制）见 `A4-technical-credibility.md`。
