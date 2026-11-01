# AI 调用链统一重试与 deadline 验收（2026-11-01）

## 状态与约束

本次补齐的是**当前 AI / RAG / Agent 服务调用链**，不是“所有调用都重试三次”。保留上一阶段未提交的原生中断恢复与质量测评工作；没有部署、切换线上审批链路、创建真实订单/售后/支付或下载模型。

实现依据用户给定的错误分类、Full Jitter、总 deadline、写幂等四项约束。可核查的工程行为与证据列在下面，不据此宣称生产 SLA、分布式 exactly-once 或模型准确率改善。

## 1. 统一机制

核心为 `ai-service/app/resilience.py`；入站约束为 `app/request_budget.py`。

### 分类和重试准入

- 瞬时 HTTP 正向名单：408 / 429 / 500 / 502 / 503 / 504。
- 可重试的网络超时/读写连接故障必须同时满足 `replay_safe=True`。
- TLS 错误、代理/本地协议配置问题、畸形远端 HTTP、401/403、其他永久 4xx、业务拒绝、模型 JSON/维度/结果验证失败不自动重试。
- `RemoteProtocolError` 只允许经当前 httpcore 源码和真实套接字用例核实的 **EOF-before-response** 固定情形。其他协议错误失败关闭，不用模糊异常字符串猜测服务可恢复性。即使是 EOF，也不能证明写操作未执行。
- 模型内容解析与校验在网络重试边界之外。坏答案不靠重新调用模型“刷到通过”。

### Full Jitter 和 Retry-After

普通第 n 次退避（n 从 0 开始）：

```text
cap_n = min(max_delay, base_delay * 2**n)
wait  = uniform(0, cap_n)
```

通用默认 base=0.25s、max_delay=2s、max_attempts=3（**含首次**，不是 3 次额外重试）。原生动作节点沿用独立 base=0.5s，上限仍为 2s，使用同一执行器。

支持 `Retry-After` 秒数与 HTTP-date。把它当作最早重试时间，并在剩余上限内叠加随机等待，避免相同服务端等待指令再次同步所有调用方。若服务端要求超过最大等待，或剩余 deadline 放不下等待及下一次尝试，则停止，不提前重试。

### 总 deadline 与共享重试额度

- 基于单调时钟。进入子调用取 `min(父 deadline, 本地操作 deadline)`，而不是每一层重新给完整时间。
- 每次网络尝试、退避睡眠均受剩余 deadline 约束；传入 HTTP/RPC 的 timeout 同步截断。
- 同一 Python 请求的并行/嵌套任务共享额度账本，默认 **6 次额外尝试**；额度扣减原子化，也覆盖传递到线程的上下文。
- 一次操作只有一个自动重试 owner。嵌套执行器退化成单次尝试，不形成 SDK×工具×业务层乘法。
- 不安全操作一旦进入派发阶段，会标记整个 enclosing attempt。即使它成功后别的读取失败、超时取消或异常被包装，外层也不能重放整个操作。
- 接受 SSE 后绝不自动重新生成。SDK HTTP 传输层同时限制流体的绝对 deadline；持续有 token 也不能无限延长。超时不能伪装成晚到的成功回执。

`RETRY_BUDGET_LIMIT` 表示 retry permits，**不是认证 token**。

## 2. 各调用角色的策略

| 角色 | 自动尝试策略 | 额外保证 |
|---|---|---|
| Chat / intent / 异步 embedding / rerank / summary 模型 HTTP | 至多 3 次，仅瞬时故障 | OpenAI/LangChain SDK `max_retries=0`；共享执行器是 owner；解析错误不重试 |
| 后端读接口（包括显式只读 POST 白名单） | 至多 3 次 | 同一请求的剩余 deadline / permits |
| 带 preparationKey 的动作准备 | 至多 3 次 | 稳定工具调用 ID、数据库唯一约束、参数绑定；重放返回同一动作 |
| 原生动作 execute/cancel | 节点至多 3 次，callback 每次只发 1 次 | 固定 actionId / 已保存决定；原有事务、归属、过期、报价、库存、业务幂等 |
| 旧链路无 key 准备、转人工、记忆写入、chunk 分配及结果写回等 | 单次 | 超时不解释为未执行；不盲目重发 |
| Java 网关、SSE、原生决定、摄取触发 | 单次 | Reactor Netty `disableRetry(true)`；无直接确认回退 |
| Web 搜索 | 每个 provider 单次 | 保留既有、有界 hedge/fallback；不再为每个分支加重试 |
| Milvus 读/写与 bootstrap | 单次应用派发 | 锁定 SDK 边界适配、RPC 剩余 timeout、禁用 Python 内部重试和 channel 重试；写 RPC 不允许内部再次派发 |
| 健康探针 | 单次、零 retry permits | 依赖并行探测，共享 3s 总预算；liveness 不探测依赖 |

