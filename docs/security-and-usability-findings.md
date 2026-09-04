# 普通用户测试漏洞登记

> **整改状态（2026-09-04）**：#2/#3/#4/#5/#7 已修复上线并实测验证；
> #6 已修复输入约束+限流（多实例部署需升级 Redis 限流）；
> #8/#11/#14/#16 已修复；#9 由 pnpm-workspace.yaml 的 onlyBuiltDependencies 覆盖；
> #1（HTTPS）/F1/F2 待运维侧操作（见 TODO F5）；#10/#12/#13/#15 及 N 组遗留为打磨项。

## 测试方式
- 以普通用户视角检查首页、导购输入、推荐结果、对比、反馈、历史会话和构建/启动链路
- 结合源码、冒烟脚本和前端构建结果做黑盒+灰盒验证
- 线上地址：`http://1.13.255.225/`
- 测试边界：只做非破坏性验证；未猜测、爆破或绕过 `API_TOKEN`；注册了临时测试账号验证普通用户登录链路

## 发现的问题

### 1. 线上站点未启用 HTTPS，登录态和访问令牌存在明文传输风险
- 严重级别：高
- 现象：`http://1.13.255.225/` 可直接访问；`https://1.13.255.225/` 的 443 端口未开放。前端会把 JWT 和 `API_TOKEN` 存入 `localStorage`，并通过请求头发送给后端。
- 影响：普通用户在公网环境访问时，登录 JWT、共享访问令牌和导购请求内容都可能被链路侧截获；一旦 `API_TOKEN` 泄露，导购接口和历史会话接口会被滥用。
- 证据：线上 `curl -I http://1.13.255.225/` 返回 `200 OK`；`curl -k -I https://1.13.255.225/` 无法连接 443；`frontend/src/lib/agentApiShared.ts` 中 JWT 和 `API_TOKEN` 存储在 `localStorage` 并随请求头发送。
- 建议：上线前必须配置 HTTPS 证书和 80 -> 443 强制跳转；增加 `Strict-Transport-Security`；避免在前端暴露共享 `API_TOKEN`，C 端登录态建议使用服务端可控的用户 JWT/Session。

### 2. 普通用户注册/登录后仍无法使用核心导购功能
- 严重级别：高
- 现象：线上注册接口可正常返回 JWT，但只携带 `Authorization: Bearer <JWT>` 调用 `/api/shopping/query` 和 `/api/shopping/sessions` 仍返回 `401 Invalid API token`。
- 影响：普通用户会认为“登录成功但产品不可用”，首屏热门问题和导购输入框都无法完成第一次体验；这会直接阻断 C 端 MVP 验证。
- 证据：线上临时测试账号注册成功；随后用登录 JWT 请求导购问答和历史会话接口，均返回 `401 Unauthorized`。源码中导购路由只依赖 `require_api_token` 校验 `X-API-Token`，没有使用 `verify_token` 从 JWT 解析用户身份。
- 建议：明确鉴权策略。C 端接口应以用户 JWT/Session 为准，共享 `API_TOKEN` 只用于服务间调用或运维保护；前端遇到 401 时应区分“未登录/令牌错误/服务不可用”。

### 3. 共享 API Token 与用户会话隔离不匹配，存在历史会话泄露风险
- 严重级别：高
- 现象：导购会话列表接口按 `X-User-Id` 过滤，但前端 `authHeaders()` 只发送 `X-API-Token` 和 `Authorization`，不会发送 `X-User-Id`。后端在 `user_id` 为空时不追加用户过滤条件。
- 影响：一旦用户配置了共享 `API_TOKEN`，`GET /api/shopping/sessions` 可能返回所有未删除历史会话；普通用户之间的咨询历史、预算、送礼对象、母婴等偏隐私需求会互相可见。
- 证据：`frontend/src/lib/agentApiShared.ts` 未设置 `X-User-Id`；`app/api/routers/shopping_router.py` 将可选请求头 `x_user_id` 传给 `list_sessions`；`app/repositories/mysql/meta/shopping_repositories.py` 只有 `user_id` 非空才按用户过滤。
- 建议：后端从 JWT 中解析 `user_id`，禁止信任客户端自传 `X-User-Id`；会话列表默认必须带用户条件；无用户身份时不要返回任何私人会话。

### 4. 会话详情和删除接口未做用户归属校验，存在 IDOR 越权风险
- 严重级别：高
- 现象：`GET /api/shopping/sessions/{session_id}` 和 `DELETE /api/shopping/sessions/{session_id}` 只按 `session_id` 查询/删除，没有校验当前登录用户是否拥有该会话。
- 影响：持有有效共享令牌的用户如果获得或猜到他人的 `session_id`，可能读取他人完整咨询消息，甚至删除他人会话。由于会话 ID 会在 SSE 和历史列表中出现，泄露面不只来自暴力猜测。
- 证据：`shopping_session_detail()` 调用 `get_session_messages(session_id)`；`delete_shopping_session()` 调用 `delete_session(session_id)`；仓储查询条件均未包含 `user_id`。
- 建议：详情、删除、继续追问、反馈、埋点都必须校验 `session_id + user_id` 归属；删除接口建议返回统一 404，避免暴露他人会话是否存在。

