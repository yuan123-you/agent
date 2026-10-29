# 管理后台：AI 链路观测

更新：2026-10-29。覆盖新执行的**单轮对话主链路**，不伪造历史执行数据。

## 使用入口

管理员登录现有控制台，进入 **AI 链路**，前端路由 `/admin/ai-traces`（生产环境沿用应用既有 base path）。

1. 发起一轮新的买家 AI 对话。
2. 管理员刷新列表，可按状态、会话 ID、问题关键词查询。
3. 点击“查看链路”，选择时间线中的步骤，查看输入、输出、执行状态和实际耗时。
4. 后台偏好提取可能晚于主回答结束，稍后“刷新详情”会显示回写的记忆阶段。

列表包含 Trace ID、会话/用户、关联 AI 消息、状态、总耗时、LLM 调用次数、已上报 Token 和步骤数量。状态、数字均来自实际执行；没有返回用量时显示“未返回”，不是估算成零。

## 数据如何到达后台

```text
Java 接收新请求，生成 Trace ID，写入 RUNNING 记录
    ↓ options.trace_id（服务器赋值，模型不能指定）
Python request-local TraceRecorder
    ├─ LangGraph 现有事件：node / model / tool start、end、error
    ├─ 上下文装配、RAG 子阶段、输出校验、记忆写入窄埋点
    └─ 有界、脱敏快照
    ↓ 内部 SSE trace 事件（在 done/error 之前）
Java ChatService 消费并持久化 ai_trace，绝不转发给买家
    ↓ 保存 AI 消息，更新关联 messageId 和最终状态
GET /api/v1/admin/ai-traces
GET /api/v1/admin/ai-traces/{traceId}
    ↓
现有管理后台：列表 + 时间线 + 步骤 JSON 明细
```

可选后台记忆任务完成后，使用现有内部令牌调用 `POST /internal/ai-traces/{traceId}` 更新同一条记录。后台快照只更新明细/计数，不覆盖已经完成的主请求状态、用户或会话归属。

不需要额外启动 Langfuse。原 Langfuse 埋点保持可选，启用时可用 metadata 中的服务器 Trace ID 关联。此功能不增加意图、改写或答案模型调用，只增加诊断收集和数据库写入。

## 可以看到哪些步骤

| 类型 | 可查看数据 |
| --- | --- |
| 上下文装配 | 问题、历史/摘要的有界快照、会话称呼、实体及记忆 |
| 意图与图节点 | 输入状态、分类输出、reply_route、工具规划、开始位置及耗时 |
| LLM 调用 | 实际模型名、公开 prompt/message 内容、公开回答、SDK 返回的 Token 用量 |
| 业务工具 | 工具名、结构化参数、实际结果和错误；不会执行额外业务动作 |
| 查询向量化 | 查询、配置的 embedding 模型、耗时、输出维度；不存储整条高维向量 |
| Milvus 搜索 | collection、范围过滤、Top-K、原始命中与分数 |
| 当前版本校验 | 候选 chunk ID、仍然有效的切片/来源 |
| 混合检索 | Dense 与 BM25 两路输入、命中结果、单路失败状态 |
| RRF / 重排 | 候选 ID、来源、正文片段、词法/向量/RRF/rerank/evidence 分数；未开启的重排明确标记跳过 |
| 可回答性 | 是否有足够证据、理由、来源上下文及引用 ID |
| 输出校验 | 草稿、允许的引用、校验后的回答、引用需求、是否被程序修改 |
| 记忆 | 显式称呼写入结果、可选偏好提取与持久化结果 |

步骤按采集开始顺序排列，保留 parentId 与相对开始时间。并行检索和嵌套节点的耗时**不能简单相加**。列表总耗时由 Java 统计主请求处理时间，步骤耗时由 Python 单调时钟统计；后置记忆任务可能晚于主请求结束，不会人为抬高主请求耗时。

LLM 调用次数不包含 embedding/reranker；后两者在自己的检索阶段中展示。Token 是已上报用量之和，不是价格估算，也不保证每个供应商/失败请求都返回用量。

## 权限、脱敏和体积

