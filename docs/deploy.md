# shopkeeper-agent 服务器部署手册（4c4g · 方案 A 全本地）

本手册描述如何把项目部署到一台 **4 核 4GB** 的 Linux 服务器，采用**全本地方案**：
Embedding 用本机 TEI 跑 bge-large-zh-v1.5，不依赖外部向量化服务；唯一的外部调用是问数时的 LLM（硅基流动）。

配套文件：

| 文件 | 作用 |
| --- | --- |
| `docker/docker-compose.server.yaml` | 服务器版编排：无 Kibana、ES 堆 512m、MySQL 调优、各服务绑 127.0.0.1、含 nginx 前端服务 |
| `docker/nginx/frontend.conf` | nginx 静态托管 + `/api` SSE 反代（已关闭缓冲） |

## 资源预算（4GB）

| 组件 | 预期内存 |
| --- | --- |
| OS + Docker daemon | ~300 MB |
| MySQL（buffer pool 128M） | ~300 MB |
| Elasticsearch（堆 512m） | ~850 MB |
| Qdrant | ~150 MB |
| TEI + bge-large-zh-v1.5 | ~1.5 GB |
| FastAPI 后端 | ~250 MB |
| nginx 前端 | ~20 MB |
| Portainer | ~150 MB |
| **合计** | **≈ 3.5 GB**（建议 2G swap 兜底） |

磁盘预留约 10GB（镜像 + 数据卷 + 模型）。

## 端口与安全组

| 端口 | 服务 | 是否放行公网 |
| --- | --- | --- |
| 22 | SSH | 是（建议限源 IP） |
| 80 | nginx 前端入口 | 是 |
| 9443 | Portainer | 建议限源 IP 或走 SSH 隧道 |
| 3306 / 6333 / 6334 / 8081 / 9200 | MySQL / Qdrant / TEI / ES | **否**（已绑 127.0.0.1） |
| 8000 | FastAPI 后端 | **否**（仅 nginx 容器经 host-gateway 访问） |

> 安全组（云平台层面）只放行 22 / 80 / 9443。ES 关闭了安全认证、MySQL 是弱密码，绝不能暴露公网。

---

## 步骤 1：服务器初始化

确认 CPU 架构为 x86_64（TEI 镜像只有 amd64 版）：

```bash
uname -m   # 应输出 x86_64
```

安装 Docker（Ubuntu/Debian/CentOS 通用官方脚本）：

```bash
curl -fsSL https://get.docker.com | sudo sh
```

调整 ES 依赖的内核参数（云服务器默认值不够，ES 会启动失败）：

```bash
echo 'vm.max_map_count=262144' | sudo tee /etc/sysctl.d/99-es.conf && sudo sysctl --system
```

创建 2G swap 并持久化：

```bash
sudo fallocate -l 2G /swapfile && sudo chmod 600 /swapfile && sudo mkswap /swapfile && sudo swapon /swapfile && echo '/swapfile none swap sw 0 0' | sudo tee -a /etc/fstab
```

## 步骤 2：上传代码与模型

在服务器上准备代码（二选一：git clone，或从本地 `rsync -av --exclude .git --exclude node_modules ./ user@server:~/shopkeeper-agent/`）：

```bash
git clone https://github.com/didilili/shopkeeper-agent.git ~/shopkeeper-agent
```

> 如果你在本地改过代码，以后者为准；`docker-compose.server.yaml` 和 `docker/nginx/frontend.conf` 是新增文件，记得一并同步。

安装 uv 并同步 Python 依赖：

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh && cd ~/shopkeeper-agent && uv sync
```

配置应用环境变量（`.env`，数据库等连接参数均通过环境变量注入，见 `conf/app_config.yaml` 中的 `${oc.env:...}` 占位）：

```bash
cp .env.example .env && vim .env
```

服务器版 `.env` 示例（本地开发不设置 DB_* 时自动使用默认值 didilili/dili123/3306）：

```bash
LLM_API_KEY=你的大模型密钥
DB_HOST=localhost
DB_PORT=13306
DB_USER=root
DB_PASSWORD=你的MySQL密码
```

再准备 Docker 侧环境变量（compose 文件同目录，首次初始化数据卷时生效）：

```bash
cp docker/.env.example docker/.env && vim docker/.env
```

下载 Embedding 模型（约 1.3GB，一次性）：

```bash
uv run hf download BAAI/bge-large-zh-v1.5 --local-dir docker/embedding/bge-large-zh-v1.5
```

## 步骤 3：本地构建前端并上传（在你自己的电脑上执行）

```bash
cd frontend && pnpm install && pnpm build
```

把产物传到服务器（路径必须是 `项目根/frontend/dist`，compose 文件按相对路径挂载）：

```bash
rsync -av frontend/dist/ user@服务器IP:~/shopkeeper-agent/frontend/dist/
```

## 步骤 4：启动基础服务并验证

```bash
cd ~/shopkeeper-agent && docker compose -f docker/docker-compose.server.yaml up -d
```

MySQL 首次启动会自动执行 `docker/mysql/dw.sql` 和 `meta.sql` 初始化数仓与元数据库（首次约需 1~2 分钟）。逐个验证：

```bash
curl -s 127.0.0.1:9200 | head -5        # ES：返回版本信息
curl -s 127.0.0.1:6333                   # Qdrant：返回版本 JSON
curl -s 127.0.0.1:8081/health            # TEI：返回 ok（模型加载需几十秒）
docker exec mysql mysql -udidilili -pdili123 -e "show databases;"   # 应看到 dw 和 meta
```

## 步骤 5：构建元数据知识库（一次性）

```bash
cd ~/shopkeeper-agent && uv run python -m app.scripts.build_meta_knowledge -c conf/meta_config.yaml
```

这一步只依赖本地 TEI，不需要外网。成功后 Qdrant 里出现 `column_info_collection` / `metric_info_collection`，ES 里出现 `value_index`。元数据持久化在 Docker 卷中，**服务器重启后不需要重建**。

## 步骤 6：启动后端（systemd 保活）

创建 `/etc/systemd/system/shopkeeper.service`，把 `User` 和路径替换成你的实际值：

```ini
[Unit]
Description=shopkeeper-agent backend
After=network.target docker.service

