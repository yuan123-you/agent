# 文档4：API 接口设计文档

> 项目名称：AI Mall 智能电商平台（内含 AI Agent）
> 文档版本：v2.0
> 最后更新：2026-08-20
> 文档状态：待评审
> 变更说明：v2.0 适配电商业务；接口聚焦主要功能；新增内联链接（mall://）协议规范；移除工单/SLA/质检/通知接口。

---

## 0. 通用约定

### 0.1 接口分组

| 分组 | 调用方 | 前缀 | 鉴权 |
|------|--------|------|------|
| 开放接口 | 前端 | `/api/v1/auth/**` | 无（登录注册） |
| 业务接口 | 前端 | `/api/v1/**` | JWT Bearer |
| SSE 接口 | 前端 | `/api/v1/chat/**`（POST 流式） | JWT Bearer |
| 内部工具接口 | Python AI 服务 → 后端 | `/internal/tools/**` | X-Internal-Token |
| 内部知识接口 | 后端 → Python AI 服务 | `/v1/**`（AI 服务侧） | X-Internal-Token |

### 0.2 统一响应体格式（REST）

```json
{
  "code": 0,
  "message": "success",
  "data": { },
  "traceId": "a1b2c3d4"
}
```

| 字段 | 类型 | 说明 |
|------|------|------|
| code | int | 0=成功；非0见错误码表 |
| message | string | 提示信息（可直接展示） |
| data | object/null | 业务数据 |
| traceId | string | 链路追踪ID |

分页响应 `data` 统一结构：`{ "records": [], "total": 128, "page": 1, "size": 20 }`

### 0.3 时间格式

- 请求/响应时间：`yyyy-MM-dd HH:mm:ss`（东八区）
- 金额：DECIMAL，单位元，两位小数

### 0.4 内联链接协议（mall://，本项目核心约定）

AI 回答正文中以 Markdown 链接语法携带**站内跳转链接**，前端渲染为高亮可点击文字：

| scheme | 格式 | 跳转目标（前端路由） |
|--------|------|---------------------|
| 商品详情 | `[商品名](mall://product/{productId})` | `/products/{productId}` |
| 订单详情 | `[订单号](mall://order/{orderId})` | `/orders/{orderId}` |
| 商品列表 | `[查看手机](mall://products?category=PHONE)` | `/products?category=PHONE` |

**规则**：
1. 仅允许 `mall://` scheme（前端白名单），其余（http/https/javascript 等）一律渲染为纯文本，**不可点击**；
2. 链接中的 id 必须来自工具真实返回结果，AI 禁止编造（Prompt 约束 + 前端兜底校验：目标 id 不存在时路由守卫跳 404）；
3. 链接原文随 token 事件流式透传、随消息落库，历史消息重新渲染同样生效。

---

## 1. 前端 ↔ SpringBoot 接口

### 1.1 认证模块 `/api/v1/auth`

#### POST `/api/v1/auth/register/customer` 买家注册

买家注册的正式接口；请求字段与下表一致，成功响应中 `user.role` 为 `CUSTOMER`。保留 `POST /api/v1/auth/register` 作为兼容入口，语义同买家注册。

#### POST `/api/v1/auth/register` 兼容买家注册

| 参数 | 位置 | 类型 | 必填 | 校验 |
|------|------|------|------|------|
| username | body | string | 是 | 4~32 位字母数字下划线 |
| password | body | string | 是 | 6~32 位 |
| nickname | body | string | 是 | 1~32 位 |
| phone | body | string | 否 | 手机号格式 |

响应 data：`{ "userId": 5, "username": "buyer02", "nickname": "新买家", "role": "CUSTOMER" }`。

#### POST `/api/v1/auth/register/merchant` 卖家注册

请求字段继承买家注册，并新增必填 `shopName`（string，最长 64）。成功响应中 `user.role` 为 `MERCHANT`。`MERCHANT` 为技术契约字面量，页面展示名称必须是“卖家”。

#### POST `/api/v1/auth/login` 登录

body：`{ "username", "password" }`

响应 data：

```json
{
  "accessToken": "eyJhbGciOi...",
  "refreshToken": "eyJhbGciOi...",
  "expiresIn": 7200,
  "user": { "userId": 3, "nickname": "王买家", "role": "CUSTOMER" }
}
```

错误：`1001 用户名或密码错误`（模糊提示防枚举）；`1002 账号已禁用`。

