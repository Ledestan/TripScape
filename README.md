# 行旅识景 TripScape

上传照片识别世界地标、RAG 智能问答、旅行手账与足迹图鉴的一站式应用。
识别结果返回百科图片与介绍；问答带会话上下文（低置信度会明确回答"不知道"）；
手账保存后自动生成足迹，公开手账可生成免登录分享链接。

主页是一颗全屏 3D 地球（react-three-fiber 渲染，不转动地球、由相机环绕）：

- **地球交互**——远看时地标按区域聚合成带国旗与计数的气泡，拉近自动散开成光点；
  悬停显示名称，点击飞过去并打开详情浮窗；搜索命中时目标高亮、其余变暗。
- **四角浮层**——左上：Logo 与灵动岛搜索框（地标/用户/手账三类，结果满 5 条出现"显示更多"进入全局搜索浮窗）；
  右上：昼夜切换与登录/头像菜单（个人主页、设置、管理后台）；
  左下：智能问答与通知中心（消息条，未读时拉长为预览条）；
  右下：Google-Earth 风格控件排（重置 / 方向角即纬度视角 / 分体式缩放 / 全屏）。
- **全部功能浮窗化**——登录注册、地标详情（评论/手账双 Tab）、手账编辑与查看、
  个人主页（足迹/手账/评论/收藏/徽章五 Tab）、他人公开主页、全局搜索、举报、
  管理后台（七个 Tab）均为叠加式小浮窗，无页面跳转。
- **视觉**——日间明亮 / 夜间深空蓝渐变 + 星空启动页；细边框 + 分层阴影表达层次；
  夜间图标与文字纯白。

## 技术栈

| 层 | 技术 |
| --- | --- |
| 后端 | Django 5.2 + Django Ninja（`/api/docs` 自动文档） |
| 数据库 | MySQL 8（Django ORM + migrations） |
| 异步 | Celery + Redis + Beat（识别 / 通知 / 审核 / 清理） |
| 识别 | DINOv2（全局特征）+ FAISS（向量检索），实测 93.9%，全本地零 API |
| 问答 | 地标文章（每地标一篇 markdown）分块 + bge-small-zh 向量 + BM25 双路检索 + RRF 融合 + 意图定向抽取 |
| 检索 | rank-bm25 混合；Meilisearch（全局搜索，可降级为 ORM） |
| 存储 | MinIO（可回退本地 `runtime/uploads/`） |
| 前端 | React 18 + Vite + TypeScript，Tailwind CSS + shadcn/ui 组件，Zustand 状态，TanStack Query，ECharts 图表，Sonner 提示，react-three-fiber 三维地球，PWA + 暗色模式 |
| 部署 | Docker Compose + Nginx + Gunicorn |
| 测试 | pytest-django（后端）/ Vitest（前端单元）/ Playwright（端到端） |

## 快速开始

```bash
pip install -r requirements.txt          # 后端依赖
copy .env.example .env                   # 环境配置（Windows）；macOS/Linux 用 cp
python scripts/reset_all.py              # 一键初始化：runtime + MySQL + 种子 + 识别/问答双索引
python backend/manage.py runserver       # http://127.0.0.1:8000

cd frontend                              # 前端（新终端）
pnpm install
pnpm build                               # 构建后由 Django 提供 SPA；开发用 pnpm dev
```

> **提示**：首次运行 reset_all 会下载 DINOv2 权重（84MB，走 hf-mirror 镜像），
> 之后缓存在用户目录不再下载；索引构建约 1 分钟。

一键重测：`python scripts/reset_all.py --with-frontend --with-tests`
（重置数据库 + 构建前端 + 跑后端测试）。

桌面应用（免命令行）：`python desktop.py`（pywebview 窗口内嵌 Django 服务）。

### 种子账号

| 账号 | 密码 | 角色 |
| --- | --- | --- |
| admin | admin123456 | 管理员（审核中心 / 地标管理 / 账号管理 / 举报处理 / 审计日志） |
| demo | demo123456 | 普通用户（演示用，含示例足迹与手账可自行创建） |

