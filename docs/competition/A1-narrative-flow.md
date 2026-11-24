# A1 叙事动线图（Narrative Flow）

> 命题：**让每一张旅行照片，成为一次可被陌生人续写的空间叙事。**
> 本图只画代码里真实存在的节点与边；每个节点标注组件/路由/端点/表，每条边标注触发函数。
> 不含任何文化解释与虚构页面（文化内容最终解释权归人）。

## 1. 动线总览（30 秒版）

```
globe（未被讲述） → 点地标 → landmark（正在被讲述：卡片切面）
      → 加入手账 → journal（已沉淀：只读快照）
      → 匿名投递 → 某个地标的碎片池 → 陌生人进入同一地标 → 拾取（来源卡片摘要）
```

四个格子不是四个页面，而是**同一张照片被讲述的四个时间尺度**。

## 2. 动线图（Mermaid，可直接渲染为展板骨架）

```mermaid
flowchart LR
  subgraph GLOBE["① globe · 尚未被讲述的空间"]
    N1["地球层叙事轨道<br/>NarrativeHud · layer=globe<br/>testid: narrative-layer-globe"]
    N2["地标光点清单<br/>GET /api/landmarks/spots<br/>26 个种子地标"]
  end

  subgraph LANDMARK["② landmark · 正在被讲述的地点"]
    N3["地标层叙事轨道<br/>NarrativeHud · layer=landmark<br/>testid: narrative-layer-landmark"]
    N4["叙事卡片（只读对象）<br/>GET /api/narrative/card/{id}<br/>9 字段 + createdAt"]
    N5["卡片组装<br/>build_narrative_card()<br/>timeFragments / ragSnippets / geo"]
  end

  subgraph JOURNAL["③ journal · 已被沉淀的个人叙事"]
    N7["手账层叙事轨道<br/>NarrativeHud · layer=journal<br/>testid: narrative-layer-journal"]
    N6["加入手账（只读快照）<br/>POST /api/narrative/journal/cards<br/>ts_narrative_journal_card"]
    N8["刷新后取回<br/>GET /api/narrative/journal"]
  end

  subgraph STRANGER["④ fragment · 叙事在陌生人之间流动"]
    N9["匿名投递<br/>POST /api/narrative/fragments<br/>ts_narrative_fragment（同地标 ≤3）"]
    N10["另一个人的地标层<br/>同一 layer=landmark"]
    N11["拾取一条碎片<br/>GET /api/narrative/fragments/pick<br/>ts_narrative_fragment_pickup（唯一）"]
  end

  N12["识别入口（既有）<br/>POST /api/recognition/recognize<br/>tripScape2 开启时并入卡片字段"]
  N13["既有地标详情（旁路，不改动）<br/>/landmarks/:id → LandmarkDetailWindow"]

  N2 --> N1
  N1 -->|"点击地标入口<br/>enterLandmark()"| N3
  N3 -->|"进入即取卡片"| N4
  N5 --> N4
  N12 -->|"识别成功<br/>_attach_narrative_card()"| N5
  N3 -->|"加入手账<br/>addToJournal.mutate()"| N6
  N6 --> N7
  N7 -->|"刷新页面"| N8
  N8 --> N7
  N7 -->|"匿名投递<br/>deliver.mutate()"| N9
  N9 -->|"他人的拾取池"| N10
  N10 -->|"拾取碎片<br/>pick.mutate()"| N11
  N11 -->|"来源卡片摘要回落地标层"| N3
  N3 -->|"返回<br/>back()"| N1
  N13 -.->|"旁路：独立入口"| N3
```

## 3. 节点表（每个节点都可追溯）

| 节点 | 名称 | 类型 | 追溯路径 |
|---|---|---|---|
| N1 | 地球层叙事轨道 | 组件 | `frontend/src/features/narrative/NarrativeHud.tsx`（`layer==="globe"`，`data-testid="narrative-layer-globe"`） |
| N2 | 地标光点清单 | API | `GET /api/landmarks/spots` → `backend/api/landmarks.py::spots` |
| N3 | 地标层叙事轨道 | 组件 | `NarrativeHud.tsx` + `LandmarkNarrativePanel.tsx`（`layer==="landmark"`） |
| N4 | 叙事卡片 | API + 模型 | `GET /api/narrative/card/{landmark_id}` → `backend/api/narrative.py::get_card` → `NarrativeCard.as_card()`（`backend/apps/narrative/models.py`） |
| N5 | 卡片组装 | 服务 | `backend/services/narrative_service.py::build_narrative_card`（`_time_fragments` / `_rag_snippets` / `_geo`） |
| N6 | 加入手账 | API + 表 | `POST /api/narrative/journal/cards` → `narrative.py::add_card` → `ts_narrative_journal_card`（`unique_together=(user,card)`） |
| N7 | 手账层叙事轨道 | 组件 | `JournalCardsPanel.tsx`（`data-testid="narrative-layer-journal"`） |
| N8 | 刷新后取回 | API | `GET /api/narrative/journal` → `narrative.py::my_journal` → `narrative_service.journal_cards()` |
| N9 | 匿名投递 | API + 表 | `POST /api/narrative/fragments` → `narrative.py::deliver` → `NarrativeFragment`；额度 `fragment_limit()` |
| N10 | 另一个人的地标层 | 组件（同一状态机） | `NarrativeHud.tsx`（`layer==="landmark"`，另一会话） |
| N11 | 拾取 | API + 表 | `GET /api/narrative/fragments/pick` → `narrative.py::pick` → `FragmentPickup`（`unique_together=(fragment,user)`）+ `fragment_payload()` |
| N12 | 识别入口（既有） | API | `POST /api/recognition/recognize` → `backend/api/recognition.py::recognize_sync` → `_attach_narrative_card()` |
| N13 | 既有地标详情（旁路） | 路由 + 组件 | `/landmarks/:id`（`frontend/src/App.tsx`）→ `GlobeApp` → `LandmarkDetailWindow`（`frontend/src/pages/LandmarkDetail.tsx`） |