### 5. 导购查询允许客户端指定任意 `session_id`，可能串改他人会话上下文
- 严重级别：高
- 现象：`POST /api/shopping/query` 接收前端传入的 `session_id`，`ensure_session()` 在会话已存在时直接刷新 `last_query`，没有检查创建者或归属。
- 影响：持有有效共享令牌的用户可以向他人会话追加咨询内容，污染历史、推荐结果和埋点；这会破坏个性化推荐和用户隐私。
- 证据：`ShoppingQuerySchema.session_id` 可选但无归属校验；`ShoppingAgentService.query()` 使用传入的 `session_id`；`ensure_session()` 仅按 `session_id` 查询，命中后直接更新。
- 建议：服务端创建并绑定会话；继续会话时必须校验会话归属；不允许客户端把任意 ID 绑定到当前请求。

### 6. 查询、历史和行为埋点缺少资源型输入限制与限流
- 严重级别：中
- 现象：`ShoppingQuerySchema.query` 没有长度限制；`history` 是无结构的 `list[dict]` 且无条数/字段长度限制；`selected_product_ids` 无长度限制；`event_data` 是无边界 `dict`。登录和导购接口未见限流、配额、验证码或重试退避。
- 影响：恶意或异常客户端可提交超长 query、超大 history 或高频请求，造成 LLM/Embedding 成本上升、后端内存压力、SSE 连接占用和日志膨胀。
- 证据：`app/api/routers/shopping_router.py` 的 Pydantic Schema 对 query/history/selected_product_ids/event_data 缺少 max/min 约束；连续多次错误登录均返回 401，未出现锁定或限速提示；源码未检索到限流逻辑。
- 建议：增加 query 长度、history 条数、单条 content 长度、selected_product_ids 数量、event_data 大小限制；按用户/IP/API Token 做登录和导购限流；LLM 调用增加单用户日配额与并发控制。

### 7. 反馈与埋点接口未校验 session/message/product 关系
- 严重级别：中
- 现象：`/api/shopping/feedback` 和 `/api/shopping/events` 直接保存客户端传入的 `session_id`、`message_id`、`product_id`，未校验是否属于当前用户、当前会话和实际推荐结果。
- 影响：反馈数据可被伪造或污染，后续推荐优化、商品质量回流和埋点分析会失真；如果未来接入运营看板，可能导致错误决策。
- 证据：`shopping_feedback()` 直接调用 `save_feedback()`；`shopping_event()` 直接调用 `save_event()`；仓储层只新增记录，不查验关联数据。
- 建议：校验 `session_id/message_id/product_id` 的存在性和归属；只允许对当前用户实际看到的推荐结果反馈；埋点做事件类型白名单。

### 8. 前端对 401 的错误提示不准确
- 严重级别：中
- 现象：未配置 `API_TOKEN` 或只登录 JWT 后点击热门问题，页面显示“无法连接导购接口。导购接口请求失败：HTTP 401”，没有提示用户需要访问令牌或当前账号无法使用导购。
- 影响：普通用户会把鉴权问题理解成系统故障，不知道下一步该登录、配置令牌还是联系管理员。
- 证据：线上点击热门问题返回 401；`frontend/src/lib/shoppingApi.ts` 对 SSE 非 2xx 统一抛出 `导购接口请求失败：HTTP ${status}`；`frontend/src/App.tsx` 统一展示“无法连接导购接口”。
- 建议：前端按状态码拆分错误。401 显示“当前账号暂无导购权限/访问令牌无效”，403 显示“无权限”，5xx 才提示服务异常；首页在不可用状态下显式展示登录/授权入口。

### 9. 前端在非交互环境下构建失败
- 严重级别：高
- 现象：`pnpm build` / `CI=true pnpm build` 会触发 pnpm 对 `node_modules` 的清理或构建脚本审批，当前环境会直接失败
- 影响：普通用户虽然不直接感知，但开发/部署流水线会卡住，前端改版无法稳定交付
- 证据：`frontend/package.json`、构建命令输出中的 `ERR_PNPM_ABORTED_REMOVE_MODULES_DIR_NO_TTY` 和 `ERR_PNPM_IGNORED_BUILDS`
- 建议：补齐 pnpm 的无交互构建配置，或固定安装策略，避免 CI/无 TTY 环境失败