管理员功能全部在地球页右上角头像菜单的"管理后台"浮窗内，无独立后台页面。

## 目录结构

```text
TripScape/
├─ backend/                              # Django 后端工程
│  ├─ manage.py                          # 管理入口（runserver / makemigrations / init_tripscape）
│  ├─ config/                            # 工程配置包
│  │  ├─ settings/                       # base.py 公共 / dev.py 开发 / prod.py 生产
│  │  ├─ urls.py                         # 根路由（SPA、API、静态）
│  │  ├─ asgi.py / wsgi.py               # 部署入口
│  │  └─ celery.py                       # Celery 实例与定时任务装载
│  ├─ apps/                              # 业务应用（应用名 apps.<name>）
│  │  ├─ accounts/                       # 用户、注册登录、昵称签名、隐私开关、封禁/禁言字段
│  │  ├─ landmarks/                      # 地标、识别记录、收藏、问答上下文
│  │  ├─ comments/                       # 评论、评论举报（含点赞模型 models_like.py）
│  │  ├─ journals/                       # 手账（含二次编辑快照 pending_edit）、足迹、分享
│  │  ├─ badges/                         # 徽章定义与用户徽章
│  │  ├─ notifications/                  # 站内通知（回复/审核/徽章/点赞/账号）
│  │  ├─ shares/                         # 公开分享链接
│  │  ├─ search/                         # Meilisearch 索引配置
│  │  ├─ dashboard/                      # 运营看板聚合
│  │  ├─ admin_panel/                    # 审计日志 + 敏感词（应用 label 为 audit）
│  │  └─ core/                           # 认证鉴权、限流、中间件、初始化命令 init_tripscape
│  ├─ services/                          # 跨应用业务服务层
│  │  ├─ user_service.py                 # 注册/登录/个人主页聚合
│  │  ├─ recognition_service.py          # 图片识别（top-3 + 低置信度候选）
│  │  ├─ journal_service.py              # 手账创建/编辑（二次审核快照）/审核动作
│  │  ├─ comment_service.py              # 评论与敏感词检查
│  │  ├─ footprint_service.py            # 足迹聚合与重建（保留隐藏状态）
│  │  ├─ notification_service.py         # 通知发送
│  │  ├─ badge_service.py                # 徽章判定
│  │  ├─ search_service.py               # 全局搜索（Meilisearch 降级 ORM）
│  │  ├─ stats_service.py                # 看板统计
│  │  ├─ file_service.py                 # 上传（MinIO / 本地回退）
│  │  ├─ share_service.py                # 分享链接
│  │  └─ audit_service.py                # 审计日志
│  ├─ tasks/                             # Celery 异步任务
│  │  ├─ recognition_tasks.py            # 异步识别
│  │  ├─ maintenance_tasks.py            # 回收站清理、临时文件清理
│  │  └─ maintenance_tasks_dashboard.py  # 看板定时聚合
│  ├─ api/                               # Django Ninja 路由（每域一个文件）
│  │  ├─ __init__.py                     # NinjaAPI 聚合与挂载
│  │  ├─ auth.py                         # 注册/登录/个人主页/公开主页/隐私开关
│  │  ├─ landmarks.py                   # 地标
│  │  ├─ comments.py / likes.py          # 评论（含举报）/ 点赞
│  │  ├─ journals.py / shares.py         # 手账 / 分享
│  │  ├─ footprints.py / badges.py       # 足迹（含单点隐藏）/ 徽章
│  │  ├─ notifications.py                # 通知
│  │  ├─ search.py / qa.py / recognition.py   # 搜索 / 文章问答 / 图片识别
│  │  ├─ dashboard.py                   # 运营看板
│  │  ├─ admin.py                        # 管理后台（审核/举报/账号/审计/回收站）
│  │  └─ admin_landmarks.py              # 地标管理（路由挂 admin router）
│  └─ runtime/                           # 后端运行日志（正式 runtime 在仓库根）
├─ frontend/                             # React 前端工程
│  ├─ index.html                         # SPA 入口（含星空启动动画）
│  ├─ public/                            # earth.png 贴图、stars.jpg、manifest、landmarks/ 百科图
│  ├─ src/
│  │  ├─ main.tsx / App.tsx              # 入口与路由（全部功能浮窗化，旧网页路由重定向回地球）
│  │  ├─ api/                            # axios 客户端
│  │  ├─ components/                     # FloatingWindow 浮窗容器、LoadingScreen、ui/ 基础组件
│  │  ├─ features/                       # 按业务域组织
│  │  │  ├─ globe/                       # Globe.tsx 三维地球、GlobeControls 控件排、ElasticLandmarkCard 预览卡
│  │  │  ├─ qa/                          # MessageBar 消息条（问答 + 通知双 Tab）
│  │  │  ├─ search/                      # DynamicIslandSearch 灵动岛、SearchWindow 全局搜索浮窗
│  │  │  ├─ profile/                     # UserProfileWindow 他人公开主页（五 Tab）
│  │  │  ├─ comments/                    # ReportDialog 举报浮窗
│  │  │  └─ admin/                       # AdminPanelWindow 管理后台（七 Tab 大浮窗）
│  │  ├─ layouts/                        # FloatingDock 右上按钮组、LoginWindow、ProfileWindow、
│  │  │  │                               # JournalViewWindow（含点赞）、SettingsWindow
│  │  ├─ pages/                          # GlobeApp 主页、LandmarkDetail 详情、JournalEditWindow 编辑、Share 分享页
│  │  ├─ hooks/ stores/ styles/ types/ utils/
│  ├─ tests/frontend/                    # Vitest 单元测试
│  ├─ e2e/                               # Playwright 端到端
│  └─ vite.config.ts / tailwind.config.js / tsconfig.json / package.json
├─ runtime/                              # 运行时目录（uploads/cache/logs/tmp + index/ 索引产物）
├─ data/                                 # 精选注册图（26 类 × 15 张，约 75MB，git 不入库随发布包分发）
├─ models/                               # bge-small-zh 向量模型（约 92MB，git 不入库随发布包分发）
├─ scripts/
│  ├─ reset_all.py                       # 一键重置重测（runtime + MySQL + 种子 + 双索引，可选前端与测试）
│  ├─ register_landmarks.py              # 识别索引构建（注册图 → DINOv2 → FAISS，幂等）
│  ├─ build_qa_index.py                  # 问答索引构建
│  └─ db/                                # 全部种子数据（新增数据只改文件、不改代码）
│     ├─ seed_landmarks.sql              #   地标（26 个：名称/地区/国家/经纬度/百科）
│     ├─ seed_badges.sql                 #   徽章（10 枚成就定义）
│     ├─ seed_sensitive_words.sql        #   敏感词基线（运行期可在后台增删）
│     ├─ register_images.json            #   识别注册图清单（指纹缓存，可手工增删）
│     └─ articles/                       #   地标文章库（每地标一篇章节式 markdown）
├─ tests/backend/                        # pytest-django 后端测试
├─ docker/                               # Dockerfile.backend / Dockerfile.frontend、nginx.conf、mysql/my.cnf
├─ desktop.py                            # 桌面应用入口（pywebview）
├─ docker-compose.yml                    # Web/Celery/Beat/MySQL/Redis/Meilisearch/MinIO/Nginx/备份
├─ .env.example / .gitignore / LICENSE / requirements.txt / pytest.ini
└─ README.md
```

