<div align='center'>
  <h1 style="margin-top: 15px;">电商问数 Agent（个人二开版）</h1>
  <p><em>基于 LangGraph 的 Text-to-SQL 全链路实践：混合检索 → 多阶段推理 → SQL 生成校验执行 → SSE 流式交付，附单机生产部署与 push 即发布的 CI 链路</em></p>
</div>

<div align='center'>

![Python](https://img.shields.io/badge/Python-3.14-3776AB.svg?logo=python&logoColor=white)
![LangGraph](https://img.shields.io/badge/LangGraph-Agentic%20Workflow-1C3C3C.svg)
![FastAPI](https://img.shields.io/badge/FastAPI-SSE%20Streaming-009688.svg)
![Deploy](https://img.shields.io/badge/Deploy-GitHub%20Actions-2088FF.svg?logo=githubactions&logoColor=white)

</div>

## 这是什么

业务同学用自然语言提问（如"统计华北地区的销售总额"），系统不靠大模型直出答案，而是：先从元数据知识库召回相关**字段、指标口径、字段真实取值**，让模型在受约束的上下文里分步推理，生成 SQL 并经数据库 `EXPLAIN` 校验、失败自动修正，最后在真实数仓上执行——结果由数据库计算产生，把模型幻觉压缩到"SQL 写得对不对"这一件事上。

![系统架构](docs/images/shopkeeper-agent-system-architecture.svg)

项目围绕两条主线：

| 主线 | 做什么 | 涉及模块 |
| --- | --- | --- |
| 元数据知识库构建 | 抽取数仓的表、字段、指标、字段取值，写入结构化库、向量库和全文索引 | MySQL / Qdrant / Elasticsearch / TEI |
| 自然语言问数 | 召回 → 上下文整理 → SQL 生成校验执行，过程流式返回前端 | LangGraph / FastAPI SSE / React |

![查询效果](docs/images/shopkeeper-agent-query-result.jpg)

## 与原项目的差异（二开增强）

本项目基于 [didilili/shopkeeper-agent](https://github.com/didilili/shopkeeper-agent) 二次开发，在其教学闭环之上补齐了**面向单台服务器落地**的工程链路：

- **生产部署方案**：`docker/docker-compose.server.yaml` 面向 4c4g 单机——裁掉 Kibana、ES 堆与 MySQL buffer pool 约束、TEI 本地跑 bge-large-zh-v1.5、全部基础服务仅绑 `127.0.0.1`，对外只暴露 nginx 的 80 端口；
- **前端同域反代**：nginx 托管前端产物并反代 `/api`，SSE 路径关闭缓冲，前端零跨域配置；
- **配置与密钥解耦**：数据库凭据经 `${oc.env:...}` 注入（`conf/app_config.yaml`）、compose 密码走 `docker/.env`，仓库里不再出现任何真实密钥，代码可随时覆盖服务器而不破坏运行配置；
- **CI 自动发布**：push 到 `main` 即由 GitHub Actions 构建前端、SSH 直投服务器并重启服务（见 `.github/workflows/deploy.yml`），**服务器全程不需要访问 GitHub**——对网络受限的境内/跨境服务器尤其友好；
- **部署手册**：[docs/deploy.md](docs/deploy.md) 覆盖初始化参数、端口安全组、故障排查表与重启恢复清单。

## 技术栈

| 模块 | 技术 | 作用 |
| --- | --- | --- |
| 教学数仓 | MySQL（星型模型） | 事实表 `fact_order` + 地区/客户/商品/时间四维表 |
| 元数据库 | MySQL / SQLAlchemy | 表、字段、指标及字段-指标依赖关系的权威来源 |
| 语义召回 | Qdrant / bge-large-zh-v1.5（TEI） | 字段与指标向量检索 |
| 值域召回 | Elasticsearch / IK | 字段真实取值的全文检索 |
| 智能体编排 | LangGraph | 12 节点工作流：关键词抽取与 LLM 检索词扩展 → 三路并行召回 → 合并 → 上下文补全 → 过滤+SQL 生成单次调用 → 校验/修正重试闭环/执行（sqlglot 只读硬校验） |
| 后端 | FastAPI + loguru | `/api/query` SSE 接口、request_id 链路日志 |
| 前端 | React + Vite + Tailwind | 聊天式问数界面、节点进度条、结果表格 |
| 发布 | uv / pnpm / GitHub Actions | 依赖管理、构建与自动部署 |

## 快速开始

### 本地开发

```bash
uv sync                                            # 后端依赖（uv 自动安装 Python 3.14）
cp .env.example .env                               # 填入 LLM_API_KEY
docker compose -f docker/docker-compose.yaml up -d # 起 MySQL/Qdrant/ES/TEI 基础服务
uv run python -m app.scripts.build_meta_knowledge -c conf/meta_config.yaml  # 构建元数据知识库
uv run fastapi dev main.py                         # 启动后端
cd frontend && pnpm install && pnpm dev            # 启动前端
```

数据库连接默认 `localhost:3306 didilili/dili123`，可通过 `.env` 中 `DB_HOST/DB_PORT/DB_USER/DB_PASSWORD` 覆盖。

### 服务器部署

完整步骤（系统参数、安全组、Secrets 配置、故障排查）见 **[docs/deploy.md](docs/deploy.md)**。配置好 GitHub Secrets 后，日常发布只需：

```bash
git push origin main
```

## 项目结构

```text
├── app/
│   ├── agent/            # LangGraph 图、状态、上下文与 12 个流程节点
│   ├── api/              # FastAPI 路由、依赖组装、生命周期
│   ├── clients/          # MySQL/Qdrant/ES/Embedding 客户端管理器
│   ├── conf/             # dataclass 结构化配置
│   ├── repositories/     # MySQL(meta/dw)、Qdrant、ES 数据访问层
│   ├── services/         # 元数据构建服务、问数查询服务
│   └── ...
├── docker/               # 开发版与服务版 compose、MySQL 初始化 SQL、nginx 配置
├── frontend/             # React 聊天式问数前端
├── prompts/              # 关键词扩展、过滤、SQL 生成/修正 Prompt
├── .github/workflows/    # push 即部署的 CI 流水线
└── docs/deploy.md        # 服务器部署手册
```

## Roadmap

- [ ] 前端多会话管理：会话列表、localStorage 持久化、历史切换（当前"新会话"仅清空）
- [ ] Embedding 提速：TEI 切换 ONNX 后端（当前 CPU 推理单次 ~6s，是查询延迟大头）
- [ ] SQL 修正闭环改循环重试（当前仅修正一轮）
- [ ] 指标配置治理（原项目 `meta_config.yaml` 中 AOV 依赖字段疑似笔误）
- [ ] 查询结果可视化图表
- [ ] 召回环节关键词去噪与并发 embedding

## 致谢

本项目基于 [didilili/shopkeeper-agent](https://github.com/didilili/shopkeeper-agent) 二次开发，原项目整理自尚硅谷「大模型智能体掌柜问数」实战课程，并配套系统性文字教程，适合按章节学习问数 Agent 的完整链路。License 沿用 MIT。
