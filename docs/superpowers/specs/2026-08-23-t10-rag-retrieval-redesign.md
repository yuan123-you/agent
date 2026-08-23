# T10 RAG 检索链路重构设计

**日期：** 2026-08-23  
**状态：** 已通过聊天评审，待书面确认  
**范围：** AI Mall 知识库 `kb_search` 链路；不改变商品检索、订单工具或知识库摄取格式

## 1. 目标

将现有“少量向量结果 + 关键词近似匹配 + 工具层 RRF”重构为可测试、可校准、可替换的检索流水线：

1. query 归一化；
2. 向量 top-20 与标准 BM25 top-20 并行召回；
3. 统一 metadata filter；
4. 按唯一 `chunk_id` 执行 RRF，取 top-10；
5. 可选 reranker，最终取 top-4；
6. 通过校准分数、top1-top2 分差与生成后引用校验判断可回答性；
7. 为模型构造 `<source id="...">` 结构化上下文。

“关键词必须命中”不再是回答条件。单路召回可独立产生可回答结果，最终是否回答由证据分数策略决定。

## 2. 非目标

- 本阶段不部署 reranker 服务，只提供兼容本地 `Qwen/Qwen3-Reranker-4B` 的配置与 HTTP 客户端边界。
- 不引入 Elasticsearch/OpenSearch。
- 不自动修改线上 answerability 阈值。
- 不进行第二次 LLM 引用修复重试。
- 不重构 `product_search`。

## 3. 架构

在 `ai-service/app/rag/` 新增独立 retrieval pipeline。工具层的 `kb_search` 只负责参数接收、调用 pipeline、写入本轮引用状态并返回稳定协议。

流水线由以下可独立测试的单元组成：

- `normalize_query`：无副作用的 query 归一化；
- vector adapter：调用 Milvus 并返回统一候选；
- BM25 adapter：调用后端 BM25 接口并返回统一候选；
- metadata filter：统一执行 `doc_type` 与 `product_id` 规则；
- RRF fusion：严格按 `chunk_id` 融合；
- reranker port/client：可选重排；
- answerability policy：根据最终候选分数判断是否有充分证据；
- citation context builder：构造 source id、XML 上下文和机器可读引用映射；
- citation guard：在生成输出边界验证引用。

候选对象至少包含：

- `chunk_id: int`
- `doc_id: int`
- `product_id: int | None`
- `doc_type: str`
- `content: str`
- `source: str`
- `vector_score: float | None`
- `bm25_score: float | None`
- `rrf_score: float`
- `rerank_score: float | None`
- `evidence_score: float`
- `matched_by: set[str]`

## 4. 检索数据流

### 4.1 Query 归一化

归一化依次执行：

1. Unicode NFKC；
2. 删除无语义控制字符；
3. Latin 字符转小写；
4. 连续空白折叠为单个空格；
5. 去除首尾空白。

不得删除中文停用词、改写数字单位或执行可能改变语义的 query expansion。空 query 直接得到 `invalid_query`，不访问召回服务。

### 4.2 并行双路召回

相同的 normalized query 同时发送至：

- Milvus vector recall，固定 top-20；
- 后端 BM25 recall，固定 top-20。

ACTIVE 状态属于数据有效性约束，必须在存储/召回层强制执行。`doc_type` 和 `product_id` 属于本次查询 metadata filter，在两路 top-20 返回后由 pipeline 统一执行。

任一路异常时继续使用另一腿，并标记降级原因；双路均异常时返回 `retrieval_unavailable`。合法的空结果与服务异常必须区分。

### 4.3 Metadata filter

过滤规则：

- `doc_type` 为空或 `ALL`：不过滤；否则仅保留相同 `doc_type`；
- `product_id` 为空：不过滤；否则保留该商品的 chunk 与平台通用 chunk。平台通用 chunk 使用现有 `product_id=-1` 语义，并兼容后端 `null` 通用值。

过滤不重新排列候选；RRF 使用过滤后列表中的连续 rank。

### 4.4 RRF

对两条过滤后的有序列表执行：

```text
rrf_score(chunk) = sum(1 / (60 + rank_in_leg))
```

rank 从 1 开始。身份键只能是非空 `chunk_id`；缺少 `chunk_id` 的候选不得以正文兜底合并，应丢弃并记录协议错误。相同 chunk 的两腿分数与 `matched_by` 都要保留。按 `rrf_score` 降序、最佳腿 rank、`chunk_id` 执行稳定排序，取 top-10。