#### POST `/api/v1/auth/refresh` 刷新令牌

body：`{ "refreshToken": "..." }` → 新 accessToken。错误：`1004 刷新令牌无效或过期`。

#### POST `/api/v1/auth/logout` 登出

accessToken 加入 Redis 黑名单（剩余 TTL）。data：null。

#### GET `/api/v1/auth/me` 当前用户信息

data：`{ "userId", "username", "nickname", "role", "phone", "email" }`

### 1.2 商品模块 `/api/v1/products`

#### GET `/api/v1/products` 商品列表（分页+筛选）

| 参数 | 位置 | 类型 | 必填 | 说明 |
|------|------|------|------|------|
| page / size | query | int | 否 | 默认 1/20 |
| keyword | query | string | 否 | 名称/品牌/卖点模糊搜索 |
| category | query | string | 否 | PHONE/LAPTOP/WEARABLE… |
| minPrice / maxPrice | query | decimal | 否 | 价格区间 |
| sort | query | string | 否 | price_asc / price_desc / created_desc（默认） |

只返回 `status=ON_SALE` 商品。data.records：

```json
[{
  "productId": 1001, "name": "星耀 X5 Pro", "brand": "星耀",
  "category": "PHONE", "price": 2999.00, "stock": 50,
  "imageUrl": "/images/x5pro.jpg", "sellingPoints": "5000万像素旗舰影像 大电池 快充"
}]
```

#### GET `/api/v1/products/{id}` 商品详情

data：列表字段 + `description`（介绍富文本/MD）+ `specs`（JSON 参数）。
错误：`2002 商品不存在或已下架`。

### 1.3 订单模块 `/api/v1/orders`

#### POST `/api/v1/orders` 下单（单商品直购）

| 参数 | 位置 | 类型 | 必填 | 校验 |
|------|------|------|------|------|
| productId | body | long | 是 | 商品须上架 |
| quantity | body | int | 是 | 1~99，不超库存 |
| receiverName | body | string | 是 | 收货人 |
| receiverPhone | body | string | 是 | 手机号格式 |
| receiverAddress | body | string | 是 | ≤255 字符 |

响应 data：

```json
{ "orderId": 5001, "orderNo": "SO20260820001", "totalAmount": 2999.00, "status": "PENDING_PAYMENT" }
```

错误：`2005 商品已下架`、`2006 库存不足`。
行为：事务内锁定商品行校验并扣减库存 → 写订单+明细。

#### POST `/api/v1/orders/{id}/pay` 模拟支付

归属校验（仅本人订单，仅 PENDING_PAYMENT 可支付）。data：`{ "status": "PAID", "paidAt": "..." }`

#### POST `/api/v1/orders/{id}/cancel` 取消订单

仅 PENDING_PAYMENT 可取消；事务回补库存。

#### GET `/api/v1/orders/my` 我的订单（分页）

query：`page/size/status`（可空）。

data.records：

```json
[{
  "orderId": 5001, "orderNo": "SO20260820001", "status": "SHIPPED",
  "totalAmount": 2999.00, "source": "USER",
  "items": [{ "productId": 1001, "productName": "星耀 X5 Pro", "quantity": 1, "price": 2999.00, "subtotal": 2999.00 }],
  "logisticsNo": "SF1234567890", "createdAt": "2026-08-20 10:00:00"
}]
```

#### GET `/api/v1/orders/{id}` 订单详情

含完整明细、收货信息、各时间戳（paidAt/shippedAt/deliveredAt）。越权 → 403/2003。

### 1.4 会话与消息模块 `/api/v1/chat`

#### POST `/api/v1/chat/conversations` 创建会话

data：`{ "conversationId": 101, "convNo": "C20260820001", "status": "ACTIVE" }`

#### GET `/api/v1/chat/conversations` 我的会话列表（分页）

data.records：`[{ "conversationId", "title", "status", "messageCount", "updatedAt" }]`

#### GET `/api/v1/chat/conversations/{id}` 会话详情（含摘要）

#### POST `/api/v1/chat/conversations/{id}/close` 关闭会话

#### POST `/api/v1/chat/conversations/{id}/satisfaction` 满意度评价（P1）

body：`{ "score": 5 }`（1~5）

#### GET `/api/v1/chat/conversations/{id}/messages` 历史消息（分页，倒序游标）

data.records：

