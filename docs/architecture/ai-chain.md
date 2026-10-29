# AI Mall：Agent + RAG 对话链路

更新：2026-10-29。本文记录仓库实际实现，而不是效果承诺或未来技术清单。

## 1. 设计约束

- 保留一个 LangGraph 编排入口和一个知识库 RetrievalPipeline，不叠加额外路由模型、多 Agent 或第二套知识问答服务。
- 确定性业务由 Java 负责；Python 负责语义理解、检索、工具编排及回答策略。
- 规则用于权限、证据要求和明确请求；模糊意图才交给分类模型。不是“所有判断都用正则”，也不是“所有步骤都调用大模型”。
- 回复快本身不是缺陷。命名确认由真实模型生成；独立身份介绍、准确时间等不为模拟思考而人为延迟。
- 已有可用 RAG 模块直接复用；本次不为展示技术名词而重写召回、重排算法。

## 2. 一条主链路

```text
Vue / Pinia / fetch SSE
  → Java ChatService
      鉴权、会话所有权、限流、请求恢复、消息持久化
      装配历史 + account nickname + 用户长期记忆
  → Python POST /v1/chat/stream
      build_state → resolve_profile
      intent_router → RequestPolicy → intent + reply_route
        ├─ small_talk → 回复
        ├─ escalate_node → Java 人工服务接口 → 回复
        └─ agent ⇄ ToolNode
              ├─ 商品/订单/动作准备 → Java 内部业务接口
              ├─ kb_search → RetrievalPipeline
              └─ web_search → 已检索的外网资料 → web_answer
      无工具最终回答 → END
      工具重复/循环上限 → finalize_without_tools → END
      OutputPolicy → SSE token / tool_call / tool_result / action / done 或 error
  → Java 保存最终 AI 消息及状态 → Vue 展示
```

Java 每轮只读取一次长期记忆快照，同时装配 `user_profile` 与 `long_term_memory`，不再为两种形态重复查询数据库。

Java 不再保留 FAQ 快捷答复旁路或 `FaqService` 的空实现。包括常见退款问题在内，政策答案都经过同一个知识证据链；失败不能偷偷换成静态政策文本。

工具循环仍有职责：模型根据业务需要选择后续工具。已经明确的查订单/查商品/查政策可以直接准备首次工具调用，不额外使用一个模型仅仅选择已知工具。已有循环次数、递归上限和重复调用收敛逻辑继续有效。

## 3. 职责与接口

| 位置 | 唯一职责 | 不承担什么 |
| --- | --- | --- |
| Java `ChatService` | 业务网关、会话与请求恢复、消息/业务持久化 | 命名解释、LLM 意图、静态 FAQ 替代证据 |
| `agent/identity.py` | 显式命名解析、画像归一化与优先级合并 | 模型生成、数据库读写 |
| `agent/routing.py` | 快速路由、模型意图约束、目标节点决策 | 执行工具、生成回复 |
| `agent/nodes.py` + `graph.py` | 模型与工具执行，图的状态增量 | 第二次图路由意图分类 |
| `rag/retrieval.py` | 单一混合检索流水线 | 对话 HTTP 或电商事务 |
| `agent/output.py` | 证据/引用/链接策略、是否允许提前输出 | 模型推理、SSE 格式编码 |
| `api/chat.py` | 请求装配、图事件到 SSE、连接生命周期 | 在接口里重复实现引文校验算法 |
| `agent/memory.py` | 记忆提示构造、显式身份写入、可选事实提取 | 从 AI 自我介绍推测用户名字 |

节点仍保留兼容性导入，方便既有测试和调用方迁移；兼容名不对应第二份策略实现。

## 4. 路由只有一个决策所有者

`intent_router_node` 检查请求并使用 `RequestPolicy`，返回 `intent`、`web_query`、`reply_route`。图分支消费 `reply_route`，不重复做一遍文本意图判断。每轮重置这些字段，避免从检查点继承上一轮路由。