### 4.5 可选 reranker

reranker 输入 normalized query 与 RRF top-10 的正文，输出每个 `chunk_id` 对应的 `[0,1]` 相关度分数。成功时按 reranker 分数稳定排序并取 top-4；关闭时直接使用 RRF top-4；开启但超时、返回缺项、重复 id、非法分数或 HTTP 错误时降级为 RRF top-4，并记录 degraded，不中断请求。

HTTP 边界采用可配置 base URL 与 endpoint，默认模型名为 `Qwen/Qwen3-Reranker-4B`，不绑定具体推理框架。客户端请求和响应适配封装在 reranker 模块内，pipeline 不依赖供应商 JSON 细节。

## 5. BM25 后端实现

现有 `/internal/kb/search` 的“LIKE + 命中词数”替换为标准 Okapi BM25：

```text
idf(t) = ln(1 + (N - df(t) + 0.5) / (df(t) + 0.5))
score(D,Q) = sum idf(t) * f(t,D)*(k1+1)
                         / (f(t,D) + k1*(1-b+b*|D|/avgdl))
```

默认 `k1=1.5`、`b=0.75`。中文连续文本使用双字 token；ASCII 使用小写字母数字词 token。query 中重复 token 在评分前去重，防止重复词无意放大权重。

仅 ACTIVE、未删除文档的 chunks 参与 N、DF 与 avgdl 统计。当前语料约 1000 chunks，本阶段允许后端精确内存评分，不增加检索基础设施；BM25 被隔离为可替换组件，后续规模增长可替换实现而不改变 API。

接口最多接受 `topK=20`，返回：`chunk_id`、`doc_id`、`product_id`、`docType`、`content`、`source`、`score`。接口不执行本次请求的 `doc_type/product_id` metadata filter。

## 6. Answerability

answerability 是独立策略，不依赖“关键词腿是否命中”。

### 6.1 Evidence score

- reranker 成功：使用 reranker `[0,1]` 分数；
- 无 reranker：向量原始分数通过 logistic 归一化，BM25 使用 `score/(score+scale)` 归一化；同一候选取可用腿中的最大归一化分数。

默认参数：

```env
RAG_VECTOR_SCORE_CENTER=0.45
RAG_VECTOR_SCORE_SCALE=0.12
RAG_BM25_SCORE_SCALE=8.0
```

这些值只提供初始可运行基线，不代表已跨模型校准。

### 6.2 判定规则

对最终排名 top-4 的前两项计算：

```text
answerable = top1 >= high_confidence
          OR (top1 >= min_score AND top1 - top2 >= min_margin)
```

只有一个候选时，分差条件视为满足。无候选时不可回答。默认：

```env
RAG_ANSWER_MIN_SCORE=0.45
RAG_ANSWER_HIGH_CONFIDENCE_SCORE=0.65
RAG_ANSWER_MIN_MARGIN=0.05
```

未通过时返回 `insufficient_evidence` 和内部 reason，不向模型提供候选正文。

## 7. 引用上下文与输出协议

通过 answerability 后，为最终候选按排名生成本次请求内稳定 id：`S1` 至 `S4`。正文与属性必须 XML 转义：

```xml
<source id="S1" chunk_id="123" title="退换货条款">
七天无理由退货……
</source>
```

工具返回包含：

- `answerable: bool`
- `reason: str`
- `context: str`
- `citations: [{id, chunk_id, title}]`
- `hits`：保留兼容所需的结构化 top-4 信息
- `degraded: bool`
- `degraded_reasons: list[str]`

Prompt 要求模型对每个基于知识库的事实结论使用句末 `[S1]` 形式，只能引用本次 context 中存在的 source id。用户可见结果不得出现 `知识库文档#N` 等内部来源名称。

## 8. 生成期引用校验与流式协议

citation guard 在最终输出边界执行：

- 本轮 `kb_search` 判定不可回答，但模型生成实质性答案：替换为统一证据不足话术；
- 有可回答上下文但答案无 `[Sx]`：`missing_citation`；
- 答案包含不在允许集合中的 `[Sx]`：`unknown_citation`；
- 引用合法：保留正文，并根据实际引用 id 构造去重 citations 列表。

校验失败不重试 LLM，统一返回：

> 当前知识库证据不足，暂时无法可靠回答该问题。

