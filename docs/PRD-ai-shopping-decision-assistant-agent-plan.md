# Agent / 工具改造方案：AI 商品决策助手

## 1. 改造目标

把当前“电商问数 Agent”改造成“商品决策 Agent”，让它从查询数仓指标转向帮助用户做购买决策。

核心变化：

1. 目标从“问数”变成“导购”。
2. 数据对象从“表/字段/指标”变成“商品/评价/风险/偏好”。
3. 输出从“SQL 结果”变成“推荐、对比和建议”。
4. 交互从“一次性问答”变成“多轮决策对话”。

## 2. 现有能力保留项

当前仓库里可以直接复用的部分：

1. FastAPI + SSE 流式返回。
2. LangGraph 状态机编排。
3. Qdrant 向量召回。
4. Elasticsearch 全文检索。
5. MySQL 结构化查询。
6. 前端对话式交互。
7. 依赖注入与生命周期管理。

## 3. 现有链路问题

当前链路中心是 SQL 闭环，主要节点包括：

1. extract_keywords
2. extend_keywords
3. recall_column / recall_metric / recall_value
4. merge_retrieved_info
5. filter_table / filter_metric
6. add_extra_context
7. generate_sql
8. validate_sql
9. correct_sql
10. run_sql

这些节点适合“结构化问数”，但对 C 端导购还缺少：

1. 场景识别。
2. 追问决策。
3. 商品适配度计算。
4. 评价风险摘要。
5. 推荐解释生成。
6. 商品对比输出。
7. 用户反馈闭环。

## 4. 建议的 Agent 新工作流

```text
rewrite_question
  -> extract_intent
  -> extract_purchase_slots
  -> decide_clarification
  -> recall_products
  -> analyze_reviews
  -> compute_risk_summary
  -> rank_products
  -> generate_recommendation
  -> build_comparison
  -> persist_session
  -> emit_sse_result
```

## 5. 节点改造建议

### 5.1 保留并改名的节点

| 当前节点 | 建议用途 | 说明 |
| --- | --- | --- |
| rewrite_question | 保留 | 多轮追问改写为独立购买需求 |
| extract_keywords | 保留并扩展 | 抽取品类、场景、预算、偏好、排除项 |

### 5.2 新增节点

| 新节点 | 职责 | 输入 | 输出 |
| --- | --- | --- | --- |
| extract_intent | 识别推荐、对比、避坑、追问 | query, history | intent |
| extract_purchase_slots | 抽取预算、场景、人群、偏好 | query, rewritten_query | purchase_slots |
| decide_clarification | 判断是否需要追问 | purchase_slots | clarification_question |
| recall_products | 召回候选商品 | purchase_slots | candidate_products |
| analyze_reviews | 摘要评价和差评风险 | candidate_products | review_summary |
| compute_risk_summary | 归纳适配风险 | review_summary | risk_summary |
| rank_products | 商品重排 | candidate_products, risk_summary | ranked_products |
| generate_recommendation | 生成推荐说明 | ranked_products | recommendation |
| build_comparison | 生成对比表 | ranked_products | comparison_table |
| persist_session | 落库会话、消息、反馈 | recommendation | session records |
| emit_sse_result | 统一 SSE 输出 | recommendation | progress / result |

## 6. 工具层改造

### 6.1 需要新增的工具

| 工具 | 用途 |
| --- | --- |
| ProductRepository | 商品基础数据查询 |
| ReviewRepository | 评价查询与聚合 |
| RiskSummaryRepository | 风险摘要读写 |
| SessionRepository | 会话持久化 |
| FeedbackRepository | 用户反馈存储 |
| PreferenceRepository | 用户偏好存储 |
| ProductSearchService | 商品召回聚合服务 |
| RecommendationService | 推荐排序与解释生成服务 |

### 6.2 现有工具如何复用

| 现有工具 | 改造方式 |
| --- | --- |
| ColumnQdrantRepository | 改为 ProductQdrantRepository，存商品语义向量 |
| MetricQdrantRepository | 改为 Scene/QA template Qdrant 或二级商品标签库 |
| ValueESRepository | 改为 ReviewESRepository，用于评价与关键词全文检索 |
| DWMySQLRepository | 改为商品主库查询、价格、库存和类目数据读取 |
| MetaMySQLRepository | 改为导购元数据管理，维护商品标签、类目、指标口径 |

## 7. LangGraph 状态改造

建议将现有 `DataAgentState` 改为 `ShoppingAgentState`，核心字段如下：

| 字段 | 说明 |
| --- | --- |
| query | 用户原始输入 |
| rewritten_query | 改写后的独立需求 |
| intent | 导购意图 |
| purchase_slots | 预算、场景、偏好、排除项 |
| clarification_needed | 是否需要追问 |
| clarification_question | 追问内容 |
| candidate_products | 候选商品 |
| review_summary | 评价摘要 |
| risk_summary | 风险摘要 |
| ranked_products | 排序结果 |
| recommendation | 推荐结果 |
| comparison_table | 对比表 |
| history | 多轮上下文 |
| session_id | 会话 ID |
| error | 错误信息 |

## 8. 依赖注入与生命周期

### 8.1 应用启动

1. 初始化商品检索、评价检索、偏好存储、会话存储和推荐服务。
2. 复用 FastAPI lifespan 做统一资源管理。

### 8.2 请求级依赖

建议通过 `dependencies.py` 注入：

1. ProductRepository
2. ReviewRepository
3. SessionRepository
4. FeedbackRepository
5. RecommendationService
6. ShoppingAgentService

## 9. 服务层职责拆分

### 9.1 ShoppingAgentService

职责：

1. 组装状态和上下文。
2. 调用 LangGraph。
3. 把事件转成 SSE 输出。
4. 处理缓存和会话追踪。

### 9.2 RecommendationService

职责：

1. 召回候选商品。
2. 计算匹配分数。
3. 归纳风险摘要。
4. 生成推荐结果结构。

### 9.3 SessionService

职责：

1. 新建会话。
2. 保存对话消息。
3. 保存推荐结果。
4. 支持历史查询。

## 10. 迁移步骤

### 阶段 1：保留旧链路，新增导购链路

1. 保留当前 `/api/query` 作为旧问数能力。
2. 新增 `/api/shopping/query`。
3. 新增商品/评价/反馈表。
4. 接入新前端入口。

### 阶段 2：替换召回对象

1. 将字段召回改为商品召回。
2. 将指标召回改为场景模板或商品标签召回。
3. 将 ES 取值检索改为评价检索。

### 阶段 3：替换生成目标

1. 将 SQL 生成改为推荐结果生成。
2. 将 SQL 校验改为推荐规则校验。
3. 将 SQL 执行改为结果落库和展示。

### 阶段 4：补闭环

1. 增加反馈。
2. 增加偏好记忆。
3. 增加会话管理。
4. 增加推荐评估指标。

## 11. 风险点

| 风险 | 说明 | 应对 |
| --- | --- | --- |
| 幻觉 | 编造商品参数或评价 | 所有事实必须来自数据库或检索结果 |
| 追问过多 | 用户流失 | 追问最多 2 次 |
| 推荐不可信 | 用户认为是广告 | 推荐理由必须可追溯 |
| 延迟过高 | 影响体验 | SSE 进度 + 缓存 + 并发检索 |
| 数据缺失 | 推荐不稳定 | 允许降级并提示样本不足 |

