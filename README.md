# AI Mall 智能电商平台（内含 AI Agent）

前后端分离 + AI 微服务的三层架构：**Vue3 前端（frontend） ↔ SpringBoot 后端（backend） ↔ Python AI 推理服务（ai-service）**。
以传统电商业务为核心（首页轮播/分类导航/楼层推荐/商品/下单/订单，三端响应式），**AI 购物助手作为独立模块**嵌入其中——对话中检索商品/查询订单，回答以**高亮链接**（`mall://` 协议）呈现，点击直达对应页面。

**商品数据**：共 **2,512 件真实商品**（512 件原位替换旧种子 + 2,000 件新增），来自 Apple / Samsung / adidas 等官方公开页面（经 Common Crawl 发现 + 官方页核验），含来源、采集等溯源元数据。**全部列表均为滚动懒加载**（无限加载，无分页器）。

## 真实商品目录（product catalog）

商品目录由 `backend/scripts/product_catalog/` 下的 Python 批量管线生成（确定性、可审计、可重跑）：

- **数据量**：`products.jsonl` 恰好 2,512 件有效商品；`replacement_slot` 1–512 原位更新旧种子，其余为新增。幂等依赖「来源商品唯一键 + 内容哈希」。
- **来源与新鲜度**：来源域名、robots 约束与限速见 [product_sources.json](backend/scripts/product_sources.json)；任何来源/采集时间须 ≥ `2025-01-01T00:00:00Z`，单个来源域名失效时跳过、不终止全量。
- **图片**：最长边 ≤ 1200 px；不透明转 WebP 质量 82、透明转无损 WebP；内容寻址存储（SHA-256 文件名）至 MinIO `aimall-files`，HTTP 访问 `/api/v1/product-images/catalog/{sha}.webp`。
- **模拟字段**：`stock` / `sales` 为确定性模拟并在记录中标注 `commerce_values_simulated=true`，勿当真实经营数据。
- **命令**（`backend/scripts/generate_product_catalog.py`）：
  ```bash
  python generate_product_catalog.py discover --max-domains N --max-records N   # 发现候选（写 .catalog-cache）
  python generate_product_catalog.py build                                        # 标准化/校验/去重 → 2512 清单
  python generate_product_catalog.py upload-images                                # 压缩上传至 MinIO（幂等）
  python generate_product_catalog.py verify --database --minio                    # 导入前全面核验
  python generate_product_catalog.py import --dry-run                             # 事务预检（不落库）
  python generate_product_catalog.py import --apply                               # 单事务：更新512/插入2000
  ```
- **缓存与报告**：`.catalog-cache/` 为中间缓存不入库；审计报告见 [catalog-report.json](backend/src/main/resources/product-catalog/catalog-report.json) 与 [catalog-report.md](backend/src/main/resources/product-catalog/catalog-report.md)（来源/分类计数、图片字节前后对比与节省率、WebP 数量）。
- **恢复**：`import --apply` 单事务执行，任一断言失败整体回滚；重跑幂等，可随时安全重试。

## 架构总览

```
浏览器 ── HTTPS ──> frontend(nginx:80) ──/api 反代──> backend(SpringBoot:8080)
                                                      ├── MySQL 8（业务数据唯一写入方）
                                                      ├── Redis 7（限流/令牌黑名单）
                                                      ├── MinIO（对象存储：知识库源文件）
                                                      └── WebClient(SSE) ──> ai-service(FastAPI:8000，不对外)
                                                                                ├── LLM(OpenAI兼容 API)
                                                                                ├── Milvus 2.4.9（向量库）
                                                                                └── 工具回调 backend /internal/tools/**
```

> **前后端分离**：前端 SPA 仅通过 `/api` 前缀与后端通信（开发期 Vite proxy → localhost:8080，生产期 nginx 反代 → backend:8080），不直连 AI 服务与数据库；backend 与 ai-service 各自独立部署、独立扩容。

核心特性：
- **LangGraph StateGraph Agent**：意图路由 → 购物助理（工具循环）→ 流式回答（禁止 LangChain 0.x / initialize_agent）
- **SSE 五类事件**：`token / tool_call / tool_result / error / done`，前端工具卡片 + 打字机流式渲染
- **AI 高亮链接**：回答中 `[商品名](mall://product/1001)` → 前端白名单渲染为可点击高亮文字 → 跳转商品/订单页；AI 侧 link_guard 后验 + 前端 scheme 白名单双重防护
- **AI 能力**：商品混合检索、订单查询、AI 下单/取消/售后申请（全部先生成买家确认动作）、知识库 RAG（Milvus）、转人工
- **安全红线**：前端永不直连 AI 服务；密钥全部环境变量；AI 服务不碰业务库；WebClient 非阻塞代理 SSE