### 10. 接口 schema 文档与实际实现不完全一致
- 严重级别：中
- 现象：PRD/接口文档写了较完整的 `/api/shopping/*` 结构，但实际路由中一些请求结构仍以 `dict` 或松散字段承载；前端与后端字段对接存在漂移风险
- 影响：普通用户会遇到“能点但结果缺字段/样式异常/追问失效”
- 证据：`app/api/routers/shopping_router.py`、`frontend/src/types/shopping.ts`、`docs/PRD-ai-shopping-decision-assistant-interfaces.md`
- 建议：统一请求/响应 DTO，接口字段做契约测试

### 11. 用户路径对“继续追问”容错不够直观
- 严重级别：中
- 现象：当用户输入“跳过/不知道/不确定”类内容时，虽然后端做了部分恢复逻辑，但前端没有明显解释当前状态是否已继续沿用上文
- 影响：普通用户容易以为系统没理解，重复提交或中断
- 证据：`app/agent/shopping/nodes/rewrite_question.py`
- 建议：前端明确展示“已沿用上一轮需求”或“已跳过追问”的状态文案

### 12. 推荐结果和对比结果的展示分区仍偏挤
- 严重级别：中
- 现象：推荐商品、对比表、反馈按钮在同屏密度高时容易挤压，尤其是推荐卡较多或对比行数较多时
- 影响：普通用户读起来费劲，尤其在商品比较场景下容易跳读
- 证据：`frontend/src/components/ShoppingBubble.tsx`、`frontend/src/components/ProductCard.tsx`、`frontend/src/components/ComparisonTable.tsx`
- 建议：将“推荐”和“对比”拆成更明确的分区，限制首屏展示长度

### 13. 反馈入口过于轻量，容易被忽略
- 严重级别：低
- 现象：反馈按钮在商品卡下方，普通用户不一定注意到，且没有强提示说明反馈用途
- 影响：质量回流不足，后续推荐优化缺少真实信号
- 证据：`frontend/src/components/ProductCard.tsx`
- 建议：增加更清晰的反馈引导文案或统一反馈面板

### 14. 会话历史与当前推荐的关系不够直观
- 严重级别：低
- 现象：用户切换历史会话后，当前对话上下文与历史推荐的关联不够显性
- 影响：普通用户容易搞不清“我现在是在看哪次对话的结果”
- 证据：`frontend/src/App.tsx`、`frontend/src/lib/shoppingApi.ts`
- 建议：历史会话进入后展示标题、最后一次查询和状态标签

### 15. 评测和冒烟脚本依赖完整后端环境
- 严重级别：中
- 现象：`scripts/smoke_shopping.py` 和 `evals/run_shopping_evals.py` 依赖 API_TOKEN、后端服务和数据种子，普通开发环境稍有缺项就会失败
- 影响：普通用户不直接感知，但影响问题复现和修复效率
- 证据：`scripts/smoke_shopping.py`、`evals/run_shopping_evals.py`
- 建议：增加本地可离线运行的 mock/snapshot 测试模式

### 16. 线上接口文档不可直接用于排障
- 严重级别：低
- 现象：访问 `http://1.13.255.225/openapi.json` 返回的是前端 HTML，而不是 FastAPI OpenAPI JSON。
- 影响：对普通用户无直接影响，但测试、联调和排查接口字段时缺少线上契约入口，容易依赖过期文档。
- 证据：线上 `curl http://1.13.255.225/openapi.json` 返回 Vite HTML 模板。
- 建议：如果出于安全考虑关闭接口文档，应在内部环境提供受控 OpenAPI；如果不是刻意关闭，需要修正 Nginx `/openapi.json`、`/docs` 反代规则。

## 已验证项
- `uv run ruff check .` 通过
- `uv run pytest -q` 通过（3 passed）
- 线上首页可正常加载，标题为 `PickMate AI · 电商商品决策助手`
- 未携带 `API_TOKEN` 请求 `/api/shopping/query` 和 `/api/shopping/sessions` 均返回 `401 Invalid API token`
- 注册接口可返回 JWT；只携带 JWT 请求导购接口仍返回 `401 Invalid API token`
- 注册入参过短时可返回 422 基础校验错误
- 连续 5 次错误登录均返回 401，未观察到限流/锁定提示

## 测试结论
当前系统首屏可访问，但作为 C 端普通用户还没有形成完整闭环：注册/登录成功后仍无法使用导购，核心接口依赖共享 `API_TOKEN`，且会话归属校验没有闭合。

上线前建议优先修复：
1. HTTPS 与鉴权闭环；
2. 从 JWT 解析用户身份并统一会话归属校验；
3. 会话列表、详情、删除、继续追问、反馈、埋点的越权风险；
4. 导购与登录接口限流、输入长度和资源消耗控制；
5. 前端 401 状态提示和访问令牌入口的产品化处理。