同步兼容 LLM/第三方 SDK 工具接口不是当前在线异步链路入口；不能用它们旁路建立“已统一”的新调用。当前 Ollama 同步 embedding 兼容方法桥接到有预算的异步实现。新增 SDK、同步入口或升级依赖必须重新审计重试所有权和 deadline，不假定所有库天然受控。

## 3. 跨服务传播及生命周期

- Java 用单调时钟捕获 deadline；原生 `start + resume/recover` 共用一份 30s 上限，不能各得 30s。
- `X-Request-Timeout-Ms` 是**剩余相对时长**，Java 发出前保留 25ms dispatch reserve。`X-Request-Retry-Budget` 只转发捕获的剩余额度上限。
- Java 仅在 `/internal/**` 通过内部 token 校验后导入预算。浏览器发来的预算头不生效。Python 入站取本地上限，非法预算拒绝；Java/Python 对已过期预算均在进入控制器前拒绝。Java 的 0/1/25ms 预算按 dispatch reserve 拒绝，未触发 execute/cancel；有效零 retry permits 仍可单次执行。
- Python 原生动作默认总预算 15s、单次 callback 上限 3s；包括排队等锁、canonical 读取及图/检查点 await，不靠 HTTP caller 取消去约束被 shield 的 owned task。
- Java chat 默认 180s 的绝对总 deadline，不随 SSE 事件重置；Python chat 取配置值和入站剩余值的较小值。
- 已完成 HTTP 响应的后台任务有明确的新 job 预算，而不是偷偷继续消耗过期前台预算；摄取/商品同步默认 300s，可选记忆任务 30s。它们不是前台请求的自动重试。
- 共享模型 HTTP 池按 event loop 隔离，并由 lifespan 关闭。退出、取消与 deadline 不能撤销已经提交的业务效果，依靠原生检查点及业务幂等恢复。

这不是跨进程共享的全局 token counter：Java 不拥有自动重试，Python 使用请求内共享账本。相对 deadline 也不等于跨主机强制停止时间；下游服务可能已执行，不能据超时断言回滚。

## 4. Milvus 版本边界

生产锁定 `pymilvus==2.4.15` 配合 Milvus 2.4.9。单传 `retry_times=0` 不足以关闭该 SDK 的所有内部路径；numeric timeout、schema-refresh 与 bootstrap 还需单独核实。

适配层不修改全局 SDK 对象；保留 SDK 请求构造/验证、认证/TLS，用 client-local 单次连接适配和受控 channel，创建时明确 `grpc.enable_retries=0`。检查实际 RPC 派发时剩余 timeout，插入/更新/删除不能因 schema refresh 等内部路径再次派发。

部分处理依赖 SDK 私有接口，因此必须锁版本并在升级时重审。离线真实 SDK + stub 不是实际 Milvus 服务联调；不能由单测推导生产兼容性保证。取消 `asyncio.to_thread` 不会杀掉工作线程，真正的 RPC 也必须收到剩余 timeout。

## 5. 实证：本地真实 TCP 故障注入

执行 `python -m eval.retry_evidence`，原始记录保存到 `docs/qa/2026-11-01-retry-evidence.json`。服务仅监听本机临时端口，使用真实 HTTPX/httpcore 套接字，**业务账本是合成内存数据**，无外部模型或生产服务。

