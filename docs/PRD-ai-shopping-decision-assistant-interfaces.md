# 接口清单：AI 商品决策助手

## 1. 接口总览

| 接口名称 | 请求方式 | 路径 | 用途 | 是否一期 |
| --- | --- | --- | --- | --- |
| 发起导购问答 | POST | /api/shopping/query | 接收自然语言需求，流式返回推荐过程和结果 | 是 |
| 提交反馈 | POST | /api/shopping/feedback | 记录用户对推荐结果的反馈 | 是 |
| 获取会话列表 | GET | /api/shopping/sessions | 获取用户历史导购会话 | 是 |
| 获取会话详情 | GET | /api/shopping/sessions/{session_id} | 获取单个会话的消息历史 | 是 |
| 终止会话 | POST | /api/shopping/sessions/{session_id}/stop | 主动终止当前流式推荐 | 是 |
| 获取商品对比 | POST | /api/shopping/compare | 对多个商品生成横向对比结果 | 是 |
| 获取商品详情摘要 | GET | /api/shopping/products/{product_id}/summary | 返回商品简介、评价摘要和风险提示 | 是 |
| 保存用户偏好 | POST | /api/shopping/preferences | 保存用户显式偏好 | 二期 |
| 获取用户偏好 | GET | /api/shopping/preferences | 获取偏好画像 | 二期 |
| 降价提醒订阅 | POST | /api/shopping/alerts/price-drop | 订阅商品降价提醒 | 二期 |

## 2. 核心接口明细

### 2.1 发起导购问答

| 项目 | 内容 |
| --- | --- |
| 接口名称 | 发起导购问答 |
| 请求方式 | POST |
| 路径 | /api/shopping/query |
| 响应类型 | text/event-stream |
| 功能说明 | 接收用户自然语言问题，返回追问、召回、分析、推荐和对比信息 |

请求参数：

| 字段 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| query | string | 是 | 用户输入 |
| session_id | string | 否 | 会话 ID，不传则新建 |
| history | array | 否 | 近几轮对话 |
| selected_product_ids | array[string] | 否 | 用户指定要比较的商品 |
| scene_tag | string | 否 | 场景标签，如租房、送礼、母婴 |

SSE 事件：

| type | 说明 |
| --- | --- |
| progress | 当前执行步骤 |
| clarification | 需要用户补充信息 |
| recommendation | 推荐结果 |
| comparison | 对比结果 |
| error | 错误信息 |

返回结果结构：

| 字段 | 说明 |
| --- | --- |
| session_id | 会话 ID |
| message_id | 当前消息 ID |
| recommended_products | 推荐商品列表 |
| comparison_table | 商品对比表 |
| next_question | 下一轮追问 |
| trace | 执行过程节点 |

### 2.2 提交反馈

| 项目 | 内容 |
| --- | --- |
| 接口名称 | 提交反馈 |
| 请求方式 | POST |
| 路径 | /api/shopping/feedback |
| 功能说明 | 记录用户对推荐是否有帮助的反馈 |

请求参数：

| 字段 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| session_id | string | 是 | 会话 ID |
| message_id | string | 是 | 消息 ID |
| feedback_type | string | 是 | helpful / unhelpful / not_accurate / too_expensive / too_few / not_understand |
| product_id | string | 否 | 关联商品 |
| comment | string | 否 | 用户补充说明 |

### 2.3 获取会话列表

| 项目 | 内容 |
| --- | --- |
| 接口名称 | 获取会话列表 |
| 请求方式 | GET |
| 路径 | /api/shopping/sessions |
| 功能说明 | 获取当前用户的历史会话 |

查询参数：

| 字段 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| page | int | 否 | 页码 |
| page_size | int | 否 | 每页数量 |
| keyword | string | 否 | 会话关键词 |

### 2.4 获取会话详情

| 项目 | 内容 |
| --- | --- |
| 接口名称 | 获取会话详情 |
| 请求方式 | GET |
| 路径 | /api/shopping/sessions/{session_id} |
| 功能说明 | 获取会话中的消息、商品推荐和反馈记录 |

### 2.5 终止会话

| 项目 | 内容 |
| --- | --- |
| 接口名称 | 终止会话 |
| 请求方式 | POST |
| 路径 | /api/shopping/sessions/{session_id}/stop |
| 功能说明 | 主动中断 SSE 流式推荐 |

### 2.6 获取商品对比

| 项目 | 内容 |
| --- | --- |
| 接口名称 | 获取商品对比 |
| 请求方式 | POST |
| 路径 | /api/shopping/compare |
| 功能说明 | 对多个商品做参数、评价、风险和适配场景对比 |

请求参数：

| 字段 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| product_ids | array[string] | 是 | 商品 ID 列表 |
| query | string | 否 | 用户原始需求 |
| session_id | string | 否 | 会话 ID |

### 2.7 获取商品详情摘要

| 项目 | 内容 |
| --- | --- |
| 接口名称 | 获取商品详情摘要 |
| 请求方式 | GET |
| 路径 | /api/shopping/products/{product_id}/summary |
| 功能说明 | 返回单商品的摘要、评价风险和适合人群 |

## 3. 接口规则

1. `/api/shopping/query` 必须走 SSE，首包尽快返回进度。
2. 查询接口不直接暴露 SQL、提示词、内部向量分值。
3. 用户反馈必须可追溯到 session_id 和 message_id。
4. 对比接口必须保证同品类优先，不同品类需要明确提示。
5. 不足样本要明确提示，不允许伪造评价摘要。
6. 需要登录态时，统一从用户上下文获取 user_id，不放在 query 参数里。