## 目录结构

```
AI-ServiceDesk/
├── frontend/                 # Vue 3.5 + TS + Vite6 + Element-Plus + Pinia
│   ├── src/
│   │   ├── api/              # axios 封装 + 全量接口
│   │   ├── stores/           # auth / chat（SSE 流式状态）
│   │   ├── composables/      # useSseChat（fetch 流式解析）
│   │   ├── components/
│   │   │   ├── chat/         # AiMessage / ToolCallCard
│   │   │   └── mall/         # StreamBuffer / link.ts（高亮链接渲染）
│   │   ├── views/            # 对话/商品/订单 + admin + workbench
│   │   └── layouts/
│   ├── nginx.conf            # SSE 反代（proxy_buffering off）
│   └── Dockerfile
├── backend/                  # SpringBoot 3.3 + JDK17 + Security6 + MyBatis-Plus
│   └── src/main/java/com/aimall/backend/
│       ├── config/           # JWT/Security/WebClient/熔断/种子密码初始化
│       ├── common/           # 统一响应体/全局异常
│       ├── auth/ product/ order/   # 认证 + 电商业务
│       ├── chat/             # ⭐ SSE 代理（Emitter 管理 + AiClient）
│       ├── kb/               # 知识库管理
│       ├── internal/         # ⭐ AI 工具回调（商品/订单/转人工/文件）
│       ├── workbench/ admin/ # 客服工作台 + 统计/用户管理
│       └── resources/db/init/V1__init.sql   # 建表 + 种子数据
├── ai-service/               # Python 3.13 + FastAPI + LangChain 1.x + LangGraph
│   └── app/
│       ├── agent/            # state / graph / nodes / prompts / link_guard
│       ├── tools/            # 6 个工具（身份 ContextVar 注入）
│       ├── rag/              # Milvus 封装 + 文档摄取链路
│       ├── clients/          # LLM 工厂 + 后端回调客户端
│       └── api/              # chat(SSE) / kb / health
├── docker-compose.yml        # 本地基础设施（MySQL/Redis/MinIO/Milvus；Langfuse 可选）
└── docs/                     # 8 份设计文档（v2.0）
```

## 本地开发（基础设施容器化，应用宿主机运行）

日常开发只将**有状态或第三方基础设施**放入 Docker；前端、后端和 AI 服务在宿主机运行，以获得热更新、断点调试和直接访问本机 Ollama 的体验。三个应用目录中的 `Dockerfile` 仅保留给 CI 或部署使用，不参与本地 Compose 编排。

前置环境：Docker Desktop（Compose v2）、JDK 17 + Maven、Python 3.13、Node.js 20+，以及可选的本机 Ollama。

```powershell
# 1. 启动核心基础设施：MySQL、Redis、MinIO、Milvus
# 默认不会启动 Langfuse，也不会构建三个应用镜像
docker compose up -d

docker compose ps

# 可选：同时启动 Langfuse 及其 PostgreSQL
# docker compose --profile observability up -d
```

首次配置 AI 服务：

```powershell
Copy-Item ai-service/.env.example ai-service/.env
# 编辑 ai-service/.env，至少配置 LLM_API_BASE、LLM_API_KEY 和模型。
# 本地进程使用 localhost 访问 Milvus、backend、Ollama 和可选的 Langfuse。
# INTERNAL_TOKEN 必须与 backend 使用的值一致；本地默认值为 dev-internal-token。
```

分别打开三个终端启动应用：

```powershell
# 终端 1：AI 服务（http://localhost:8000）
Set-Location ai-service
python -m pip install -r requirements.txt
python -m uvicorn app.main:app --reload --port 8000
```

```powershell
# 终端 2：后端（http://localhost:8080）
Set-Location backend
$env:MYSQL_PORT = "3307"  # Docker MySQL 映射到 3307，避开宿主机已有的 3306
$env:MYSQL_PASSWORD = "root123456"
mvn spring-boot:run
```

```powershell
# 终端 3：前端（http://localhost:5173，/api 代理至 backend）
Set-Location frontend
npm install
npm run dev
```

访问 http://localhost:5173 ，演示账号密码均为 `123456`：