基础设施双路失败使用独立的服务不可用话术，不与证据不足混淆。

为防止已经流出的 token 无法撤回：普通非 RAG 回答保持实时流式；一旦本轮调用 `kb_search`，后续自然语言 token 暂存在服务端，完成 citation guard 后再发送。工具调用和工具结果事件仍实时发送。`token` 拼接结果必须与 `done.content` 完全一致；`done` 额外包含机器可读 `citations`。

## 9. 配置

```env
RAG_VECTOR_RECALL_K=20
RAG_BM25_RECALL_K=20
RAG_RRF_K=60
RAG_RRF_TOP_K=10
RAG_FINAL_TOP_K=4

RAG_ANSWER_MIN_SCORE=0.45
RAG_ANSWER_HIGH_CONFIDENCE_SCORE=0.65
RAG_ANSWER_MIN_MARGIN=0.05
RAG_VECTOR_SCORE_CENTER=0.45
RAG_VECTOR_SCORE_SCALE=0.12
RAG_BM25_SCORE_SCALE=8.0

RAG_RERANKER_ENABLED=false
RAG_RERANKER_MODEL=Qwen/Qwen3-Reranker-4B
RAG_RERANKER_BASE_URL=http://localhost:8001
RAG_RERANKER_ENDPOINT=/v1/rerank
RAG_RERANKER_API_KEY=
RAG_RERANKER_TIMEOUT_S=10
RAG_RERANKER_BATCH_SIZE=10
```

配置模型必须校验：召回和截断值为正，`RAG_FINAL_TOP_K <= RAG_RRF_TOP_K <= 20`，阈值位于 `[0,1]`，scale 和 timeout 大于零。reranker 默认关闭。

## 10. 错误处理与可观测性

| 场景 | 行为 | 用户结果 |
|---|---|---|
| 单路召回异常 | 另一腿继续，degraded | 正常回答或证据不足 |
| 双路召回异常 | `retrieval_unavailable` | 知识库暂不可用 |
| reranker 关闭 | RRF top-4 | 正常，不标 degraded |
| reranker 开启但失败 | RRF top-4，degraded | 正常回答或证据不足 |
| answerability 未通过 | 不暴露正文 | 证据不足 |
| 引用缺失/未知 | 确定性替换 | 证据不足 |

retrieval span 记录 query 摘要、两腿召回数、过滤后数量、RRF/rerank 数量、top 分数、margin、判定原因与降级腿。不得记录 API Key；普通日志不得记录完整文档正文。

## 11. 校准

增加带 `answerable: true/false` 标签的评测数据与 threshold sweep 入口。报告至少包含 precision、recall、F1、拒答率、候选阈值和 margin。脚本只生成报告，不自动修改环境文件或默认配置。上线阈值由人工评审报告后调整。

## 12. 测试与验收

### AI 服务

- query normalization：Unicode、大小写、空白、控制字符、空 query；
- 双路并行与固定 top-20 参数；
- metadata filter 规则与原顺序保持；
- 严格按 `chunk_id` RRF、rank 从 1 开始、top-10、稳定排序；
- 单路降级与双路故障；
- 分数归一化和 answerability 阈值/margin 边界；
- source id 稳定性、XML 转义及 top-4；
- Qwen reranker HTTP 合约、排序及所有降级条件；
- citation guard 的合法、缺失、未知和强制拒答路径；
- RAG token 校验前不外发，最终 token 与 `done.content` 一致。

### 后端

- 中文双字和 ASCII tokenizer；
- 标准 BM25 公式与排序；
- 仅 ACTIVE 文档参与统计；
- topK 上限 20；
- 返回 metadata 字段完整。

### 回归

- AI 服务完整 pytest；
- 后端 Maven 测试；
- 离线 eval 与 answerability calibration 报告；
- 保留当前工作区中阶段 1 的未提交改动，不回滚、不覆盖。

## 13. 验收标准

1. 一次知识库请求严格执行 normalized query → vector 20 + BM25 20 → metadata filter → chunk-id RRF 10 → optional reranker 4。
2. 关键词腿为空时，向量候选仍可通过分数策略成为可回答结果。
3. 任意缺失或伪造 source id 的生成答案不会作为最终正文返回。
4. reranker 默认关闭；配置指向本地 `Qwen/Qwen3-Reranker-4B` 时可启用；失败自动降级。
5. 所有新增单测和既有回归测试通过，阈值校准可离线重放并输出报告。
