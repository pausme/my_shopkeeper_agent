# 数据表设计：AI 商品决策助手

## 1. 设计原则

1. 保留当前项目已有的 `table_info`、`column_info`、`metric_info`、`column_metric` 元数据体系，但将业务实体从“数仓问数”扩展为“商品决策”。
2. 业务数据与元数据分离，避免推荐链路直接依赖业务表结构。
3. 推荐链路需要支持商品、评价、会话、反馈、用户偏好和埋点数据。
4. 核心表要支持增量更新和历史追溯。

## 2. 元数据层

### 2.1 保留表

| 表名 | 用途 |
| --- | --- |
| table_info | 商品、评价、会话等业务表的元信息 |
| column_info | 字段元数据 |
| metric_info | 指标元数据 |
| column_metric | 字段与指标关系 |

### 2.2 建议扩展字段

| 表名 | 新增字段 | 说明 |
| --- | --- | --- |
| table_info | biz_domain | 业务域，如 product / review / user / order |
| column_info | biz_tag | 业务标签，如 price / risk / scene / preference |
| metric_info | biz_scope | 指标适用范围 |
| metric_info | display_name | 前端展示名 |

## 3. 业务主数据表

### 3.1 商品表 `product_info`

| 字段名 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| id | bigint | 是 | 主键 |
| product_id | varchar(64) | 是 | 商品业务 ID |
| title | varchar(255) | 是 | 商品标题 |
| category_id | varchar(64) | 是 | 类目 ID |
| category_name | varchar(128) | 是 | 类目名称 |
| brand | varchar(128) | 否 | 品牌 |
| price | decimal(10,2) | 是 | 原价 |
| promotion_price | decimal(10,2) | 否 | 到手价 |
| stock | int | 否 | 库存 |
| sales_30d | int | 否 | 近 30 天销量 |
| rating | decimal(3,2) | 否 | 平均评分 |
| review_count | int | 否 | 评论数 |
| status | varchar(32) | 是 | on_sale / off_sale / deleted |
| attributes_json | json | 否 | 商品属性 |
| detail_text | text | 否 | 商品详情文本 |
| image_url | varchar(512) | 否 | 主图 |
| created_at | datetime | 是 | 创建时间 |
| updated_at | datetime | 是 | 更新时间 |
| is_deleted | tinyint | 是 | 逻辑删除 |

索引建议：

1. `uk_product_id` 唯一索引。
2. `idx_category_status_price` 联合索引。
3. `idx_brand` 普通索引。

### 3.2 商品评价表 `product_review`

| 字段名 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| id | bigint | 是 | 主键 |
| review_id | varchar(64) | 是 | 评价业务 ID |
| product_id | varchar(64) | 是 | 商品 ID |
| user_id | varchar(64) | 否 | 用户 ID |
| rating | tinyint | 是 | 评分 |
| content | text | 是 | 评价内容 |
| append_content | text | 否 | 追评 |
| sku_text | varchar(255) | 否 | 规格信息 |
| sentiment | varchar(32) | 否 | 情感倾向 |
| review_tags_json | json | 否 | 评价标签 |
| created_at | datetime | 是 | 评价时间 |
| is_deleted | tinyint | 是 | 逻辑删除 |

索引建议：

1. `uk_review_id` 唯一索引。
2. `idx_product_created_at` 联合索引。
3. `idx_sentiment` 普通索引。

### 3.3 商品风险摘要表 `product_risk_summary`

| 字段名 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| id | bigint | 是 | 主键 |
| product_id | varchar(64) | 是 | 商品 ID |
| risk_level | varchar(32) | 是 | low / medium / high |
| risk_tags_json | json | 是 | 风险标签 |
| risk_summary | text | 是 | 风险摘要 |
| sample_size | int | 是 | 样本量 |
| created_at | datetime | 是 | 创建时间 |
| updated_at | datetime | 是 | 更新时间 |
| is_deleted | tinyint | 是 | 逻辑删除 |

索引建议：

1. `uk_product_id` 唯一索引。
2. `idx_risk_level` 普通索引。

## 4. 会话与反馈表

### 4.1 导购会话表 `shopping_session`