| 账号 | 角色 | 入口 |
|------|------|------|
| customer01 | 买家 | `/chat` AI 对话、商品、订单 |
| agent01 | 人工客服 | `/workbench` 工作台 |
| admin | 管理员 | `/admin/*` 商品/订单/知识库/用户/统计 |

> 首次启动 backend 时，Flyway 会自动初始化 MySQL 数据库。停止基础设施使用 `docker compose down`；该命令不会删除数据卷。
## 账号、卖家与管理员运营约定

- 注册页将**买家注册**与**卖家注册**分开：买家使用 `POST /api/v1/auth/register/customer`；卖家使用 `POST /api/v1/auth/register/merchant`，并且必须填写店铺名称；两种注册均可选填手机号。技术接口和令牌中的卖家角色字面量为 `MERCHANT`，所有面向用户的页面文案统一显示为“卖家”。
- 管理员的用户管理按“买家 / 卖家 / 客服”三个标签筛选，标签中不显示管理员；管理员只能在“客服”标签创建人工客服，并且只能启用或禁用用户，**不提供角色转换**。
- 管理后台默认入口为 `/admin/dashboard`。看板以 `Asia/Shanghai` 为“今日”口径；应用 Clock、backend JVM 与 MySQL 默认时区均统一为该时区。看板集中展示平台用户、卖家、在售商品、今日订单/GMV/会话、近 7 日订单与 GMV、订单状态、待人工会话、AI 回复质量、热门问题和工具调用排行。
- 管理员商品管理仅支持新建、列表查询及上/下架，不提供商品编辑；卖家仍可在自己的商品管理页创建、编辑、上/下架或删除自有商品。
## 验证清单（核心链路）

1. admin 登录 → 知识库 → 上传 `退换货政策.md`（类型 POLICY）→ 状态变为「已生效」
2. customer01 登录 → AI 助手 → 发送 **"推荐几款 DIGITAL 给我"**
   - 应看到工具卡片「检索商品」→ 流式回答中**商品名为高亮链接**（真实商品，如 *20W USB-C Power Adapter*）
3. 点击高亮商品名 → 跳转商品详情页（真实商品与价格）→ 立即购买 → 填收货信息 → 模拟支付
4. admin → 订单管理 → 对该订单「发货」（填物流单号）→ 订单变已发货
5. 回到对话发送 **"我的订单到哪了"** → AI 回答订单状态，**订单号可点击**跳转订单详情
6. 发送 **"退货政策是什么"** → kb_search 检索知识库 → 回答引用上传文档内容
7. 发送 **"转人工"** → 会话进入等待人工 → agent01 工作台「接入」→ 双方对话互通
8. admin → 使用统计 → 今日会话/热门问题/工具调用分布

## 平台知识库（AI 客服大脑）

系统内置《AI Mall 平台服务规则知识库》（[platform-policies.md](backend/src/main/resources/kbseed/platform-policies.md)），涵盖：平台基础说明、商品规则（16 分类特殊规则）、订单与支付、物流配送、**7天无理由/15天换货/质保维修完整退换货条款**、售后维权与平台介入、账户安全、违规处理、24 条高频 FAQ、法律法规依据。

- **自动播种**：backend 启动时自动导入并摄取（清库重建后也自动恢复），管理员可在知识库管理页查看/停用/重建
- **双路检索**：向量检索（Milvus）优先；本地 Embedding 不可用时**自动降级关键词检索**（MySQL LIKE + 切词 + 命中排序），知识库始终可用
- **本地 Embedding + Reranker**：默认可使用 Ollama 的 Qwen3 4B Q4_K_M 量化模型；Milvus 使用独立的 1024 维 Qwen3 collection，摄取前查询当前 collection 的 chunk ID，已生成的向量不会重复 Embedding
- **自愈重试**：摄取异常（FAILED/卡住）每 90 秒自动重试，LLM 配置修复后自动恢复向量模式（也可手动"重建索引"）

## Windows Ollama 本地 RAG 模型

模型通过 `D:\Ollama\ollama.exe` 管理，实际模型目录由 `OLLAMA_MODELS` 决定。RTX 3050 4GB 环境使用 Q4_K_M，并把上下文限制为 2048、GPU offload 限制为 10 层，避免默认 40960 上下文启动时内存不足。

```powershell
D:\Ollama\ollama.exe pull qwen3-embedding:4b
D:\Ollama\ollama.exe pull dengcao/Qwen3-Reranker-4B:Q4_K_M
```

