# 开关关闭（tripScape2=false）时的负向对照证据
# 采集方式：以 DB_ENGINE=sqlite、TRIPSCAPE2_ENABLED=false 启动同一份 dist 与后端，再执行两类检查。

## 1. Playwright 证据测试在开关关闭时拒绝运行（先断言开关为真）
见 docs/competition/evidence/s1-flag-off-negative-control.log：
  1) ..\e2e\narrative-journal.spec.ts:23:48 › expect((await features.json()).tripScape2).toBe(true)
  1 failed

## 2. 浏览器级检查（同一份 dist，开关关闭）

实测输出（`node runtime\tmp\flag_off_ui_check.cjs`，Playwright Chromium）：

```json
{"hud":0,"globeLayer":0,"features":{"tripScape2":false,"version":"2.0.0"},"cardStatus":404}
```

## 3. 匿名请求的状态码分层（同一份关闭态构建，2026-11-25 实测）

```
$ curl -sS http://127.0.0.1:8000/api/features
{"tripScape2": false, "version": "2.0.0"}

$ curl -i http://127.0.0.1:8000/api/narrative/card/8
HTTP/1.1 404
{"detail": "TripScape 2.0 叙事层未开启（tripScape2=false）"}

$ curl -i -X POST http://127.0.0.1:8000/api/narrative/journal/cards \
       -H 'Content-Type: application/json' -d '{"card_id":1}'
HTTP/1.1 401
{"detail": "Unauthorized"}

$ curl -i 'http://127.0.0.1:8000/api/narrative/fragments/pick?landmark_id=8'
HTTP/1.1 401
{"detail": "Unauthorized"}
```

判读：`get_card` 用 `OptionalAuth`（匿名放行），所以匿名也直接走到 `_gate()` → **404**；
其余五个叙事端点的 `@login_required` 在 router 装饰器内层、**先于** `_gate()`，
因此匿名调用得到 **401**；带有效 token 时才会走到 `_gate()` → **404**。

字段含义：
  hud        = 页面中 data-testid="narrative-hud" 的数量（0 = 叙事层未渲染）
  globeLayer = data-testid="narrative-layer-globe" 的数量
  features   = GET /api/features 的返回（tripScape2=false）
  cardStatus = GET /api/narrative/card/8 的 HTTP 状态（404 = 叙事端点被门控）

结论：开关关闭时，同一份前端产物不渲染叙事层，叙事 API 返回 404；默认行为保持在 1.0。