## 4. 边表（每条边都有触发点）

| 边 | 用户动作 | 触发代码 | 数据落点 |
|---|---|---|---|
| N2→N1 | 打开地球页 | `useQuery(["landmarks","spots"])`（`NarrativeHud.tsx`） | 内存（光点清单） |
| N1→N3 | 点击地标入口 | `data-testid="narrative-landmark-entry"` → `useNarrativeStore.enterLandmark()` | 前端状态 `layer=landmark` |
| N3→N4 | 进入地标层 | `useQuery(["narrative","card",id])` | `ts_narrative_card`（无则现建） |
| N5→N4 | 卡片组装 | `build_narrative_card()` | `ts_narrative_card`（timeFragments/ragSnippets/geo） |
| N12→N5 | 识别成功 | `_attach_narrative_card()`（`api/recognition.py`） | 同上 + 识别响应字段 |
| N3→N6 | 点"加入手账" | `addToJournal.mutate()` → `POST /api/narrative/journal/cards` | `ts_narrative_journal_card` |
| N6→N7 | 手账计数刷新 | `invalidateQueries(["narrative","journal"])` + `showJournal()` | 前端状态 `layer=journal` |
| N7→N8 | **刷新页面** | `useQuery(["narrative","journal"])` 重新拉取 | 服务端 `ts_narrative_journal_card` |
| N7→N9 | 点"匿名投递" | `deliver.mutate()` → `POST /api/narrative/fragments` | `ts_narrative_fragment` |
| N9→N10 | 他人进入同一地标 | 拾取池按 `landmark_id` 过滤 | `ts_narrative_fragment` |
| N10→N11 | 点"拾取碎片" | `pick.mutate()` → `GET .../pick?landmark_id=` | `ts_narrative_fragment_pickup` |
| N11→N3 | 拾取结果展示 | `picked` 状态 → `data-testid="narrative-picked-fragment"` | 内存（来源卡片摘要） |
| N3→N1 | 点"返回" | `back()`（`stores/narrative.ts`） | 前端状态回退 |
| N13⇢N3 | 打开既有详情后进入叙事层（旁路） | `/landmarks/:id` 路由 | 不写库（只读背景） |

## 5. 这张图提出的结构关系（代码里不存在、需要被画出来的部分）

1. **同一 URL 上叠着三层**：`/` 这一个路由里，`globe / landmark / journal` 是 `useNarrativeStore`
   的三个状态值，不是三个页面。图上的横向移动在浏览器里是**零跳转**的。
2. **刷新会重置视点，但不会重置内容**：`layer` 回到 `globe`，而 `ts_narrative_journal_card`
   里的卡片仍在（N8 边），这是"叙事沉淀"与"界面状态"的分离。
3. **两种"来源"合流到同一张卡片**：识别（N12）与地标现建（N4）都落到 N5，
   因此卡片既可以来自一张照片，也可以来自一次"我先看看这里有什么"。
4. **碎片是卡片的剪影而不是副本**：N9 只记录 `card_id`，N11 返回 `sourceCard` 摘要，
   原始卡片不被复制、投递者身份不进入响应（匿名边不可反向追踪）。
5. **额度与唯一性是两个不同层级的闸门**：额度在"投递"（N9，同地标 ≤3），
   唯一性在"拾取"（N11，同碎片 ≤1）；图上它们分居两格，不能画在一条边上。

## 6. 证据（动线是否真的走得通）

| 证据 | 路径 | 结论 |
|---|---|---|
| S1 e2e 绿 | `e2e/narrative-journal.spec.ts` → `docs/competition/evidence/s1-e2e-green.log` | globe→landmark→journal→刷新仍在→逐层返回 |
| S1 截图 | `docs/competition/evidence/s1-journal-{before,after}-refresh.png` | 刷新前后卡片一致 |
| S3 投递/拾取 | `tests/backend/test_s3_fragment_{delivery,pickup}.py` → `s3-functional-green.log` | 第 4 次 409 / 二次拾取 409 / 摘要字段 |
| S3 手动 | `docs/competition/evidence/s3-manual-curl.log` | 真实 HTTP 200/409 序列 |

## 7. 本图不包含什么

- 不含评论、审核、徽章、后台看板（属 §2 之外模块，本轮不改动）；
- 不含任何文化解释性文案（卡片文字来自文章库真实句，解释权归人）；
- 不把 N13（既有地标详情）画成叙事层的一部分——它只是旁路入口。