## 数据库表（MySQL `tripscape`，业务表统一 `ts_` 前缀、蛇形命名）

| 表 | 用途 |
| --- | --- |
| ts_user | 用户（昵称/签名/隐私开关/封禁/禁言/限登） |
| ts_landmark | 地标（名称/地区/国家/经纬度/百科/热度/上下架） |
| ts_journal / ts_journal_image | 手账（含二次编辑快照）与配图 |
| ts_footprint | 足迹（手账自动聚合，含单点隐藏） |
| ts_comment | 评论（软删除） |
| ts_like | 点赞（手账/评论通用） |
| ts_favorite | 地标收藏 |
| ts_report | 举报（待处理/已下架/仅标记/已驳回四态） |
| ts_notification | 站内通知（回复/审核/徽章/点赞/账号） |
| ts_share_link | 手账公开分享链接 |
| ts_badge / ts_user_badge | 徽章定义与用户获得记录 |
| ts_recognition | 识别记录（看板统计） |
| ts_qa_context | 问答会话历史 |
| ts_sensitive_word / ts_audit_log | 敏感词 / 管理审计日志 |

> 框架表（auth_* / django_*）由 Django 维护，不手工操作。

## API 概览

文档自动生成：`/api/docs`。认证：`Authorization: Bearer <token>`。