- `qwen3-embedding:4b` 当前官方 4B 标签本身就是 **Q4_K_M**，原始输出 2560 维；项目通过 Ollama `dimensions` 参数使用 **1024 维**。
- AI 服务在宿主机运行时通过 `http://localhost:11434` 访问 Windows Ollama；通常无需将 Ollama 暴露到局域网。
- Reranker 对 RRF 候选做二阶段排序；模型不可用或评分失败时自动保留原 RRF 顺序，不影响基本检索。
## 大规模真实业务知识库（Agent + RAG 检索验证）

项目额外内置 15 篇面向真实电商服务流程编写的纯文本业务文档；内容用于 AI Mall 演示业务，不代表其他平台的服务承诺：

- **规模**：15 篇大型文档，共 27.8 万字符，单篇 1.83–1.89 万字符；保持 `chunk_size=600`、`chunk_overlap=90`，实测生成 **715 个 chunks**
- **类型**：POLICY 8、FAQ 4、INTRO 3；全部为便于版本管理和标题感知分块的 Markdown 纯文本，覆盖 15 个电商主题
- **场景**：平台/商家政策、支付发票、会员营销、普通/跨境/冷链/大件物流、售后维权、账户风控及 16 类商品知识
- **检索难例**：口语改写、近义规则、条件与例外、地区/渠道/版本差异、多跳问题和硬负样本
- **受控摄取**：默认每批 2 份、最多 4 份同时处于 PROCESSING；失败或超过 900 秒的任务会自动续跑，不会在启动时瞬间提交全部文档
- **清单同步**：backend 启动时会删除已不在当前 manifest 中的 `seed-synthetic-kb-*` 分块并逻辑删除对应文档，MySQL 与目标数据集保持一致

数据由固定种子的脚本生成，可重复构建：

```bash
python backend/scripts/generate_kb_dataset.py
```

生成清单位于 `backend/src/main/resources/kbseed/generated/manifest.json`，检索标注集位于 `eval/dataset/kb_large_rag.jsonl`。完整摄取会调用约 715 个 chunk 的 Embedding，请先确认模型配额；不需要压力数据时设置 `KB_BULK_SEED_ENABLED=false`。

关键配置：

| 环境变量 | 默认值 | 说明 |
|---|---:|---|
| `RAG_CHUNK_SIZE` | 600 | 中文字符分块上限，标题路径计入长度 |
| `RAG_CHUNK_OVERLAP` | 90 | 相邻正文重叠，约为 15% |
| `KB_INGEST_BATCH_SIZE` | 2 | 每次调度提交数量 |
| `KB_INGEST_MAX_CONCURRENT` | 4 | 新鲜 PROCESSING 文档上限 |
| `KB_INGEST_STUCK_TIMEOUT_SECONDS` | 900 | 卡住任务重试阈值 |
## 常见问题排查

| 症状 | 原因 | 处理 |
|------|------|------|
| AI 回答报 5001/5002 | ai-service 未就绪或 INTERNAL_TOKEN 两端不一致 | 查看运行 Uvicorn 的终端日志；确认 backend 与 ai-service/.env 的 INTERNAL_TOKEN 一致 |
| 知识库文档一直「处理中」 | 摄取失败（LLM Key 无 embedding 权限等） | 查看运行 Uvicorn 的终端日志；确认 EMBEDDING_MODEL/DIM |
| 对话无输出/整段一起出 | Nginx 缓冲 | nginx.conf 已设 `proxy_buffering off`；自建代理需同样配置 |
| 登录 1001 | 密码错误 | 种子密码 123456；或查 `SEED_PASSWORD` 环境变量 |
| 商品链接点击 404 | 商品被下架/删除 | 属预期兜底（路由守卫跳 404） |

## 技术栈版本基线

| 层 | 组件 |
|----|------|
| 前端 | Vue 3.5 / TypeScript 5 / Vite 6 / Element-Plus 2.9 / Pinia 2 / Vue-Router 4 / marked 12 + DOMPurify |
| 后端 | SpringBoot 3.3.x / JDK 17 / Spring Security 6 + JWT(jjwt 0.12) / MyBatis-Plus 3.5.7 / MySQL 8 / Redis 7 / Resilience4j |
| AI 服务 | Python 3.13 / FastAPI / LangChain 1.x / LangGraph 1.x / pymilvus 2.4.15 / pypdf |
| 本地运行 | Docker Compose v2（基础设施）+ Vite / Spring Boot / Uvicorn（宿主机应用） |

设计文档见 `docs/`（8 份，v2.0 电商版）。