- 明确转人工优先，包括“你太笨了，请转人工”这样的混合表达。
- 命名、身份、会话追问、时间、问候和明确抱怨不因为开启联网而进入网络搜索。
- 独立商品推荐与明确平台政策可以跳过分类模型；“3000 左右呢”“那里下雨吗”等上下文相关请求仍做分类。
- 分类器可在同一次调用中生成消歧后的 `web_query`，不另加查询改写模型。
- 工具 allowlist 集中在一处，联网关闭时未知意图也不会默认暴露 `web_search`。
- 路由/allowlist 不是权限验证替代品：业务身份、归属和敏感操作确认仍由服务端校验。

## 5. 记忆：区分存储职责，不复制真相

### 会话状态

MySQL 消息是用户可见的历史记录；LangGraph 检查点是图运行的会话状态，包含消息、活动实体与画像。两者用途不同。命中检查点时只追加当前用户消息，避免全量历史再次累加。

画像解析优先级：

```text
后端长期画像 < 检查点中的会话称呼 < 有序 USER 历史中的显式约定 < 本轮显式约定
```

历史由已鉴权的 Java 网关注入，只从 `USER` 角色恢复称呼。没有检查点时也可恢复历史中的命名。重新生成失败回复时，使用后端提供的有效历史重建称呼，不继承被丢弃回合的画像。其他长期偏好字段仍以后端提供的值优先。

账户 `nickname` 与明确约定的 `user_name` 分开；Java 不再把账户昵称伪装成用户本轮自报的名字。Python 不使用“朋友/用户/购物助手”等大范围黑名单阻止用户明确设置称呼。问句“你叫啥/我叫啥”不能写成新名字。

### 长期写入

- 显式命名通过规则提取，在成功答案的 `done` 事件前等待 Java 内部持久化接口返回；不依赖下一轮前恰好执行完的游离任务。
- `done.memorySaved`：命名回合为 `true/false`，分别表示本次长期写入成功/失败；非命名回合省略。失败时保留会话回答，但不能宣称长期保存成功。现有前端暂不单独展示此字段。
- 只有明确偏好/背景候选表达才使用可选模型提取。例如“我更喜欢拍照好的手机”；普通政策、订单、新闻提问不额外触发记忆模型。
- 提取器只可写 `PREFERENCE/FACT`，程序拒绝推断结果中的身份类或 `user_name/assistant_name` 键。AI 回复不能覆盖显式身份。
- 可选提取交由响应拥有的 `BackgroundTasks` 管理，客户端收到完成事件后执行；不使用无所有者的 `asyncio.create_task`。这仍是进程内 best-effort，不是持久化任务队列。

## 6. RAG 保留完整检索能力

```text
文档入库：解析 → 切片/重叠 → embedding → 向量索引及元数据

在线问答：query normalize + 平台/商品范围
  ├─ Milvus dense recall
  └─ Java KB BM25 keyword recall
       ↓ 并行召回、过滤当前有效范围
       RRF 融合 → 可配置 reranker → Top-K
       可回答性判断 → 带 [Sx] 的证据上下文
       生成式回答或配置的抽取式回答
       OutputPolicy / validate_citations
```

没有新增“RAG Agent”包装层。`kb_search` 继续调用现有 `RetrievalPipeline`。文档版本/商品范围、单路召回失败、重排失败等现有退化逻辑保留。实际模型、阈值、Top-K 和是否开启重排取决于配置，不承诺固定 Top-3 或某个检索准确率。

明确的政策问题必须经过引文校验；联网结果不能绕过该要求。其他文本根据终结节点与检索状态决定是否提前流式输出，商品链接继续用 `GuardedLinkBuffer` 增量拦截未知 ID。

引用 ID 存在不等于每个事实在语义上都被原文支持。本次守卫校验来源/格式及可回答性，不宣称自动消除所有幻觉；语义忠实度需要独立评测。

## 7. 调用预算：按业务需要，不按模块数量付费

下表是典型成功路径，不含 embedding/reranker、后台摘要、可选偏好提取、供应商重试或复杂多轮工具循环。