| 字段名 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| id | bigint | 是 | 主键 |
| session_id | varchar(64) | 是 | 会话 ID |
| user_id | varchar(64) | 否 | 用户 ID |
| scene_tag | varchar(64) | 否 | 场景标签 |
| title | varchar(255) | 否 | 会话标题 |
| status | varchar(32) | 是 | active / stopped / completed |
| last_query | varchar(1024) | 否 | 最近一次用户输入 |
| created_at | datetime | 是 | 创建时间 |
| updated_at | datetime | 是 | 更新时间 |
| is_deleted | tinyint | 是 | 逻辑删除 |

索引建议：

1. `uk_session_id` 唯一索引。
2. `idx_user_updated_at` 联合索引。

### 4.2 导购消息表 `shopping_message`

| 字段名 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| id | bigint | 是 | 主键 |
| message_id | varchar(64) | 是 | 消息 ID |
| session_id | varchar(64) | 是 | 会话 ID |
| role | varchar(16) | 是 | user / assistant / system |
| content | text | 是 | 消息内容 |
| message_type | varchar(32) | 是 | query / clarification / recommendation / comparison / error |
| trace_json | json | 否 | 执行过程 |
| created_at | datetime | 是 | 创建时间 |
| is_deleted | tinyint | 是 | 逻辑删除 |

索引建议：

1. `uk_message_id` 唯一索引。
2. `idx_session_created_at` 联合索引。

### 4.3 推荐结果表 `shopping_recommendation`

| 字段名 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| id | bigint | 是 | 主键 |
| recommendation_id | varchar(64) | 是 | 推荐结果 ID |
| session_id | varchar(64) | 是 | 会话 ID |
| message_id | varchar(64) | 是 | 消息 ID |
| query_text | varchar(1024) | 是 | 用户问题 |
| result_json | json | 是 | 推荐结果整体结构 |
| comparison_json | json | 否 | 对比信息 |
| created_at | datetime | 是 | 创建时间 |
| is_deleted | tinyint | 是 | 逻辑删除 |

索引建议：

1. `uk_recommendation_id` 唯一索引。
2. `idx_session_created_at` 联合索引。

### 4.4 用户反馈表 `shopping_feedback`

| 字段名 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| id | bigint | 是 | 主键 |
| feedback_id | varchar(64) | 是 | 反馈 ID |
| session_id | varchar(64) | 是 | 会话 ID |
| message_id | varchar(64) | 是 | 消息 ID |
| product_id | varchar(64) | 否 | 商品 ID |
| user_id | varchar(64) | 否 | 用户 ID |
| feedback_type | varchar(32) | 是 | helpful / unhelpful / not_accurate 等 |
| comment | varchar(1024) | 否 | 补充说明 |
| created_at | datetime | 是 | 创建时间 |
| is_deleted | tinyint | 是 | 逻辑删除 |

索引建议：

1. `uk_feedback_id` 唯一索引。
2. `idx_session_created_at` 联合索引。

## 5. 偏好与埋点表

### 5.1 用户偏好表 `shopping_user_preference`

| 字段名 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| id | bigint | 是 | 主键 |
| user_id | varchar(64) | 是 | 用户 ID |
| preference_key | varchar(64) | 是 | 偏好项 |
| preference_value | varchar(255) | 是 | 偏好值 |
| confidence | decimal(3,2) | 否 | 置信度 |
| source | varchar(32) | 否 | explicit / inferred |
| updated_at | datetime | 是 | 更新时间 |
| is_deleted | tinyint | 是 | 逻辑删除 |

### 5.2 查询埋点表 `shopping_event_log`

| 字段名 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| id | bigint | 是 | 主键 |
| session_id | varchar(64) | 是 | 会话 ID |
| message_id | varchar(64) | 否 | 消息 ID |
| user_id | varchar(64) | 否 | 用户 ID |
| event_type | varchar(64) | 是 | query_start / recall_done / recommendation_shown / click / feedback |
| event_data_json | json | 否 | 事件内容 |
| created_at | datetime | 是 | 创建时间 |

## 6. 索引与约束建议

1. 所有业务 ID 统一使用 `varchar(64)`，便于和外部平台 ID 对齐。
2. 会话、消息、推荐、反馈都要有唯一业务 ID，避免幂等问题。
3. 推荐链路高频查询字段必须建立组合索引。
4. 商品和评价表要支持增量更新，不建议只靠全量重建。
5. 风险摘要、评价摘要可以缓存为结果表，避免每次都重新聚合。