| 故障 | 应观察到的物理请求 / 效果 | 诚实结果 |
|---|---|---|
| 读请求 503、503、200 | 3 / 0 | 有界恢复成功 |
| 401 | 1 / 0 | 拒绝，不重试 |
| HTTP 200 但模型 JSON 坏格式 | 1 / 0 | 解析失败，不重新生成 |
| 无幂等写：提交后丢响应 | 1 / 1 | **结果未确认**，不重放、不伪称没执行 |
| 有 key 写：提交后丢响应 | 2 / 1 | 原 key 重试取回同一结果 |
| 3 个并行 root、共享 2 个额外 permits、内部嵌套调用 | 5 / 0 | 不是 9，更不是 27 |
| 200 SSE 已输出一个 chunk 后断开 | 1 / 0 | 失败，不从头重放 |
| 服务端迟答 0.2s，deadline 0.04s | 1 / 0 | 在总预算内终止，不追加请求 |

故障注入使用 base=0.005s、cap=0.01s 的缩短测试参数，避免人为等待；生产默认值见上文，不能把测试时延包装成模型响应 SLA。

本次实际记录共 **15 次物理 HTTP 请求**，0 个残留 handler / 0 个未关闭连接 / 0 个意外服务端错误。表格是验收条件；只有实际观测全部满足，证据 CLI 才输出成功记录。记录包括真实请求序列、扣减额度、裁剪 timeout、jitter 等待、事件及源码/版本指纹；不包含目标地址、密钥、prompt 或业务正文。它不是模型质量指标或生产延迟 SLA。

同一轮重新执行原生子进程崩溃证据，确保统一重试并未破坏 interrupt/checkpoint、固定决定及幂等恢复。历史 RAG live 报告仍对应此前线上版本 `2dbf495`，不能伪称测过本次重试代码。

## 6. 验证和启用门禁

| 本地验证范围 | 结果 |
|---|---:|
| AI 服务全量 | **787 passed** |
| 后端全量 | **868 passed**；0 failures/errors/skips |
| 前端全量 | **580 passed / 58 files** |
| 前端 TypeScript / Vite | 两项退出码均为 **0** |
| eval + 仓库卫生 + 发布配置 + 重排服务 | **121 passed** |
| 锁定 pymilvus 2.4.15 边界审计（临时未安装副本） | **51 passed** |
| 当前本地 pymilvus 2.6.17 边界审计 | **51 passed**，也包含在 AI 全量中 |
| 原生子进程恢复证据 | **verified**；重新生成后包含当前 resilience/engine SHA-256 |
| TCP 故障证据 | 8 场景通过，源码及版本匹配，15 次实际请求 |

独立审查发现并修复：不安全内层写成功/取消/被包装后仍被外层重试、shielded owned operation 只约束等锁、永久 TLS/畸形协议误重试，以及晚到 EOF / 外层 SSE 重放两个边界。均先复现失败，再补回归。

复现（仓库根目录；AI 全量在 ai-service 目录执行）：

```powershell
python -m pytest eval/tests tests deploy/test_action_workflow_config.py deploy/test_reranker_service.py -q
python -m eval.retry_evidence
python -m eval.native_recovery_evidence
# ai-service
python -m pytest tests -q
# repository root
mvn -o -f backend/pom.xml test
# frontend
npm test -- --run
npx --no-install tsc --noEmit
npm run build
```

上述数字来自实际执行输出，不把 targeted suite 与全量重复相加。全量 Python 为当前本地 SDK 2.6.17 环境；锁定 2.4.15 是单独的边界审计，不冒充完整生产依赖环境验证。

- 保留既有购物车“模拟支付”文案静态门禁失败，不修改无关页面，也不声称全仓全绿。
- 上线前需使用隔离环境中的锁定依赖、真实 Java↔Python HTTP 和 Milvus/MySQL 执行故障验收。原生审批开关仍为 false。
- 不承诺取消 JDBC / 磁盘系统调用、杀死服务端已执行操作、全局分布式额度、动态 SDK 升级兼容或多实例 exactly-once。

可准确用于项目材料的表述：**“为 AI/RAG/Agent 调用链实现错误分类、Full Jitter、Retry-After、deadline 与共享重试额度，关闭 SDK/网关叠加重试，并通过真实本地 TCP 故障注入验证幂等写和 SSE 不重放。”** 不扩写成“整个分布式系统所有调用均具备统一强实时取消与 exactly-once 保证”。