```json
[{
  "messageId": 5001, "role": "AI",
  "content": "为您找到 3 款：1. [星耀 X5 Pro](mall://product/1001)…",
  "toolCalls": [{"tool": "product_search", "args": {"maxPrice": 3000}, "result": {"total": 3}, "elapsedMs": 120}],
  "status": "SUCCESS", "createdAt": "2026-08-20 10:29:55"
}]
```

> content 中 mall:// 链接原文原样返回，前端渲染逻辑与流式一致。

#### POST `/api/v1/chat/messages` ⭐ 发送消息（SSE 流式，核心接口）

**请求**

| 参数 | 位置 | 类型 | 必填 | 说明 |
|------|------|------|------|------|
| Authorization | header | string | 是 | `Bearer <accessToken>` |
| Accept | header | string | 是 | `text/event-stream` |
| conversationId | body | long | 是 | 归属校验，非本人 403/2003 |
| content | body | string | 是 | 1~4000 字符 |

**响应**：`Content-Type: text/event-stream`，事件五类（完整协议见第 3 节）：

```
event: token
data: {"content": "为您找到"}

event: token
data: {"content": " 3 款符合条件的手机："}

event: tool_call
data: {"callId": "call_1", "tool": "product_search", "args": {"maxPrice": 3000, "keyword": "拍照"}}

event: tool_result
data: {"callId": "call_1", "tool": "product_search", "elapsedMs": 110, "result": {"total": 3, "preview": "星耀X5 Pro/轻语Note14/星耀X5"}}

event: token
data: {"content": "1. [星耀 X5 Pro](mall://product/1001)"}

event: token
data: {"content": " —— 5000 万像素旗舰影像…"}

event: done
data: {"messageId": 5002, "tokenUsage": {"promptTokens": 1520, "completionTokens": 180}, "latencyMs": 3800, "degraded": false}

event: error
data: {"code": 5002, "message": "AI 助手繁忙，请稍后重试或转人工"}
```

**行为约定**
- HTTP 200 即开始流；鉴权/参数错误在建立流之前以普通 JSON 返回。
- 链接语法 `[..](mall://..)` 可能被 token 事件切断（如 `[星耀` 与 ` X5](mall://product/1001)` 分属两个 token），前端缓冲器负责拼接后再渲染（见文档6）。
- 客户端断开：后端 emitter 清理并取消上游订阅。
- 熔断打开：立即返回 error（5002）后结束流。
- done 后连接关闭；AI 消息（含链接原文）已持久化。

### 1.5 客服工作台 `/api/v1/workbench`（AGENT，P1）

| 接口 | 方法 | 路径 | 说明 |
|------|------|------|------|
| 待接入列表 | GET | `/api/v1/workbench/pending` | status=PENDING_HUMAN 会话（含 AI 摘要） |
| 接入会话 | POST | `/api/v1/workbench/conversations/{id}/claim` | 抢占式接管（已被接 → 2004） |
| 人工发送消息 | POST | `/api/v1/workbench/conversations/{id}/messages` | 普通 JSON 响应（非 SSE），role=AGENT |
| 结束服务 | POST | `/api/v1/workbench/conversations/{id}/finish` | 会话 CLOSED，触发满意度评价 |

### 1.6 管理后台 `/api/v1/admin`（ADMIN）