| 方法 | 路径 | 说明 | 权限 |
| --- | --- | --- | --- |
| POST | /api/auth/register · /api/auth/login · /api/auth/profile(PUT) | 注册 / 登录 / 改资料 | 匿名/登录 |
| GET | /api/auth/{id}/public | 用户公开主页（按隐私开关过滤） | 匿名 |
| PUT | /api/auth/privacy | 隐私开关（足迹/手账/评论/收藏/徽章） | 登录 |
| GET/POST | /api/admin/review/* | 审核中心（评论/手账，含风险预检） | 管理员 |
| CRUD | /api/admin/landmarks | 地标管理（增删改/上下架） | 管理员 |
| POST | /api/admin/users/{id}/account | 封禁/禁言/限制登录（可设时长） | 管理员 |
| GET/POST | /api/admin/reports · /{id}/handle | 举报处理（下架/仅标记/驳回/重开） | 管理员 |
| GET | /api/admin/audit-logs(/export) | 审计日志（筛选/导出 CSV） | 管理员 |
| GET/POST | /api/admin/trash(/restore/purge) | 回收站（软删除恢复/清理） | 管理员 |
| POST | /api/qa/chat | 问答（上下文 + 低置信度不知道） | 匿名 |
| POST | /api/recognition/recognize | 图片识别（top-3 + 候选） | 登录 |
| GET | /api/landmarks/spots · /{id} | 地球光点 / 详情（百科） | 匿名 |
| CRUD | /api/comments · /journals · /likes | 评论 / 手账（二次编辑审核）/ 点赞 | 登录 |
| POST | /api/journals/{id}/share + GET /api/shares/{token} | 分享链接 / 免登录查看 | 作者/匿名 |
| GET/POST | /api/footprints/mine · /{id}/visibility | 足迹 / 单点隐藏 | 登录 |
| GET | /api/search/ | 全局搜索（地标/用户/手账） | 匿名 |
| GET | /api/dashboard/stats | 运营看板 | 管理员 |
| GET | /healthz · /readyz | 存活 / 就绪探针 | 匿名 |

## 权限矩阵

| 功能 | 匿名 | 登录用户 | 管理员 |
| --- | :-: | :-: | :-: |
| 浏览 / 问答 / 识别 / 搜索 / 分享查看 / 公开主页 | ✓ | ✓ | ✓ |
| 评论 / 手账 / 收藏 / 点赞 | – | ✓ | ✓ |
| 审核中心（隐藏/恢复/通过/驳回，删除进回收站） | – | – | ✓ |
| 地标管理 / 账号管理 / 举报处理 / 审计日志 | – | – | ✓ |

## Docker 部署

```bash
docker compose up -d --build
docker compose exec web sh -c "cd /app/backend && python manage.py init_tripscape"
# 应用 http://localhost   文档 http://localhost/api/docs
```

编排服务：Web、Celery、Celery Beat、MySQL（慢查询日志 + my.cnf）、Redis、
Meilisearch、MinIO、Nginx、每日备份（MySQL dump，保留 7 天）。

## 测试

```bash
pytest                                  # 后端（tests/backend）
cd frontend && npx vitest run           # 前端单元（tests/frontend）
cd frontend && npx playwright test      # 端到端（e2e/，先启动后端并 pnpm build）
```

## 运维要点

- **日志**：`runtime/logs/tripscape.log`（RotatingFileHandler 10MB×5）+ 请求中间件（request_id / 耗时）
- **健康检查**：`/healthz` `/readyz` + compose healthcheck
- **定时任务**：03:00 清理 runtime/tmp 与回收站；每小时看板聚合
- **备份**：`runtime/backups/`（每日，保留 7 天）
- **__pycache__ 根除**：虚拟环境 `site-packages/sitecustomize.py` 全局禁用字节码写入，
  `scripts/reset_all.py` 会自愈重建该文件

## 识别引擎（检索式）

采用 **DINOv2 全局检索** 的以图搜图管线（`backend/services/retrieval_engine.py`）：

```
离线注册：地标注册图 → DINOv2 全局特征（384 维）→ FAISS 索引 + 元数据
查询识别：查询图 → DINOv2 特征 → FAISS 检索 top-k 候选
            → 按地标去重取最优 → 地标名 + 置信度
```

- **加新地标零训练**——注册图放 `data/<类名>/`，跑
  `python scripts/register_landmarks.py` 重建索引。
- **实测**：26 类 / 3065 张验证集 Top-1 **93.9%**，CPU 平均 64ms/图。
- **全本地运行，零 API 费用**——DINOv2 ViT-S/14（85 MB，torch.hub 自动下载）、
  FAISS（纯库）。
- **索引幂等可恢复**——注册图清单带内容指纹，未变化时直接复用旧索引；
  `--force-rebuild` 强制重建；索引与元数据不一致时启动报错提示重建。
- 索引不存在时识别接口返回失败与重建指引（`python scripts/register_landmarks.py`）。

## 问答引擎（文章式 RAG）

以 **"每地标一篇章节式文章"** 为知识源（`backend/services/article_qa.py`）：

```
离线建库：地标文章（scripts/db/articles/*.md）
            → 按章节分块（元数据：地标 / 标题 / 章节 / Chunk ID）
            → bge-small-zh 向量索引 + BM25 索引（同一 Chunk ID 关联）

在线问答：用户查询 → 主题提取（地标词典最长匹配，支持多主题比较）
            → 意图切分（疑问词边界：多高 / 何时 / 门票…→ 章节标签）
            → 定向检索（主题锁文章 + 意图锁章节）→ 向量 + BM25 → RRF 融合
            → 句子级打分抽取 → 按主题聚合答案 + 来源标注
            → 逐子项拒答（"文章未提及"）/ 整体拒答（"知识库中没有相关信息"）
```

- **文章即数据**——`scripts/db/articles/` 每地标一篇 markdown
  （YAML 元数据 + 概述/基本参数/历史沿革/地理位置/参观信息章节），
  手工编辑后运行 `build_qa_index.py` 重建索引。
- **复合问题**——"埃菲尔铁塔多高、什么时候建的"按疑问词边界拆分逐项作答
  （顿号 / 问号 / 分号均识别），答不出的子项明示"文章未提及"。
- **零幻觉**——答案全部来自原文句子抽取，来源标注为文章章节，比生成式更可靠。
- 索引构建：`python scripts/build_qa_index.py`（文章指纹变化自动重建）；
  索引不可用时返回重建指引。

## 数据说明

- `data/`：注册图（26 类 × 15 张），git 不入库，发布包需携带。
- `models/`：bge-small-zh 向量模型（约 92MB），同上。
- `scripts/db/`：种子数据（地标/徽章/敏感词 SQL、文章库 markdown），
  `reset_all.py` 一键导入。

## 许可

Apache License 2.0，作者 Tingchu，详见 [LICENSE](LICENSE)。
