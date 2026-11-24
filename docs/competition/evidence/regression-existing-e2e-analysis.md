# 既有 e2e 套件的失败分析（regression-existing-e2e.log 附注）

> 这是 Agent 的**分析记录**，不是 Playwright 输出的原文；原始输出见
> `docs/competition/evidence/regression-existing-e2e.log`（`3 passed, 4 failed`）。

## 1. 失败用例与原因（全部为选择器失效，不是行为回归）

| 失败用例 | Playwright 等待失败的定位器 | 该定位器在当前前端源码中是否存在 |
|---|---|---|
| 进入 app 页：5 秒加载动画 → 3D 地球 → 搜索 → 消息条 | `button[title="展开智能问答"]` | **0 处**（`frontend/src` 全量搜索无命中） |
| 灵动岛搜索：点击展开 → 回车搜索 → 结果浮窗 | `getByPlaceholder("搜索地标、手账、评论、用户…")` | **0 处** |
| demo 账号登录成功 | `getByPlaceholder("demo")` / `getByPlaceholder("••••••")` | **0 处**（`LoginWindow.tsx` 的 placeholder 为「用户名（英文/数字/下划线）」「密码（≥6位，含字母和数字）」） |
| 管理后台登录入口 | `getByText("管理员登录")` | **0 处** |

## 2. 为什么判定为"升级前既有"，而不是本轮引入

1. 上述四个组件（`MessageBar.tsx`、`DynamicIslandSearch.tsx`、`LoginWindow.tsx`、
   管理后台浮窗）在本轮 `git diff main..HEAD` 中**均未被修改**
   （`git diff --name-only main..HEAD | grep -E 'MessageBar|DynamicIslandSearch|LoginWindow|AdminPanel|SearchWindow'` 无输出）。
2. 失败原因是"页面上不存在该元素"，不是"点击/断言流程被打断"；
   本轮新增的叙事层 HUD 只在 `tripScape2` 开启时渲染，且位于底部中央，
   没有覆盖上述四个定位器所在的区域（登录浮窗、灵动岛、管理后台登录页）。
3. 同一套件中仍然通过的 3 个用例（`登录页可达`、`无效分享链接`、`搜索页可达`）
   说明站点本身可访问、SPA 可加载。

## 3. 本轮的处理与边界

- SPEC §5 明确禁止修改/删除 `e2e/` 下已存在的测试文件来"适配"实现，
  因此**没有修正这 4 个失效选择器**，也没有跳过它们；
- 本轮新增的证据测试放在仓库根 `e2e/`（`narrative-journal.spec.ts`），
  与既有套件互不影响（两个独立的 Playwright 配置文件）；
- 结论：既有 e2e 的 4 个失败是**升级前已存在的测试漂移**，
  本轮不把它算作回归，也不把它算作通过项；`STOP.md` 会如实列出。