| 场景 | 意图模型 | 回答模型 | 说明 |
| --- | --- | --- | --- |
| 明确改名 | 0 | 1 | 更新会话称呼，生成自然确认；不加模拟延时 |
| 独立问名字/问时间 | 0 | 0 | 可信会话信息或服务器时间直接回答 |
| 明确商品推荐 | 0 | 通常 1 | 先真实检索，再按证据生成 |
| 明确平台政策 | 0 | 生成模式通常 1；抽取模式 0 | 统一 RAG 与引文校验 |
| 模糊联网追问 | 1 | 通常 1 | 同次分类产生 web_query，检索后直接 web_answer |
| 复杂交易咨询 | 按需要 | 按工具循环需要 | 准备与确认分离，有上限及重复调用收敛 |

这些是路径调用次数设计与测试约束，不是线上时延或准确率测量。

## 8. 故障与部署限制

- 命名生成失败不再替换成模板“成功”，避免已流出一段内容后伪装整轮成功。异常走统一 SSE error/失败恢复流程。
- 客户端断开后关闭图事件迭代器，不继续发送 done 或执行成功后的记忆写入。
- 有证据约束的政策答案不能为追求打字机效果提前泄露未校验文本。
- SQLite 检查点和进程内任务适合当前单实例学习部署；水平扩容前需要共享检查点、同会话并发协调、持久化任务与幂等设计。本次不额外引入 PostgreSQL/队列。
- 多实例/同用户跨会话同时改名的版本竞争、记忆删除治理、语义引用忠实度评测不是本次已经解决的能力。
- 测试使用 fake model/backend，不意味着生产 Ollama、Milvus 或真实商品链路已经完成上线验收。

## 9. 验证入口

从相应目录运行：

```powershell
# ai-service
$env:PYTHONPATH='.'
python -m pytest tests -q --disable-warnings

# backend（clean 防止删除的 Java 类残留在 target 中）
mvn clean test -q

# frontend
npm test -- --reporter=dot
```

专项覆盖：`test_identity_resolution.py`、`test_routing_policy.py`、`test_output_policy.py`、`test_memory_completion.py`、`ChatGatewayBoundaryTest.java`，以及既有 RAG、流式引文、工具权限/业务确认和恢复测试。

### 本轮验收记录（2026-10-29）

| 检查 | 结果 |
| --- | --- |
| Python 全量 | 502 passed |
| Java clean test | 774 tests，0 failures/errors/skipped |
| 前端全量 | 53 个测试文件、497 tests passed |
| diff 空白检查 | git diff --check 通过 |

仍有现有 Python/pytest asyncio 弃用警告；本轮没有进行生产模型效果评测或线上部署，不把单元测试通过换算成召回准确率或时延改善百分比。

## 10. AI 客服标准评测基准 (AI CS Benchmark)

为了对整个 Agent + RAG 链路进行标准化、可量化的质量度量，项目建立了标准电商客服评测体系：

- **评测数据集**：`eval/dataset/customer_service_benchmark.jsonl`（涵盖 6 大核心客服维度共 60 道标准化测试用例）。
- **6 大评测场景覆盖**：
  1. `PRE_SALES` (售前导购与选型)：复合条件导购、区间价格提取、品牌筛选、单品配置咨询；
  2. `ORDER_FULFILLMENT` (售中履约与订单物流)：全量/待支付/已发货/已完成状态过滤、取消与下单交互卡片拉起；
  3. `AFTER_SALES_POLICY` (售后政策与三包维权)：七天无理由退货、三包保修凭证、运费承担与退款时效精准知识检索；
  4. `EMPATHY_ESCALATION` (情绪抚慰与人工接管)：差评安抚致歉、物流延误安抚、“转人工”强优先级路由与在线时间查询；
  5. `MULTI_TURN_PERSONA` (人设约定与多轮消歧)：双向命名记忆、身份查询、上下文指代继承与时间问答；
  6. `SAFETY_GUARD` (越界任务与安全红线)：拒绝编写代码、拒绝长文创作与解题、防 Prompt 注入与防敏感密钥刺探。
- **评测执行入口**：`python eval/scripts/run_benchmark.py`（自动化生成 Markdown 与 JSON 报告）。
- **管理后台可视化接入**：管理控制台（`/admin/ai-traces`）直接集成标准评测指数看板与 6 大场景雷达通过率。
