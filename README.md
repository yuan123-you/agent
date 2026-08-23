# AI Mall 智能电商平台（内含 AI Agent）

前后端分离 + AI 微服务的三层架构：**Vue3 前端（frontend） ↔ SpringBoot 后端（backend） ↔ Python AI 推理服务（ai-service）**。
以传统电商业务为核心（首页轮播/分类导航/楼层推荐/商品/下单/订单，三端响应式），**AI 购物助手作为独立模块**嵌入其中——对话中检索商品/查询订单，回答以**高亮链接**（`mall://` 协议）呈现，点击直达对应页面。

**商品数据**：16 大分类（手机数码/电脑办公/家用电器/服饰内衣/美妆个护/食品生鲜/母婴玩具/运动户外/图书文娱/家具家居/珠宝饰品/箱包/鞋靴/宠物生活/医疗保健/汽车用品）共 **512 件**种子商品（每类 20 基础款 + 12 变体款）。**全部列表均为滚动懒加载**（无限加载，无分页器）。

## 架构总览

```
浏览器 ── HTTPS ──> frontend(nginx:80) ──/api 反代──> backend(SpringBoot:8080)
                                                      ├── MySQL 8（业务数据唯一写入方）
                                                      ├── Redis 7（限流/令牌黑名单）
                                                      ├── MinIO（对象存储：知识库源文件）
                                                      └── WebClient(SSE) ──> ai-service(FastAPI:8000，不对外)
                                                                                ├── LLM(OpenAI兼容 API)
                                                                                ├── Milvus 2.5(向量库)
                                                                                └── 工具回调 backend /internal/tools/**
```

> **前后端分离**：前端 SPA 仅通过 `/api` 前缀与后端通信（开发期 Vite proxy → localhost:8080，生产期 nginx 反代 → backend:8080），不直连 AI 服务与数据库；backend 与 ai-service 各自独立部署、独立扩容。

核心特性：
- **LangGraph StateGraph Agent**：意图路由 → 购物助理（工具循环）→ 流式回答（禁止 LangChain 0.x / initialize_agent）
- **SSE 五类事件**：`token / tool_call / tool_result / error / done`，前端工具卡片 + 打字机流式渲染
- **AI 高亮链接**：回答中 `[商品名](mall://product/1001)` → 前端白名单渲染为可点击高亮文字 → 跳转商品/订单页；AI 侧 link_guard 后验 + 前端 scheme 白名单双重防护
- **AI 能力**：商品推荐（SQL 结构化检索）、订单查询/AI 下单（回调后端，身份服务端注入）、知识库 RAG（Milvus）、转人工
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
├── docker-compose.yml        # 九服务编排（mysql/redis/minio/milvus/ai-service/backend/frontend/langfuse-db/langfuse，ai-service 不对外映射）
└── docs/                     # 8 份设计文档（v2.0）
```

## 快速启动（Docker Compose 一键）

前置：Docker Desktop（含 Compose v2）。

```bash
# 1. 配置环境变量（密钥）
cp ai-service/.env.example ai-service/.env
# 编辑 ai-service/.env，必填：
#   LLM_API_BASE / LLM_API_KEY / LLM_CHAT_MODEL / LLM_INTENT_MODEL
#   EMBEDDING_PROVIDER / OLLAMA_BASE_URL / EMBEDDING_MODEL / EMBEDDING_DIM
#   INTERNAL_TOKEN（与下方 compose 环境保持一致）

# 2. 一键启动（可自定义 MYSQL_ROOT_PASSWORD / JWT_SECRET / INTERNAL_TOKEN / MINIO_ROOT_USER / MINIO_ROOT_PASSWORD / MINIO_BUCKET）
docker compose up -d --build