| 接口 | 方法 | 路径 | 说明 |
|------|------|------|------|
| 商品列表 | GET | `/api/v1/admin/products` | 含下架商品，全状态筛选 |
| 创建商品 | POST | `/api/v1/admin/products` | 名称/类目/品牌/价格/库存/卖点/参数/图片；管理员前端不提供编辑 |
| 上架/下架 | POST | `/api/v1/admin/products/{id}/status` | body `{ "status": "OFF_SHELF" }` |
| 订单列表 | GET | `/api/v1/admin/orders` | 全状态筛选，含买家昵称 |
| 发货 | POST | `/api/v1/admin/orders/{id}/ship` | body `{ "logisticsNo": "SF123" }`，仅 PAID 可发 |
| 标记送达 | POST | `/api/v1/admin/orders/{id}/deliver` | 模拟物流终点（或定时任务自动） |
| 知识库文档列表 | GET | `/api/v1/admin/kb/docs` | 状态筛选 |
| 上传知识文档 | POST | `/api/v1/admin/kb/docs` | multipart：file+productId(可空)+title+docType → 异步摄取 |
| 文档详情（轮询） | GET | `/api/v1/admin/kb/docs/{id}` | PENDING→PROCESSING→ACTIVE/FAILED |
| 启用/停用文档 | POST | `/api/v1/admin/kb/docs/{id}/status` | 停用后检索不命中 |
| 重建索引 | POST | `/api/v1/admin/kb/docs/{id}/reindex` | version+1 重建向量 |
| 删除文档 | DELETE | `/api/v1/admin/kb/docs/{id}` | 软删 + 清 Milvus 向量 |
| 用户列表 | GET | `/api/v1/admin/users` | 查询参数 `role` 仅使用 `CUSTOMER`、`MERCHANT`、`AGENT`；管理端标签不包含 ADMIN |
| 创建客服 | POST | `/api/v1/admin/users/agents` | 管理员唯一可创建的账号类型；请求为用户名、密码、昵称及可选手机号 |
| 用户状态更新 | PUT | `/api/v1/admin/users/{id}/status` | body `{ "status": "ACTIVE" | "DISABLED" }`；仅状态变更，不支持角色转换 |
| 数据看板 | GET | `/api/v1/admin/dashboard` | 见下；“今日”及近 7 日时间窗按 `Asia/Shanghai` 计算 |
| 使用统计 | GET | `/api/v1/admin/stats/overview` | P1，见下 |

**数据看板响应 data**：

```json
{
  "summary": { "userCount": 120, "merchantCount": 8, "onSaleProductCount": 90, "todayOrderCount": 12, "todayGmv": 2680.00, "todayConversationCount": 40 },
  "orderTrend": [{ "date": "2026-08-23", "orderCount": 12, "gmv": 2680.00 }],
  "orderStatusDistribution": [{ "status": "PAID", "count": 5 }],
  "operations": { "waitingHumanConversationCount": 2 },
  "aiQuality": { "replySuccessRate": 98.5, "toolCallRatio": 42.0, "avgLatencyMs": 760, "totalTokens": 12000 },
  "topQuestions": [{ "name": "推荐手机", "count": 8 }],
  "toolCalls": [{ "name": "product_search", "count": 6 }]
}
```

指标包括平台用户、卖家、在售商品、今日订单/GMV/会话，近 7 日订单与 GMV、订单状态、待人工会话、AI 回复成功率/工具调用率/平均时延/Token、热门问题与工具调用排行。日期计算统一使用 `Asia/Shanghai`。

**统计响应 data**（P1，极简）：

```json
{
  "todayConversationCount": 356,
  "todayAiMessageCount": 890,
  "topQuestions": [
    { "keyword": "推荐手机", "count": 128 },
    { "keyword": "查订单", "count": 96 }
  ],
  "aiToolCalls": { "product_search": 210, "order_query": 88, "kb_search": 140 }
}
```

---

## 2. SpringBoot ↔ Python AI 服务 内部接口

### 2.1 调用方向与鉴权

- 方向 A（正向）：后端 → AI 服务，Header `X-Internal-Token: <INTERNAL_TOKEN 环境变量>`。
- 方向 B（回调）：AI 服务 → 后端 `/internal/tools/**`，同一令牌。双向校验。
- 网络边界：生产环境 AI 服务 8000 端口不对外映射（Docker 内部网络）。

### 2.2 后端 → AI 服务：对话流 `POST /v1/chat/stream`

**请求**

```json
{
  "conversation_id": 101,
  "user_id": 3,
  "message": "推荐一款3000以内拍照好的手机",
  "history": [
    { "role": "USER", "content": "上次买的手机不错" },
    { "role": "AI", "content": "感谢认可！[星耀 X5 Pro](mall://product/1001)…" }
  ],
  "summary": "买家关注手机品类，预算约3000",
  "user_profile": { "nickname": "王买家" },
  "options": { "temperature": 0.3, "max_history": 10 }
}
```

**响应**：`text/event-stream`，事件协议与「前端↔后端」完全一致（token/tool_call/tool_result/error/done），后端只透传不解析；`done` 事件额外含 `callback_data`（建单结果、转人工标记等）由后端消费后剥离。

### 2.3 后端 → AI 服务：文档摄取（异步任务提交）`POST /v1/kb/ingest`

```json
{
  "doc_id": 12,
  "product_id": 1001,
  "doc_type": "FAQ",
  "doc_version": 1,
  "file_url": "http://backend:8080/internal/files/12",
  "file_format": "PDF"
}
```

