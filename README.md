# AI Mall 智能电商平台

[![CI](https://github.com/yuan123-you/agent/actions/workflows/ci.yml/badge.svg)](https://github.com/yuan123-you/agent/actions/workflows/ci.yml)

AI Mall 是一个前后端分离的智能电商项目，由 **Vue 3 前端、Spring Boot 后端和 Python AI Agent 服务**组成。平台覆盖买家、商家、客服和管理员四类角色，并提供商品检索、购物车、地址、下单支付、订单售后、人工接管、知识库 RAG、管理员运营看板和离线评测。

> 本仓库用于开发与演示。默认账号、默认密码和示例密钥只能用于本地环境，部署前必须全部替换。

## 核心能力

- **完整电商链路**：商品浏览、收藏、购物车、地址簿、下单、支付、订单状态与评价。
- **真实商品目录**：2,512 件带来源和采集元数据的商品；512 件替换原种子，2,000 件新增。
- **多角色后台**：商家商品管理、客服工作台、管理员用户/订单/知识库/统计看板。
- **AI 购物助手**：LangGraph 工具循环、SSE 流式输出、`mall://` 站内链接和工具调用卡片。
- **安全业务动作**：取消订单和申请售后必须由买家确认，Agent 不能直接执行高风险动作。
- **混合 RAG**：Milvus 向量召回 + 后端 BM25 + RRF 融合 + 可选 Qwen Reranker。
- **证据与降级**：回答置信度判定、引用校验、旧向量去重、当前文档版本校验以及检索故障降级。
- **人工接管**：转人工、客服抢占接入、等待超时恢复和会话状态同步。
- **质量评测**：离线基线、答案可回答性校准和可选在线 Agent 评测。

## 架构

```text
Browser
  │
  ▼
frontend (Vue 3 + Nginx)
  │ /api
  ▼
backend (Spring Boot 3 / Java 17)
  ├── MySQL 8       业务数据、知识库文档与分块
  ├── Redis 7       缓存与会话辅助
  ├── MinIO         文档和商品图片
  └── SSE ───────────────┐
                         ▼
                 ai-service (FastAPI)
                   ├── LangGraph Agent
                   ├── Milvus 2.4
                   ├── Ollama / OpenAI-compatible API
                   └── Langfuse（可观测性）
```

业务鉴权由后端负责；AI 服务只通过 `/internal/**` 和共享内部令牌访问后端，不应直接暴露到公网。

## 仓库结构

```text
.
├── .github/workflows/ci.yml     # GitHub Actions
├── frontend/                    # Vue 3、TypeScript、Vite、Vitest
├── backend/                     # Spring Boot、MyBatis-Plus、Flyway
├── ai-service/                  # FastAPI、LangGraph、RAG、Agent 工具
├── eval/                        # 离线/在线评测数据与脚本
├── docs/                        # 产品、架构、API、部署与测试文档
├── docker-compose.yml           # 完整本地运行栈
├── CONTRIBUTING.md              # 贡献与提交规范
└── README.md
```

## 环境要求

| 工具 | 建议版本 |
|---|---|
| Docker Desktop / Docker Engine | 支持 Compose v2 |
| Java | 17 |
| Maven | 3.9+ |
| Node.js | 20+ |
| Python | 3.12+ |
| Ollama | 可选；本地 Embedding/Reranker 使用 |

仅使用 Docker 启动时，本机仍需提供可用的 LLM/Embedding 服务，或者把 `ai-service/.env` 配置为云端兼容 API。

## 快速启动：Docker Compose

### 1. 克隆并创建 AI 配置

```bash
git clone https://github.com/yuan123-you/agent.git
cd agent
cp ai-service/.env.example ai-service/.env
```

PowerShell：

```powershell
Copy-Item ai-service/.env.example ai-service/.env
```

至少修改 `ai-service/.env` 中的：

```dotenv
LLM_API_BASE=https://your-provider.example/v1
LLM_API_KEY=replace-me
LLM_CHAT_MODEL=your-chat-model
LLM_INTENT_MODEL=your-intent-model
```

默认 Embedding 和 Reranker 访问宿主机 Ollama：

```bash
ollama pull qwen3-embedding:4b
ollama pull dengcao/Qwen3-Reranker-4B:Q4_K_M
```

如果不用 Ollama，请同时配置 `EMBEDDING_PROVIDER`、`EMBEDDING_API_BASE`、`EMBEDDING_API_KEY`、`EMBEDDING_MODEL` 和正确的 `EMBEDDING_DIM`。

### 2. 设置本地开发密钥并启动

PowerShell 示例：

```powershell
$env:MYSQL_ROOT_PASSWORD = "replace-local-mysql-password"
$env:JWT_SECRET = "replace-with-at-least-64-random-characters"
$env:INTERNAL_TOKEN = "replace-shared-internal-token"
$env:MINIO_ROOT_USER = "replace-minio-user"
$env:MINIO_ROOT_PASSWORD = "replace-minio-password"
docker compose up -d --build
```

Bash 示例：

```bash
export MYSQL_ROOT_PASSWORD='replace-local-mysql-password'
export JWT_SECRET='replace-with-at-least-64-random-characters'
export INTERNAL_TOKEN='replace-shared-internal-token'
export MINIO_ROOT_USER='replace-minio-user'
export MINIO_ROOT_PASSWORD='replace-minio-password'
docker compose up -d --build
```

检查状态：

```bash
docker compose ps
docker compose logs -f backend ai-service
```

默认入口：

| 服务 | 地址 |
|---|---|
| Web 前端 | <http://localhost> |
| 后端 API / Actuator | <http://localhost:8080> |
| Langfuse | <http://localhost:3000> |
| MinIO Console | <http://localhost:9001> |
| Milvus | `localhost:19530` |

停止服务但保留数据：

```bash
docker compose down
```

删除本地容器数据需要显式执行 `docker compose down -v`，请谨慎使用。

## 本地开发

### 基础设施

```bash
docker compose up -d mysql redis minio milvus
```

本地运行 `ai-service` 时，把 `ai-service/.env` 中的以下地址改为 `localhost`：

```dotenv
OLLAMA_BASE_URL=http://localhost:11434
MILVUS_URI=http://localhost:19530
BACKEND_BASE_URL=http://localhost:8080
RERANKER_BASE_URL=http://localhost:11434
```

### AI 服务

```bash
cd ai-service
python -m venv .venv
# Windows: .venv\Scripts\activate
# Linux/macOS: source .venv/bin/activate
pip install -r requirements.txt -r requirements-dev.txt
python -m uvicorn app.main:app --reload --port 8000
```

### 后端

```bash
cd backend
mvn spring-boot:run
```

常用环境变量：`MYSQL_HOST`、`MYSQL_PORT`、`MYSQL_PASSWORD`、`REDIS_HOST`、`AI_SERVICE_BASE_URL`、`INTERNAL_TOKEN`、`JWT_SECRET` 和 MinIO 相关配置。

### 前端

```bash
cd frontend
npm ci
npm run dev
```

开发入口为 <http://localhost:5173>，Vite 会把 `/api` 代理到后端。

## 演示账号

Flyway 初始化后会创建以下本地演示账号，默认密码均为 `123456`：

| 用户名 | 角色 | 默认入口 |
|---|---|---|
| `admin` | 管理员 | `/admin/dashboard` |
| `agent01` | 客服 | `/workbench` |
| `customer01` | 买家 | `/` |
| `merchant01` | 商家 | `/merchant/products` |

生产环境必须关闭或替换种子账号，并设置非默认 `SEED_PASSWORD`。

## 验证与测试

```bash
# 后端
cd backend && mvn -B test

# 前端
cd frontend && npm ci && npm test && npx tsc --noEmit && npm run build

# AI 服务
cd ai-service && pip install -r requirements.txt -r requirements-dev.txt && pytest -q

# 商品目录管线
python -m pytest backend/scripts/tests/product_catalog -q

# Eval
python -m pytest eval/tests -q
python eval/scripts/generate_dataset.py
python eval/scripts/run_eval.py --json

# Docker 配置

docker compose config --quiet
```

GitHub Actions 对 `main` 的 push 和所有 Pull Request 执行后端、前端、AI、Eval 以及 AI 镜像健康检查。

## 商品目录

正式目录位于 `backend/src/main/resources/product-catalog/`，生成与导入工具位于 `backend/scripts/product_catalog/`。

```bash
cd backend/scripts
pip install -r requirements-product-catalog.txt
python generate_product_catalog.py verify --database --minio
python generate_product_catalog.py import --dry-run
# 完成备份并确认报告后：
python generate_product_catalog.py import --apply
```

导入器要求恰好 2,512 条有效记录和 512 个替换槽；使用单事务切换并校验来源键、版本、图片、种子摘要和写入数量。`.catalog-cache`、WARC、虚拟环境与临时输出不会提交。

## 知识库与 RAG

- 正式知识库包含 15 份业务文档，按当前 `600/90` 分块配置约生成 **715 chunks**。
- 向量候选必须通过后端 ACTIVE 状态和当前文档版本校验，旧 collection 仅用于摄取查重。
- BM25 在后端对当前有效分块检索；AI 服务执行 RRF、可选重排、置信度判定和引用输出。
- 任一检索腿或 Reranker 不可用时记录降级原因；证据不足时不允许根据常识补写平台政策。

重新生成确定性知识库资源：

```bash
python backend/scripts/generate_kb_dataset.py
```

评测说明见 [eval/README.md](eval/README.md)。

## 安全与仓库规范

- 不提交 `.env`、API Key、访问令牌、数据库导出、日志、缓存、构建产物或本地工作树。
- `INTERNAL_TOKEN` 必须在 backend 与 ai-service 间一致，并使用随机值。
- 不在公网暴露 AI 服务、MySQL、Redis、Milvus、MinIO 管理端或 Langfuse 管理端。
- 默认密码和 Compose 默认值只用于隔离的本地开发环境。
- 贡献前阅读 [CONTRIBUTING.md](CONTRIBUTING.md)。
- 部署细节见 [部署与运维文档](docs/07-部署与运维文档.md)，测试策略见 [测试方案](docs/08-测试方案.md)。

## 常见问题

| 现象 | 检查项 |
|---|---|
| AI 服务启动失败 | `ai-service/.env` 是否存在；LLM/Embedding 模型、Key 和维度是否匹配 |
| 容器访问不到 Ollama | Ollama 是否监听宿主机；`OLLAMA_BASE_URL` 是否为 `host.docker.internal:11434` |
| 知识库停在处理中 | 查看 `docker compose logs ai-service backend`；检查 Milvus、Embedding 和内部令牌 |
| 商品图片 404 | 检查 MinIO bucket、对象路径及 `/api/v1/product-images/**` 公开读取规则 |
| SSE 中断 | 检查反向代理是否禁用响应缓冲，以及 backend/ai-service 超时设置 |
| Flyway 启动失败 | 不要手改已执行迁移；确认数据库版本和 `flyway_schema_history` |

## 许可证

本项目采用 [Apache License 2.0](LICENSE)。
