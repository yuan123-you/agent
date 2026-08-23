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
#   EMBEDDING_MODEL / EMBEDDING_DIM（须与模型一致，如 text-embedding-v3 / 1024）
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

## 账号、卖家与管理员运营约定

- 注册页将**买家注册**与**卖家注册**分开：买家使用 `POST /api/v1/auth/register/customer`；卖家使用 `POST /api/v1/auth/register/merchant`，并且必须填写店铺名称。技术接口和令牌中的卖家角色字面量为 `MERCHANT`，所有面向用户的页面文案统一显示为“卖家”。
- 管理员的用户管理按“买家 / 卖家 / 客服”三个标签筛选，标签中不显示管理员；管理员只能在“客服”标签创建人工客服，并且只能启用或禁用用户，**不提供角色转换**。
- 管理后台默认入口为 `/admin/dashboard`。看板以 `Asia/Shanghai` 为“今日”口径，集中展示平台用户、卖家、在售商品、今日订单/GMV/会话、近 7 日订单与 GMV、订单状态、待人工会话、AI 回复质量、热门问题和工具调用排行。
- 管理员商品管理仅支持新建、列表查询及上/下架，不提供商品编辑；卖家仍可在自己的商品管理页创建、编辑、上/下架或删除自有商品。

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
- **自愈重试**：摄取异常（FAILED/卡住）每 90 秒自动重试，LLM 配置修复后自动恢复向量模式（也可手动"重建索引"）

## 大规模合成知识库（Agent + RAG 压力测试）

项目额外内置一套**合成测试数据**，不代表 AI Mall 或任何真实电商平台的服务承诺：

- **规模**：300 份文档，约 618 万字符；使用默认分块参数实测生成 **19,502 个 chunks**
- **类型**：FAQ 120、INTRO 100、POLICY 80；格式包括 MD 240、TXT 50、PDF 10
- **场景**：平台/商家政策、支付发票、会员营销、普通/跨境/冷链/大件物流、售后维权、账户风控及 16 类商品知识
- **检索难例**：口语改写、近义规则、条件与例外、地区/渠道/版本差异、多跳问题和硬负样本
- **受控摄取**：默认每批 2 份、最多 4 份同时处于 PROCESSING；失败或超过 900 秒的任务会自动续跑，不会在启动时瞬间提交 300 份

数据由固定种子的脚本生成，可重复构建：

```bash
python backend/scripts/generate_kb_dataset.py
```

生成清单位于 `backend/src/main/resources/kbseed/generated/manifest.json`，检索标注集位于 `eval/dataset/kb_large_rag.jsonl`。大规模摄取会调用约 1.95 万个 chunk 的 Embedding，请先确认模型配额；不需要压力数据时设置 `KB_BULK_SEED_ENABLED=false`。

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