响应：`{ "task_id": "ing_abc123", "status": "ACCEPTED" }`（202）。完成/失败后回调后端。

### 2.4 后端 → AI 服务：删除文档向量 `DELETE /v1/kb/docs/{doc_id}`

query：`version`。响应：`{ "deleted": 128 }`。

### 2.5 后端 → AI 服务：健康检查 `GET /health`

响应：`{ "status": "UP", "milvus": "UP", "llm": "UP" }`

### 2.6 后端 → AI 服务：会话摘要压缩 `POST /v1/chat/summarize`（非流式，P1）

```json
{ "old_summary": null, "messages": [ { "role": "USER", "content": "..." }, ... ] }
```
响应：`{ "summary": "买家咨询3000以内拍照手机，已推荐星耀X5 Pro…" }`

### 2.7 AI 服务 → 后端：内部工具回调 `/internal/tools/**`

> 设计要点：回调入参中的 `userId` 由**后端在发起对话请求时注入**并随工具上下文传递；后端回调接口以会话归属为准**二次校验**——即使模型被 Prompt 注入生成他人 userId，服务端也会强制改写为会话归属人。

#### POST `/internal/tools/product/search` 商品检索

请求（AI 服务发起）：

```json
{ "userId": 3, "keyword": "拍照", "category": "PHONE", "minPrice": null, "maxPrice": 3000, "topK": 5 }
```

响应：

```json
{
  "products": [{
    "productId": 1001, "name": "星耀 X5 Pro", "brand": "星耀", "category": "PHONE",
    "price": 2999.00, "stock": 50, "sellingPoints": "5000万像素旗舰影像 大电池 快充",
    "link": "mall://product/1001"
  }],
  "total": 3
}
```

> 后端直接返回 `link` 字段（规范化的 mall:// 链接），供 AI 原样引用，降低模型拼错概率。

#### POST `/internal/tools/product/detail` 商品详情

`{ "userId": 3, "productId": 1001 }` → 详情（含 specs/description 摘要 + link）。下架/不存在返回错误说明。

#### POST `/internal/tools/order/query` 订单查询

`{ "userId": 3, "status": "ALL" }` → 该用户订单摘要列表：

```json
{
  "orders": [{
    "orderId": 5001, "orderNo": "SO20260820001", "status": "SHIPPED",
    "statusText": "已发货", "logisticsNo": "SF1234567890",
    "items": [{ "productId": 1001, "productName": "星耀 X5 Pro", "quantity": 1 }],
    "totalAmount": 2999.00, "createdAt": "2026-08-18 10:00:00",
    "link": "mall://order/5001"
  }]
}
```

#### POST `/internal/tools/order/create` AI 下单（P1）

```json
{
  "userId": 3, "conversationId": 101,
  "productId": 1001, "quantity": 1,
  "receiverName": "王买家", "receiverPhone": "138****5678", "receiverAddress": "…"
}
```

响应：`{ "orderId": 5002, "orderNo": "SO20260820002", "totalAmount": 2999.00, "status": "PENDING_PAYMENT", "link": "mall://order/5002" }`
幂等：conversation_id+消息 幂等键，重复回调返回原订单。收货信息须来自买家本轮明确提供或历史默认（后端校验）。

#### POST `/internal/tools/escalate` 转人工（P1）

`{ "userId": 3, "conversationId": 101, "reason": "买家要求投诉处理" }` → `{ "success": true }`；后端置会话 PENDING_HUMAN。

#### POST `/internal/kb/result` 摄取结果回调

`{ "doc_id": 12, "status": "ACTIVE", "chunk_count": 86 }` 或 `{ "doc_id": 12, "status": "FAILED", "fail_reason": "PDF解析失败：加密文档" }`

#### POST `/internal/kb/chunks/batch` 分块元数据批量落库

`{ "docId": 12, "chunks": [{ "id": 9001, "chunkIndex": 0, "content": "…", "tokenCount": 210 }] }`

---

## 3. SSE 事件协议定义（规范）

### 3.1 传输格式

- `Content-Type: text/event-stream; charset=utf-8`
- 每事件两行：`event: <type>` + `data: <json 单行>`，事件间空行。
- 心跳：后端每 15s 发送注释行 `: ping`（防中间层超时断连）。

### 3.2 五类事件 schema