[Service]
User=ubuntu
WorkingDirectory=/home/ubuntu/shopkeeper-agent
ExecStart=/home/ubuntu/.local/bin/uv run uvicorn main:app --host 0.0.0.0 --port 8000
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl daemon-reload && sudo systemctl enable --now shopkeeper
```

说明：绑定 `0.0.0.0` 是为了让 nginx 容器经 `host.docker.internal`（host-gateway）访问到它；安全组不放行 8000 即可挡住外部访问。不要用 README 里的 `fastapi dev`，那是开发模式。

## 步骤 7：安装 Portainer

```bash
docker volume create portainer_data && docker run -d -p 9443:9443 --name portainer --restart=unless-stopped -v /var/run/docker.sock:/var/run/docker.sock -v portainer_data:/data portainer/portainer-ce:lts
```

启动后**几分钟内**访问 `https://服务器IP:9443` 设置管理员密码（超时会自动锁定，需重启容器）。更安全的访问方式是 SSH 隧道：

```bash
ssh -L 9443:localhost:9443 user@服务器IP   # 然后本机访问 https://localhost:9443
```

## 步骤 8：整体验证

先在服务器上直连后端，确认 SSE 链路通（`-N` 关闭 curl 缓冲才能看到逐步输出）：

```bash
curl -N -X POST http://127.0.0.1:8000/api/query -H 'Content-Type: application/json' -d '{"query":"统计华北地区的销售总额"}'
```

应依次收到 `progress`（抽取关键词 → 三路召回 → 合并 → 过滤 → 生成SQL → 校验SQL → 执行SQL）和最后的 `result` 消息。

然后浏览器访问 `http://服务器IP`，输入同一个问题：StepRail 逐步亮起、最后出结果表格即部署成功。

在 Portainer 的 Containers 页面核对各容器实际内存占用，验证预算。

---

## 故障排查

| 现象 | 排查方向 |
| --- | --- |
| ES 容器反复重启 | 看 `docker logs elasticsearch`：`max virtual memory areas` 报错 → 步骤 1 的 sysctl 没生效；`Killed` → 内存不足，确认 swap 已挂载、其他服务没超预算 |
| TEI 容器被 OOM Kill | 2g 内存 limit 对 bge-large 偏紧时，关闭其他临时占内存的进程，或把 limit 提到 2.5g |
| 前端页面正常但一直转圈不出结果 | `docker logs frontend` + 后端 `journalctl -u shopkeeper`；确认后端 8000 已监听（`curl 127.0.0.1:8000/docs`） |
| 前端有进度但卡在中间不动 | nginx 缓冲未关（确认挂载的是 `docker/nginx/frontend.conf` 且容器已重建） |
| 问数报错找不到表/字段 | 元数据知识库没构建成功，重跑步骤 5 |
| MySQL 里没有 dw / meta 库 | 首次启动时初始化脚本失败。修复后需删除卷重建（**会清空数据**）：`docker compose -f docker/docker-compose.server.yaml down -v && docker compose -f docker/docker-compose.server.yaml up -d`，再重跑步骤 5 |

应用日志位于项目根 `logs/` 目录（loguru，10MB 轮转、保留 7 天），带 request_id 可按请求追踪。

## 重启后的恢复

- Docker 基础服务：`restart: unless-stopped`，开机自动拉起；
- 后端：systemd `enable --now` 已设置，开机自动拉起；
- 元数据/索引：持久化在 Docker 卷，无需重建；
- 验证：`docker ps` 五个容器全 Up + `systemctl status shopkeeper` 为 active。

## CI 自动部署（push 即发布）

仓库内置 `.github/workflows/deploy.yml`：push 到 `main` 分支后，GitHub Actions 自动构建前端、把代码与 `frontend/dist` 通过 SSH 同步到服务器、执行 `uv sync`、`docker compose up -d` 并重启后端，最后对 `/docs` 做健康检查。

服务器全程不需要访问 GitHub（构建发生在 Actions Runner 上），适合网络受限的服务器。

使用前需在仓库 **Settings → Secrets and variables → Actions** 添加三个 Secret：

| Secret | 内容 |
| --- | --- |
| `DEPLOY_HOST` | 服务器 IP，如 `1.13.255.225` |
| `DEPLOY_USER` | SSH 用户，如 `ubuntu` |
| `DEPLOY_SSH_KEY` | CI 专用私钥（`ssh-keygen -t ed25519 -f ~/.ssh/shopkeeper_ci -N ""` 生成，公钥追加到服务器 `~/.ssh/authorized_keys`，私钥内容粘贴为 Secret） |

注意事项：

- 同步时会排除 `.env`、`docker/.env`、`docker/embedding`（模型）、`.venv`、`logs`，服务器上的密钥与模型不会被覆盖；
- 每次部署都会重启后端（`systemctl restart shopkeeper`），正在执行的问数查询会被中断；
- 元数据知识库不会被自动重建；修改 `conf/meta_config.yaml` 或 `docker/mysql/*.sql` 后需手动执行步骤 5。