- 列表/详情位于现有 `/api/v1/admin/**` ADMIN 权限下。CUSTOMER、MERCHANT、AGENT 均不能读取。
- 后台回写要求 `/internal/**` 的 `X-Internal-Token`，管理员 JWT 也不能代替内部令牌写入。
- Java 生成并绑定 Trace ID、userId、conversationId；快照不能覆盖这些归属字段。
- trace 事件不进入买家 SSE、不进入普通消息正文或恢复重放流。
- 不序列化任意运行时对象，不采集 provider 的 reasoning/thinking/additional_kwargs；文本 think 标签同样脱敏。
- 屏蔽常见口令/令牌键、Bearer、API key、JWT、邮箱和手机号等模式。**自由文本脱敏不是完整 DLP 保证**；这仍属于受限运维数据，不能公开分享数据库或截图。
- 每轮最多保留 96 个步骤；文本与嵌套结构按长度/深度限制，快照阶段数据上限约 240 KB。截断会标记，超限步骤计数在页面显示。
- 列表查询不读取大明细列，分页最大 100 条。权限、SSE 不泄漏、脱敏、体积限制均有专项测试。

## 状态与故障语义

- 正常请求：RUNNING → SUCCESS / DEGRADED；错误、超时、异常 EOF：FAILED。
- 工具以 ToolMessage 返回 error 时，该步骤也标记失败，而非误报成功。
- 失败发生在 AI 服务连接之前，也保留 Java 创建的尝试记录；没有收到的步骤不会被编造。
- 初始化失败会尝试导出失败快照；已经开始但未正常结束的步骤标记失败。
- 进程被强杀或网络中断、数据库本身不可用时，不能保证收到完整快照；未结束记录可能停留在 RUNNING。当前没有后台 watchdog 伪判执行结果。
- 诊断写入采取 best-effort，失败仅记录不含载荷的告警，不阻断正常购物/聊天。
- 快照在请求完成/失败时集中上报，后台偏好提取结束后可补充；**不是逐 Token 实时监控台**。

## 部署与验收

1. 更新 Java 后端、Python AI 服务和前端。
2. 先备份数据库，按既有流程启动后端；Flyway 自动执行 `V19__ai_execution_traces.sql`，创建 `ai_trace` 表与索引。没有改写既有迁移。
3. 确认原有内部令牌配置在 Java 与 Python 中一致。
4. 发起新对话，再以管理员查看。旧历史没有步骤记录，不回填假的 trace。
5. 如需实际线上验收，应覆盖命名、商品推荐、政策 RAG、联网、工具故障及模型服务不可用。

本轮没有改动生产数据库或部署线上服务。数据库迁移已在 H2 MySQL 模式运行验证，权限使用真实安全过滤链测试；这不等于真实生产 MySQL/Ollama/Milvus 端到端验收。

目前以对话为单位记录。离线知识入库、异步历史摘要不在此页面的采集范围。未增加自动清理/导出接口，长期使用需要运营方确定保留周期并归档或清理受限诊断数据。

## 开发验收夹具

`frontend/tests/ai-traces.html` 使用明确标注的合成数据，只运行真实页面组件与交互，不访问业务后端或改变用户登录状态，不随普通生产入口打包。

已检查桌面详情展开、模型输入输出，以及移动端页面宽度。移动端表格在内部滚动，页面本身不横向溢出。截图保存在本地 `docs/qa/ai-traces/`（生成媒体按仓库规则可能被忽略）。

## 关键实现

- Python：`app/observability/execution_trace.py`、`app/api/chat.py`、RAG 与 memory 子阶段。
- Java：`AiTraceService`、`AiTraceController`、`InternalAiTraceController`、`ChatService` 的私有 trace 事件处理。
- Vue：`AiTraceView.vue`、`api/aiTraces.ts`、管理员路由与双端菜单。

## 本轮自动化验收结果

- Python 全量：516 项通过。
- Java clean test：787 项，失败/错误/跳过均为 0。
- 前端全量：54 个文件、502 项通过；新页面/聊天流最终专项 12 项通过；生产构建通过。
- 现有 Python 弃用警告及部分前端第三方构建注解警告仍存在，不影响上述通过结果。