| 事件 | data 字段 | 说明 |
|------|-----------|------|
| token | `content`(string) | 增量文本片段，可含**未闭合的链接语法片段**，前端拼接后解析 |
| tool_call | `callId`, `tool`, `args`(object) | 工具开始调用（前端展示"正在检索商品…"） |
| tool_result | `callId`, `tool`, `elapsedMs`, `result`(object) | 工具返回（脱敏摘要，供过程可视化） |
| error | `code`(int), `message` | 流中断错误；发送后连接关闭 |
| done | `messageId`, `tokenUsage`, `latencyMs`, `degraded`(bool) | 正常结束标志；随后连接关闭 |

**约束**
1. `tool_call` 与 `tool_result` 通过 `callId` 配对。
2. error 是流的最后一个事件；done 只在成功时出现。
3. 事件顺序保证：单会话内后端按上游顺序透传。
4. `result` 为脱敏摘要（隐藏完整地址/电话），详细数据落库 message.tool_calls。
5. **链接完整性**：单个链接标记（`[..](mall://..)`）可能跨越多个 token 事件，前端负责缓冲拼接到标记闭合后再渲染（协议层不保证单 token 内闭合）。

---

## 4. 全局错误码表

| code | HTTP | 含义 | 触发场景 |
|------|------|------|---------|
| 0 | 200 | 成功 | — |
| 1001 | 401 | 用户名或密码错误 | 登录失败（模糊提示） |
| 1002 | 403 | 账号已禁用 | 登录拦截 |
| 1003 | 401 | 令牌无效或过期 | JWT 过滤器拒绝 |
| 1004 | 401 | 刷新令牌无效 | refresh 接口 |
| 1005 | 429 | 请求过于频繁 | 限流触发（含对话 QPS、登录防爆破） |
| 2001 | 400 | 参数校验失败 | @Valid 失败 |
| 2002 | 404 | 资源不存在 | 商品不存在/会话不存在等 |
| 2003 | 403 | 无权访问该资源 | 越权访问他人订单/会话 |
| 2004 | 409 | 业务状态冲突 | 重复接管会话、非法订单状态流转（支付已支付订单） |
| 2005 | 400 | 商品已下架 | 下单/检索 |
| 2006 | 400 | 库存不足 | 下单 |
| 2007 | 400 | 文件格式不支持 | 知识库上传非 pdf/md/txt |
| 3001 | 500 | 数据库写入失败 | 后端内部异常兜底 |
| 5001 | 502 | AI 服务调用失败 | AI 服务 5xx/超时（SSE error 同码） |
| 5002 | 503 | AI 服务熔断中 | CircuitBreaker OPEN |
| 5003 | 502 | LLM 上游异常 | AI 服务透传 LLM 错误 |
| 9999 | 500 | 系统内部异常 | 兜底（不暴露堆栈） |

> 全局异常处理器保证：非流式接口永远返回统一 JSON；流式接口建流前同上、建流后以 error 事件表达。

---

## 5. 接口安全与幂等补充

| 措施 | 说明 |
|------|------|
| 越权三查 | 会话/订单/用户信息一律 `userId = token.userId` |
| 工具回调防护 | `/internal/**` 仅内网 + 内部令牌；回调 userId 与会话归属强校验 |
| 幂等 | AI 下单以 conversation_id+消息 为幂等键；支付/取消有状态机防重 |
| 文件上传 | 白名单后缀（pdf/md/txt）+ 20MB 上限 + UUID 重命名 |
| 敏感字段 | 响应中手机号统一脱敏（138****5678）；AI 工具回调结果同样脱敏 |
| 库存并发 | 下单走 `SELECT ... FOR UPDATE` 行锁 + 事务，防超卖 |
| 链接安全 | 前端仅渲染 mall:// 白名单 scheme；AI 侧 Prompt 禁止生成外部链接 |

---

> 版本记录
> - v2.1（2026-08-20）：服务模块 gateway 统一更名为 backend，全文术语同步（前后端分离命名）。
> - v2.0（2026-08-20）：适配电商业务；新增 mall:// 内联链接协议（0.4 节）与工具回调 link 字段规范；新增商品/下单/支付/发货接口；SSE 协议补充"链接标记可跨 token"约束；错误码增库存/下架项；移除工单/SLA/质检/通知接口。
> - v1.0（2026-08-20）：智能售后服务平台首版（已废弃）。
