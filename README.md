# AI Mall 智能电商平台

[![CI](https://github.com/yuan123-you/agent/actions/workflows/ci.yml/badge.svg)](https://github.com/yuan123-you/agent/actions/workflows/ci.yml)

AI Mall 是面向购物与客服场景的智能电商平台，由 **Vue 3 前端、Spring Boot 业务后端与 Python AI Agent 服务**组成。项目将商品检索、购物车、订单与售后流程同 AI 对话助手连接，并通过知识库检索增强生成（RAG）、用户确认与人工接管，建立从咨询到业务处理的协作链路。

平台覆盖买家、商家、客服和管理员四类角色。业务权限与交易状态由后端校验，AI 服务负责意图理解、工具编排与证据组织，不替代业务系统的授权与决策。

> 本仓库用于开发与演示。部署前必须替换默认凭据，并使用受控的秘密注入机制。

## 导航

- [核心能力](#核心能力)
- [技术架构](#技术架构)
- [环境要求](#环境要求)
- [快速启动](#快速启动docker-compose)
- [本地开发](#本地开发)
- [验证与测试](#验证与测试)
- [知识库与 RAG](#知识库与-rag)
- [部署安全](#部署安全)
- [项目文档](#项目文档)
- [常见问题](#常见问题)

## 核心能力

- **完整电商链路**：商品浏览、收藏、购物车、地址簿、下单、支付、订单状态与评价。
- **带来源的商品数据集**：当前 `products.jsonl` 包含 2,512 条记录，保留来源、图片摘要与采集元数据；交易字段包含模拟数据，不代表实时供应商库存与价格。
- **多角色后台**：商家商品管理、客服工作台、管理员用户/订单/知识库/统计看板。
- **AI 购物助手**：LangGraph 工具循环、SSE 流式输出、`mall://` 站内链接和工具调用卡片。
- **显式业务确认**：AI 下单、取消订单与申请售后先生成准备动作，再通过买家确认接口执行；身份与订单归属由后端校验。
- **混合 RAG**：Milvus 向量召回 + 后端 BM25 + RRF 融合 + 可选 Qwen Reranker。
- **证据与降级**：回答置信度判定、引用校验、旧向量去重、当前文档版本校验以及检索故障降级。
- **人工接管**：转人工、客服抢占接入、等待超时恢复和会话状态同步。
- **质量评测**：离线基线、答案可回答性校准和可选在线 Agent 评测。

### 当前交易与 AI 实现

- `OrderTransition` 定义待支付 → 已支付 / 已取消、已支付 → 已发货、已发货 → 已送达的转换。`OrderService` 按原状态条件更新数据库，取消成功后在事务内回补库存，订单事件在事务提交后发布。
- `pay` 当前实现为校验归属并更新支付状态与时间，没有在该流程调用第三方支付渠道；不应描述为真实资金扣款或结算。
- `AgentOrderActionService` 支持 `ORDER_CREATE`、`ORDER_CANCEL`、`AFTER_SALE_APPLY` 的准备与确认；`OrderActionController` 提供买家侧状态查询、确认与撤销接口。
- LangGraph 图包含意图路由、Agent / 工具循环、闲聊、转人工与强制收敛节点。它是明确的业务工作流，不是任意自主执行交易的通用代理。
- RAG 源码包含候选融合、可回答性判定和引用组织；最终质量仍需真实模型与业务数据验收。

### 角色与场景

| 角色 | 主要场景 |
| --- | --- |
| 买家 | 浏览与检索商品、收藏与购物车、地址管理、下单、订单查询、售后与 AI 咨询 |
| 商家 | 商品维护与商家运营 |
| 客服 | 工作台、会话接入、人工接管与问题处理 |
| 管理员 | 用户、订单、知识库管理与运营统计 |

> 支付能力按当前业务实现理解，不代表已完成第三方支付渠道接入或真实资金结算。离线评测结果也不能直接等同于线上服务质量。

## 技术架构

| 层次 | 技术与职责 |
| --- | --- |
| Web 前端 | Vue 3、TypeScript、Vite、Pinia、Element Plus；多角色页面与流式交互 |
| 业务后端 | Java 17、Spring Boot 3.3.5、MyBatis-Plus、Flyway；鉴权、交易状态与数据库迁移 |
| AI 服务 | Python、FastAPI、LangGraph；意图识别、工具调用、RAG 与流式响应 |
| 数据与文件 | MySQL 8、Redis 7、MinIO；业务数据、缓存与对象存储 |
| 检索增强 | Milvus、BM25、RRF、可选 Reranker；混合召回与证据筛选 |
| 观测与验证 | Langfuse、JUnit、Vitest、pytest、离线 / 在线 Eval |

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
  └── 内部调用 / SSE ───┐
                         ▼
                 ai-service (FastAPI)
                   ├── LangGraph Agent
                   ├── Milvus 2.4
                   ├── Ollama / OpenAI-compatible API
                   └── Langfuse（可观测性）
```

业务鉴权由后端负责；AI 服务只通过 `/internal/**` 和共享内部令牌访问后端，不应直接暴露到公网。取消订单、申请售后等动作先准备，再经买家确认，由业务后端执行。知识库回答须结合当前有效文档与引用；检索失败或证据不足时应明确降级，而不是补写平台规则。

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
| Node.js | 22.22.2+ |
| Python | 本地开发建议 3.12+；AI Docker 镜像使用 3.13 |
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

先在受控环境中配置 `LLM_API_KEY`，并修改 `ai-service/.env` 中的非敏感模型参数：

```dotenv
LLM_API_BASE=https://your-provider.example/v1
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

配置分为两层：`ai-service/.env` 保存模型与 AI 参数；仓库根目录 `.env` 或当前 shell 的环境变量用于 Compose 插值。Compose 的 `environment` 会覆盖 AI 配置中的同名变量（例如内部令牌与容器服务地址）。两种运行方式切换时，应重新核对地址和令牌。

启动前，通过受控环境注入 `MYSQL_ROOT_PASSWORD`、`JWT_SECRET`、`INTERNAL_TOKEN`、`MINIO_ROOT_USER` 与 `MINIO_ROOT_PASSWORD`；在 AI 服务环境中配置 `LLM_API_KEY`。首次启动可能触发模型下载、数据库迁移与知识库摄取，容器启动不代表所有 AI 功能已就绪。


PowerShell 示例：

```powershell
docker compose up -d --build
```

Bash 示例：

```bash
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

以下各服务的命令分别从仓库根目录开始，在独立终端中执行。

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

本机后端不会自动继承 Compose 容器的配置。数据库密码须与启动基础设施时的 `MYSQL_ROOT_PASSWORD` 一致，内部令牌须与本机 AI 服务一致，MinIO 账号也须与容器设置一致。

| 环境变量 | 本地开发用途 |
| --- | --- |
| `MYSQL_HOST` / `MYSQL_PORT` / `MYSQL_DB` | 数据库地址与库名；默认本机 `3306`、`ai_mall` |
| `MYSQL_USERNAME` / `MYSQL_PASSWORD` | 数据库凭据 |
| `REDIS_HOST` / `REDIS_PORT` | Redis 地址；默认本机 `6379` |
| `AI_SERVICE_BASE_URL` | 本机 AI 服务地址，默认 `http://localhost:8000` |
| `INTERNAL_TOKEN` | backend 与 ai-service 共用的内部令牌 |
| `JWT_SECRET` | 用户令牌签名密钥 |
| `MINIO_ENDPOINT` / `MINIO_ACCESS_KEY` / `MINIO_SECRET_KEY` | 文件存储地址与凭据 |

后端配置定义见 `backend/src/main/resources/application.yml`；AI 参数模板见 `ai-service/.env.example`。

### 前端

```bash
cd frontend
npm ci
npm run dev
```

开发入口为 <http://localhost:5173>，Vite 会把 `/api` 代理到后端。

## 账号与凭据管理

账号由授权人员创建、分配或通过受控初始化流程配置。

生产环境必须关闭或替换默认种子凭据。后端与 Compose 支持通过 `SEED_PASSWORD` 显式设置初始化密码。新库存在待初始化种子账号时，未提供该变量会在写入前拒绝初始化；已有账号不随该变量自动重置。数据库、JWT、内部令牌与对象存储凭据不再提供固定兜底值，启动前须通过受控环境配置。

## 验证与测试

下面每个代码块都从仓库根目录开始执行，避免连续 `cd` 导致路径错误。

**后端（JUnit）**

```bash
cd backend
mvn -B test
```

**前端（Vitest、类型检查与构建）**

```bash
cd frontend
npm ci
npm test
npx tsc --noEmit
npm run build
```

**AI 服务（pytest）**

```bash
cd ai-service
pip install -r requirements.txt -r requirements-dev.txt
python -m pytest -q
```

**商品目录与评测工具**

```bash
python -m pytest backend/scripts/tests/product_catalog -q
python -m pytest eval/tests -q
python eval/scripts/generate_dataset.py
python eval/scripts/run_eval.py --json
```

**容器配置检查**

```bash
docker compose config --quiet
```

GitHub Actions 对 `main` / `master` 的 push 和所有 Pull Request 执行后端、前端、AI、Eval 以及 AI 镜像健康检查。具体步骤见 [CI 配置](.github/workflows/ci.yml)。

涉及真实模型、数据库或对象存储的测试，应使用独立的测试配置与数据，避免操作生产数据。

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

- 当前知识库种子清单包含 15 份文档。Compose 的默认分块参数为 `600/90`，实际入库分块数以摄取结果为准。
- 向量候选必须通过后端 ACTIVE 状态和当前文档版本校验，旧 collection 仅用于摄取查重。
- BM25 在后端对当前有效分块检索；AI 服务执行 RRF、可选重排、置信度判定和引用输出。
- 任一检索腿或 Reranker 不可用时记录降级原因；证据不足时不允许根据常识补写平台政策。

重新生成确定性知识库资源：

```bash
python backend/scripts/generate_kb_dataset.py
```

评测说明见 [eval/README.md](eval/README.md)。

## 部署安全

- `INTERNAL_TOKEN` 必须在 backend 与 ai-service 间一致，并使用随机值。
- 不在公网暴露 AI 服务、MySQL、Redis、Milvus、MinIO 管理端或 Langfuse 管理端。
- 部署前更换默认凭据。
- 部署细节见 [部署与运维文档](docs/07-部署与运维文档.md)，测试策略见 [测试方案](docs/08-测试方案.md)。

## 源码索引

| 说明 | 当前实现入口 |
| --- | --- |
| 订单生命周期 | [OrderService](backend/src/main/java/com/aimall/backend/order/OrderService.java)、[OrderTransition](backend/src/main/java/com/aimall/backend/order/OrderTransition.java) |
| AI 动作准备与确认 | [AgentOrderActionService](backend/src/main/java/com/aimall/backend/internal/AgentOrderActionService.java)、[OrderActionController](backend/src/main/java/com/aimall/backend/order/OrderActionController.java) |
| Agent 流程 | [graph.py](ai-service/app/agent/graph.py) |
| RAG 候选与证据 | [retrieval.py](ai-service/app/rag/retrieval.py)、[citations.py](ai-service/app/rag/citations.py) |
| 账号种子初始化 | [SeedDataInitializer](backend/src/main/java/com/aimall/backend/config/SeedDataInitializer.java) |
| 商品资源与知识库清单 | [商品数据集](backend/src/main/resources/product-catalog/products.jsonl)、[知识库 manifest](backend/src/main/resources/kbseed/generated/manifest.json) |
| 运行配置 | [Compose](docker-compose.yml)、[后端配置](backend/src/main/resources/application.yml)、[AI 配置模板](ai-service/.env.example) |

## 项目文档

| 文档 | 内容 |
| --- | --- |
| [产品需求](docs/01-产品需求文档-PRD.md) | 角色、业务场景与功能范围 |
| [系统架构](docs/02-系统架构设计文档.md) | 服务边界与整体设计 |
| [数据库设计](docs/03-数据库设计文档.md) | 数据模型与持久化结构 |
| [API 设计](docs/04-API接口设计文档.md) | 接口与调用约定 |
| [AI Agent 设计](docs/05-AI-Agent设计文档.md) | 工具编排、知识检索与对话流程 |
| [前端设计](docs/06-前端设计文档.md) | 页面与交互设计 |
| [部署与运维](docs/07-部署与运维文档.md) | 环境配置与运行维护 |
| [测试方案](docs/08-测试方案.md) | 分层测试与验收策略 |
| [评测说明](eval/README.md) | 数据集、指标与评测命令 |
| [贡献指南](CONTRIBUTING.md) | 协作与提交规范 |


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

敏感信息回归检查：在仓库根目录运行 `python tests/test_secret_hygiene.py`。该检查不包含已公开 Git 历史的清理，也不意味着既有部署凭据已轮换。
