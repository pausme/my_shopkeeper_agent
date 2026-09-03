<div align='center'>
  <h1 style="margin-top: 15px;">PickMate AI · 电商 AI 商品决策助手</h1>
  <p><em>用自然语言把「我该买哪个」变成可解释、可比较、可行动的购买决策：意图理解 → 智能追问 → 商品召回 → 评价风险分析 → 可解释推荐 → 横向对比</em></p>
</div>

<div align='center'>

![Python](https://img.shields.io/badge/Python-3.14-3776AB.svg?logo=python&logoColor=white)
![LangGraph](https://img.shields.io/badge/LangGraph-Agentic%20Workflow-1C3C3C.svg)
![FastAPI](https://img.shields.io/badge/FastAPI-SSE%20Streaming-009688.svg)
![Deploy](https://img.shields.io/badge/Deploy-GitHub%20Actions-2088FF.svg?logo=githubactions&logoColor=white)

</div>

## 这是什么

PickMate AI 是一款面向 C 端电商用户的 AI 导购工具。用户用自然语言描述购买需求（"想买个空气炸锅预算 500"），系统完成：

1. **需求理解**：单次 LLM 调用识别意图（推荐/对比/避坑/追问）并抽取槽位（品类、预算、场景、人群、偏好、排除项）；
2. **智能追问**：信息不足时主动追问（最多 1 次，只问品类这一最关键缺失）；
3. **商品召回**：Qdrant 语义召回（需求+槽位拼接文本）+ MySQL 主库结构化校正；
4. **评价与风险分析**：预计算的风险摘要（差评占比定级/风险标签/适合人群）+ ES 差评原文佐证；
5. **确定性重排**：语义匹配 0.45 / 评分 0.2 / 销量 0.15 / 预算契合 0.2 − 风险惩罚，品类硬约束 + 语义地板分拦截跑题候选；
6. **可解释推荐**：LLM 生成推荐理由，**强制锚定真实价格/评分/销量/评价/风险字段**（product_id 白名单防编造），母婴品类自动追加谨慎话术；
7. **横向对比与反馈闭环**：结构化对比表、四类轻反馈、行为埋点。

全部过程经 SSE 流式推送（progress / clarification / recommendation / comparison / error 五类事件）。

## 技术栈

| 模块 | 技术 | 作用 |
| --- | --- | --- |
| 智能体编排 | LangGraph | 10 节点导购工作流 |
| 商品语义召回 | Qdrant / bge-large-zh-v1.5（TEI ONNX int8） | 标题+类目+属性多语义入口 |
| 评价全文检索 | Elasticsearch / IK | 差评关键词与原文佐证 |
| 业务数据 | MySQL（商品/评价/风险摘要/会话/反馈/埋点） | 推荐链路权威数据源 |
| 后端 | FastAPI + SSE + JWT 认证 | `/api/shopping/*` 全套接口 |
| 前端 | React + Vite + Tailwind | 商品卡片、对比表、轻反馈、历史会话 |
| 质量 | pytest + 导购评测集（16 用例四类） | CI 门禁：lint + test + 部署后冒烟 |
| 发布 | uv / pnpm / GitHub Actions | push 即部署，服务器无需访问 GitHub |

## 快速开始

```bash
uv sync                                            # 后端依赖（uv 自动安装 Python 3.14）
cp .env.example .env                               # 填入 LLM_API_KEY（数据库等可按需覆盖）
docker compose -f docker/docker-compose.yaml up -d # MySQL/Qdrant/ES/TEI 基础服务
uv run python scripts/seed_shopping_data.py        # 生成 4 品类 24 商品 + 600 评价 + 双索引（可自定义规模）
uv run uvicorn main:app --host 0.0.0.0 --port 8000
cd frontend && pnpm install && pnpm dev
```

评测与冒烟：

```bash
API_TOKEN=xxx uv run python scripts/smoke_shopping.py            # 三用例冒烟
API_TOKEN=xxx uv run python evals/run_shopping_evals.py          # 16 用例全量评测
uv run pytest                                                    # 单元测试
```

## 项目结构

```text
├── app/
│   ├── agent/shopping/       # 导购 LangGraph 图、状态、上下文与 10 个节点
│   ├── api/                  # 认证路由、导购路由、依赖组装、生命周期
│   ├── clients/              # MySQL/Qdrant/ES/Embedding 客户端管理器
│   ├── models/               # 商品域 + 导购会话域 + 用户 ORM（启动自动建表）
│   ├── repositories/         # MySQL(meta)、Qdrant(商品)、ES(评价) 数据访问层
│   ├── services/             # 导购编排服务、认证服务
│   └── conf/                 # dataclass 结构化配置（检索参数可配）
├── evals/                    # 导购评测集（16 用例四类）与跑批脚本
├── scripts/                  # 种子数据、冒烟与备份脚本
├── frontend/                 # React 导购前端（商品卡片/对比/反馈/历史）
├── prompts/                  # 意图槽位抽取、追问改写、推荐生成 Prompt
├── docs/                     # PRD 文档与部署手册
└── .github/workflows/        # ci（lint+test）与 deploy（push 即发布 + 冒烟门禁）
```

## 服务器部署

4c4g 单机部署方案（含系统参数、安全组、GitHub Secrets 配置）见 **[docs/deploy.md](docs/deploy.md)**。配置好后日常发布：

```bash
git push origin main    # CI 自动构建前端、同步服务器、跑导购冒烟评测门禁
```

## Roadmap

- [ ] 导购评测集扩充：多品类组合、中文口语变体、对抗性输入
- [ ] 用户偏好记忆（shopping_user_preference 表已建）：历史咨询画像反哺排序
- [ ] 图文评价摘要、搭配购买方案（PRD 二期）
- [ ] 埋点看板：点击率/追问率/有帮助率对齐 PRD 成功指标

## 致谢

项目基础设施（FastAPI/SSE/LangGraph/Qdrant/ES/依赖注入骨架）源自 [didilili/shopkeeper-agent](https://github.com/didilili/shopkeeper-agent)（电商问数教学项目，整理自尚硅谷「大模型智能体掌柜问数」课程）。本项目在其工程底座上按 [PRD](docs/PRD-ai-shopping-decision-assistant-master.md) 重建为 AI 导购应用。License 沿用 MIT。