# 3. 查看状态（全部 healthy 即成功）
docker compose ps
```

访问 http://localhost ，演示账号（密码均为 `123456`，启动时自动重置）：

| 账号 | 角色 | 入口 |
|------|------|------|
| customer01 | 买家 | `/chat` AI 对话、商品、订单 |
| agent01 | 人工客服 | `/workbench` 工作台 |
| admin | 管理员 | `/admin/*` 商品/订单/知识库/用户/统计 |

> 首次启动 MySQL 会自动执行 `V1__init.sql`（8 张表 + 5 件种子商品）。

## 本地开发（前后端分离，基础设施容器化）

```bash
# ① 只起中间件（Milvus 镜像内置 etcd/MinIO，无需单独起）
docker compose up -d mysql redis minio milvus langfuse-db langfuse

# ② AI 推理服务
cd ai-service
cp .env.example .env    # MILVUS_URI 默认 localhost:19530，BACKEND_BASE_URL 默认 localhost:8080
pip install -r requirements.txt   # 或 uv venv && uv pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000

# ③ 后端（dev 默认连 localhost）
cd backend
mvn spring-boot:run     # JWT_SECRET/INTERNAL_TOKEN 可用默认 dev 值

# ④ 前端（Vite proxy /api → localhost:8080）
cd frontend
npm install
npm run dev             # http://localhost:5173
```

## 验证清单（核心链路）

1. admin 登录 → 知识库 → 上传 `退换货政策.md`（类型 POLICY）→ 状态变为「已生效」
2. customer01 登录 → AI 助手 → 发送 **"推荐一款3000以内拍照好的手机"**
   - 应看到工具卡片「检索商品」→ 流式回答中**商品名为高亮链接**（如 *星耀 X5 Pro*）
3. 点击高亮商品名 → 跳转商品详情页（价格 2999）→ 立即购买 → 填收货信息 → 模拟支付
4. admin → 订单管理 → 对该订单「发货」（填物流单号）→ 订单变已发货
5. 回到对话发送 **"我的订单到哪了"** → AI 回答订单状态，**订单号可点击**跳转订单详情
6. 发送 **"退货政策是什么"** → kb_search 检索知识库 → 回答引用上传文档内容
7. 发送 **"转人工"** → 会话进入等待人工 → agent01 工作台「接入」→ 双方对话互通
8. admin → 使用统计 → 今日会话/热门问题/工具调用分布

## 平台知识库（AI 客服大脑）

系统内置《AI Mall 平台服务规则知识库》（[platform-policies.md](backend/src/main/resources/kbseed/platform-policies.md)），涵盖：平台基础说明、商品规则（16 分类特殊规则）、订单与支付、物流配送、**7天无理由/15天换货/质保维修完整退换货条款**、售后维权与平台介入、账户安全、违规处理、24 条高频 FAQ、法律法规依据。

- **自动播种**：backend 启动时自动导入并摄取（清库重建后也自动恢复），管理员可在知识库管理页查看/停用/重建
- **双路检索**：向量检索（Milvus）优先；Embedding 不可用（如 DeepSeek Key 无 embeddings 接口）时**自动降级关键词检索**（MySQL LIKE + 切词 + 命中排序），知识库始终可用
- **本地 Embedding + Reranker**：默认可使用 Ollama 的 Qwen3 4B Q4_K_M 量化模型；Milvus 按模型/维度使用独立 collection，摄取前同时查询当前与 legacy collection 的 chunk ID，已生成的向量不会重复 Embedding
- **自愈重试**：摄取异常（FAILED/卡住）每 90 秒自动重试，LLM 配置修复后自动恢复向量模式（也可手动"重建索引"）

## T10 RAG 固定检索与引用流程

`kb_search` 对每个请求严格按以下固定顺序执行，不以关键词命中作为回答前提：

1. query 归一化（NFKC、控制字符清理、Latin 小写、空白折叠）；
2. 使用同一 normalized query 并行执行 Milvus vector top-20 与后端 BM25 top-20；
3. 对两路结果统一执行 `doc_type` / `product_id` metadata filter；
4. 仅按唯一 `chunk_id` 做 RRF（`k=60`），稳定排序并截取 top-10；
5. 可选 HTTP reranker 重排，随后截取最终 top-4；关闭时直接使用 RRF top-4；
6. 将 reranker 分数（或归一化后的 vector/BM25 分数）用于 answerability：`top1 >= high_score`，或 `top1 >= min_score` 且 `top1 - top2 >= min_margin`；
7. 仅在可回答时，按最终排名构造 `S1` 至 `S4` 的 XML source context；
8. 模型生成后在输出边界执行 citation guard，通过后才向客户端发送 RAG 自然语言 token 与 `done.content`。

上下文块使用 `<source>`，例如：

```xml
<source id="S1" chunk_id="123" title="退换货条款">
七天无理由退货……
</source>
```

模型对知识库事实必须使用句末 `[S1]` 形式，且只能引用本次 `<source id="S1">` 上下文中存在的 ID。缺少引用或出现未知 `[S#]` 时不重试模型，也不会泄漏原回答；citation guard 会确定性替换为“当前知识库证据不足，暂时无法可靠回答该问题。”并返回空 citations。answerability 未通过时同样不向模型提供候选正文。

降级行为是确定的：单个召回腿异常时保留另一腿并标记 `degraded`；两腿都异常时返回独立的“知识库暂时不可用”结果；reranker 关闭不算降级，开启后若超时、HTTP/协议/评分失败则保留 RRF top-4、记录 `reranker_unavailable` 并继续 answerability 判断。单元测试使用替身，不要求 Milvus、后端 BM25、reranker 或其他网络服务。

answerability 与 evidence normalization 的当前默认值如下；它们只是**未经校准的可运行基线**，并不代表跨模型最优值：

```env
RAG_ANSWER_MIN_SCORE=0.45
RAG_ANSWER_HIGH_CONFIDENCE_SCORE=0.65
RAG_ANSWER_MIN_MARGIN=0.05
RAG_VECTOR_SCORE_CENTER=0.45
RAG_VECTOR_SCORE_SCALE=0.12
RAG_BM25_SCORE_SCALE=8.0
```

校准命令和 JSONL schema 见 [eval/README.md](eval/README.md)；其报告只写显式 `--output`，绝不修改应用配置或 `.env`。

本地 `Qwen/Qwen3-Reranker-4B` HTTP 边界由以下字段配置（默认关闭，不绑定具体推理框架）：

```env
RAG_RERANKER_ENABLED=false
RAG_RERANKER_MODEL=Qwen/Qwen3-Reranker-4B
RAG_RERANKER_BASE_URL=http://localhost:8001
RAG_RERANKER_ENDPOINT=/v1/rerank
RAG_RERANKER_API_KEY=
RAG_RERANKER_TIMEOUT_S=10
RAG_RERANKER_BATCH_SIZE=10
```

## Windows Ollama 本地 RAG 模型

模型通过 `D:\Ollama\ollama.exe` 管理，实际模型目录由 `OLLAMA_MODELS` 决定。RTX 3050 4GB 环境使用 Q4_K_M，并把上下文限制为 2048、GPU offload 限制为 10 层，避免默认 40960 上下文启动时内存不足。

```powershell
D:\Ollama\ollama.exe pull qwen3-embedding:4b
D:\Ollama\ollama.exe pull dengcao/Qwen3-Reranker-4B:Q4_K_M
```

- `qwen3-embedding:4b` 当前官方 4B 标签本身就是 **Q4_K_M**，原始输出 2560 维；项目通过 Ollama `dimensions` 参数使用 **1024 维**。
- Windows Ollama 必须监听 `0.0.0.0:11434`，容器通过 `http://host.docker.internal:11434` 访问。
- Reranker 对 RRF 候选做二阶段排序；模型不可用或评分失败时自动保留原 RRF 顺序，不影响基本检索。
- `MILVUS_LEGACY_COLLECTIONS` 只用于 chunk ID 查重，不把不同 Embedding 模型的向量混入同一次相似度检索。
## 大规模合成知识库（Agent + RAG 压力测试）

项目额外内置一套**合成测试数据**，不代表 AI Mall 或任何真实电商平台的服务承诺：

- **规模**：15 份分层抽样文档，约 30.9 万字符；保持 `chunk_size=600`、`chunk_overlap=90`，实测生成 **970 个 chunks**
- **类型**：FAQ 6、INTRO 5、POLICY 4；格式包括 MD 12、TXT 2、PDF 1，覆盖 15 个不同电商主题
- **场景**：平台/商家政策、支付发票、会员营销、普通/跨境/冷链/大件物流、售后维权、账户风控及 16 类商品知识
- **检索难例**：口语改写、近义规则、条件与例外、地区/渠道/版本差异、多跳问题和硬负样本
- **受控摄取**：默认每批 2 份、最多 4 份同时处于 PROCESSING；失败或超过 900 秒的任务会自动续跑，不会在启动时瞬间提交全部文档

数据由固定种子的脚本生成，可重复构建：

```bash
python backend/scripts/generate_kb_dataset.py
```

生成清单位于 `backend/src/main/resources/kbseed/generated/manifest.json`，检索标注集位于 `eval/dataset/kb_large_rag.jsonl`。完整摄取会调用约 970 个 chunk 的 Embedding，请先确认模型配额；不需要压力数据时设置 `KB_BULK_SEED_ENABLED=false`。

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
| AI 回答报 5001/5002 | ai-service 未就绪或 INTERNAL_TOKEN 两端不一致 | `docker compose logs ai-service`；对比 ai-service/.env 与 compose 环境变量 |
| 知识库文档一直「处理中」 | 摄取失败（LLM Key 无 embedding 权限等） | `docker compose logs ai-service` 查 ingest 报错；确认 EMBEDDING_MODEL/DIM |
| 对话无输出/整段一起出 | Nginx 缓冲 | nginx.conf 已设 `proxy_buffering off`；自建代理需同样配置 |
| 登录 1001 | 密码错误 | 种子密码 123456；或查 `SEED_PASSWORD` 环境变量 |
| 商品链接点击 404 | 商品被下架/删除 | 属预期兜底（路由守卫跳 404） |

## 技术栈版本基线

| 层 | 组件 |
|----|------|
| 前端 | Vue 3.5 / TypeScript 5 / Vite 6 / Element-Plus 2.9 / Pinia 2 / Vue-Router 4 / marked 12 + DOMPurify |
| 后端 | SpringBoot 3.3.x / JDK 17 / Spring Security 6 + JWT(jjwt 0.12) / MyBatis-Plus 3.5.7 / MySQL 8 / Redis 7 / Resilience4j |
| AI 服务 | Python 3.13 / FastAPI / LangChain 1.x / LangGraph 1.x / pymilvus 2.5 / pypdf |
| 部署 | Docker Compose v2（frontend:80 / backend:8080 对外，ai-service 仅内网） |

设计文档见 `docs/`（8 份，v2.0 电商版）。


