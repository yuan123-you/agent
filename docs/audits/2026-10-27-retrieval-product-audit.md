# 知识库检索与商品信息深度检查（含修复验收）

## 修复闭环：2026-10-27

**状态：F01–F09 与 L01 均已完成代码修复及离线回归验证。未部署生产，也未修改生产数据。**

| 原问题 | 修复结果 | 验证证据 |
|---|---|---|
| F01 商品信息补造 | 缺失字段显示未提供；移除无依据标准、保修、物流/保险承诺、伪造划线价与销量下限；快速预览同类问题一并修复 | 商品详情 53 测试通过；快速预览 3 测试通过；真实模板 SSR PASS |
| F02 引用覆盖/错配 | 请求级唯一 S 编号、工具上下文同步重写、同 chunk 复用、失败不擦除先前成功证据；并发完成不覆盖 | 顺序查询、并发查询与失败追问回归通过 |
| F03 空目录遗留 | 成功空目录立即清 corpus，并清理旧向量；清理服务失败仍维持空语料并标记 degraded | 空目录/清理失败/空 rebuild 回归通过 |
| F04 预算被旧向量绕过 | 截断前用当前语料复验过滤条件；工具层再从业务详情核对价格/库存/在售状态 | 预算 500 不返回 1000 元商品，售罄/下架候选剔除，实时服务故障不伪装合法空目录 |
| F05 静默跨类目 | 删除无命中后取消类目限制的分支 | LAPTOP 查询不再返回 PHONE |
| F06 商品指代错误 | 一至十及最后一款解析；越界、歧义不默认为第一款；详情和下单共用解析 | 第四/第五/最后/越界/歧义及下单指代回归通过 |
| F07 商品事实丢失 | 详情与全量 DTO、检索正文包含产地/发货地/材质/生产日期；保留真实完整描述 | Java 真实 controller 测试及 DTO 探针 PASS |
| F08 故障被吞 | 版本校验错误向上传播，继续 fail-closed，并正确标记检索不可用 | 双路故障与显式失败对照通过 |
| F09 旧集合去重失配 | 摄取只按当前可搜索集合的 ID 跳过生成，旧集合独有 chunk 从原文重建；不删除旧集合 | 旧集合独有向量重新写入当前集合后可搜索 |
| L01 top-20 后过滤漏检 | 请求过滤传入两路；SQL/Milvus 在 LIMIT 前应用商品和文档类型限制，pipeline 仍保留复核 | 第 22 条目标商品资料及 null/-1 通用资料均能保留，Java/Python 双侧验证 |

额外处理：
- 搜索结果发布前并发读取业务详情，不把 600 秒缓存快照冒充实时价格；全部核验失败明确报不可用。
- 商品状态接口直接读取进程 corpus，不再因 Milvus 宕机把已有语料误报为零。
- 独立复核后补充修复“第三方/第二代”被误当商品序号的回归；模型提示同步禁止歧义时猜第一款，并显示全部最多十个缓存位置。
- 索引 Embedding 工厂固定主模型，主模型异常走 BM25/SQL 降级，不自动切换向量空间。通用 fallback 类保留，但不用于共享索引自动换模型。

### 最终验证

| 命令 / 检查 | 结果 |
|---|---|
| AI 服务 `python -m pytest -q --disable-warnings --tb=short` | **366 passed** |
| 后端 `mvn -q test` | **683 tests，65 类，0 failures/errors/skipped** |
| 前端 `npm run test -- --maxWorkers=3` | **332 passed，42 文件通过** |
| 前端 `npm run build` | **生产构建成功** |
| 原审计 Python 入口 | **32 passed**；现复用常规回归测试，不重复维护旧逻辑 |
| 食品商品真实规格模板 | **PASS**，不再补造材质/批次/保修事实 |
| Java 真实 AI 详情 DTO | **PASS**，四个真实字段完整保留 |

后端数量按本次执行生成的报告计数；目录另有前一天遗留的 `p1-red` XML，不属于本次测试。AI 测试仍有既有依赖 warnings 和后台记忆任务退出提示；构建有第三方 PURE 注释告警，均不影响退出码，本次没有顺带修改无关记忆模块或依赖。

### 上线与剩余证据边界

1. 本次是代码与离线执行验收，未做真实模型/真实 Milvus/生产环境端到端验证；不能据此声称线上数据已修复。
2. AI 服务与后端需配套部署，随后同步商品。已经存在的历史旧集合独有/混用模型数据，需要重新摄取相关知识库文档；换 Embedding 模型需换 collection 并全量重建，不能仅以维度相同判断兼容。旧集合未删除。
3. 旧集合独有 chunk 重新摄取时可能产生一次重新向量化成本；已存在于当前集合的向量仍跳过生成。
4. 置信阈值没有为了让简单命中样例通过而调低。原 BM25 分数校准观察仍成立：回答质量/误答率须用真实业务标注评测，当前保留证据不足拒答策略。
5. 保留了工作区其他已有改动；未创建分支、未提交、未部署。

---

## 原始诊断记录（以下为修复前历史，不代表当前状态）

日期：2026-10-27（Asia/Shanghai）
范围：AI 工具入口、商品混合召回与同步、知识库摄取/检索/引用、Java 内部查询接口、商品详情展示。
性质：诊断审计，未修改任何业务代码或现有测试；仅新增本目录的报告与独立复现程序。未调用真实 LLM、后端数据写接口或生产环境。

### 结论与证据边界

确认 9 项功能问题（其中旧索引兼容问题仅在相应配置开启时触发），另有 1 项可复现的召回设计局限。最高优先级是：**商品页面补造事实、多次知识库查询引用错配、全量商品清空后仍推荐旧商品**。

这些结论来自真实函数/接口/模板执行，但外部后端、Embedding、Milvus 使用隔离替身，不等于已经在生产环境复现。Docker daemon 不可用；检查时本机 8000、8080、5173、19530 未监听，因此没有进行真实服务端到端联调。

检查期间前端存在其他工作的并行变更，未修改、回滚或覆盖它们。下面商品信息模板中的硬编码内容在 HEAD 版本也存在，不是将并行加载状态改造误判成新缺陷。

### 验证汇总

| 验证 | 实际结果 | 说明 |
|---|---:|---|
| AI 服务现有全量测试 | 332 passed | pytest；另有 warnings 和后台记忆任务未退出提示，不把它们计为本次检索缺陷 |
| Java 相关测试（9 个测试类） | 55 passed，0 failures/errors | BM25、知识库搜索/版本/事务/内容、商品分页/排序/规格 |
| 前端相关测试（最终复测） | 97 passed，5 个文件通过 | 商品详情、聊天页面、聊天 store、SSE、消息展示 |
| 新增检索专项检查 | 8 failed，4 passed | 8 个失败是针对未修问题的预期红灯；4 个对照检查通过 |
| 真实商品规格模板 SSR | 预期失败，3 项无依据事实 | 食品商品没有材质、生产批次、保修字段，仍展示硬编码事实 |
| 真实 Java AI 商品详情接口 | 预期失败，缺 4 个字段 | Product 实体已赋值，但接口返回 map 丢失这些字段 |

前端第一轮出现 2 个加载状态断言失败；期间存在其他工作的修改。最终复测为 97/97 通过，且监测的 ProductDetailView.vue、对应测试、ChatView.vue、chat store、SSE 源文件在最终测试期间未变化。因此不把第一轮失败登记为尚存检索缺陷。

### 发现

#### F01 / P1：商品详情在信息缺失时自动补造事实

- 位置：`frontend/src/views/ProductDetailView.vue:158-163`、`:488-490`，发货地还涉及 `:75`。
- 真实规格模板对缺字段商品补入：中国、全国智能分仓、阳极氧化铝合金 / 环保亲肤、2026年最新生产，并无条件声明执行标准和 12 个月联保。
- description 为空时，也会填入航空级金属、顶尖性能、七天退换、破损全额包赔等承诺。这不是从商品或政策数据中检索出的事实。
- 复现：渲染一件只有名称/FOOD 类目的“食用面包”，得到：

  `官方正品 食品 中国 全国智能分仓 阳极氧化铝合金 / 环保亲肤 2026年最新生产 GB/T 26572 国家质量标准 支持 12 个月官方正品联保`

- 影响：买家看到伪造的材质、生产批次与售后承诺；这些问题不依赖模型是否幻觉。
- 最小修复方向：无值就隐藏或明确“商家未提供”；平台承诺必须来自明确适用、可信且可维护的数据，不能通用硬编码到所有商品。
- 证据：`product_information_render_20261027.cjs` 执行真实模板表达式，不是只检查字符串。

#### F02 / P1：同轮多次 kb_search 覆盖引用映射，错误引用仍可通过校验

- 位置：`ai-service/app/tools/tools.py:341-347`；引用编号生成见 `app/rag/retrieval.py` 的 `build_source_context`。
- 每次查询都从 S1 开始分配引用，且把 `rag_allowed_citations` 整体覆盖。图允许一轮多工具调用，也可先后查询不同政策。
- 复现：第一次“退货”得到 S1→chunk 101；第二次“保修”得到 S1→chunk 202；随后校验“退货期限为七天[S1]”，校验通过，但来源被指向保修文档 202。
- 影响：不是单纯丢引用，而是出现“看起来有引用、实际引错文档”的答案；最后一次查询若无答案，还会覆盖之前的 answerable 状态。
- 最小修复方向：在请求级别分配不冲突的来源编号，保持工具返回上下文与最终引用映射一致；合并每次检索证据，而不是最后写入覆盖。
- 证据：`test_multiple_kb_calls_must_keep_unique_correct_citations`。

#### F03 / P1：成功同步空商品目录时不清缓存，旧商品可持续被推荐

- 位置：`ai-service/app/rag/ingest.py:218-220`；`app/rag/product_index.py:86-88` 同样忽略空 rebuild。
- 后端成功返回 []，函数直接返回 no products，既不清空进程内 corpus，也不清理旧向量。
- 复现：先让 corpus 有商品 1，再令 products_all 成功返回 []，执行 sync_products；无关键词搜索仍返回商品 1。
- 影响：最后一批商品下架/售罄后，之后每轮“成功但为空”的同步都不能纠正缓存；并不只是正常 10 分钟刷新延迟。
- 最小修复方向：区分“请求失败”和“成功空目录”；后者应发布空语料并执行相应旧向量清理。
- 证据：`test_empty_successful_catalog_sync_must_clear_old_products`。

#### F04 / P2：新语料配旧向量时，硬预算/类目约束没有最终兜底校验

- 位置：`ai-service/app/rag/product_index.py:275-300`；同步顺序见 `app/rag/ingest.py:222` 之后。
- 商品 corpus 先刷新，Embedding/向量同步可能随后失败。向量库中的 price/category 标量与当前 corpus 不一致时，合并后的候选仅检查 ID 存在，不再用当前商品重验过滤条件。
- 复现：旧向量价格 100 元，当前 corpus 价格 1000 元；查询最高 500 元，旧向量命中后最终返回 1000 元商品。
- 最小修复方向：所有召回腿合并后，对当前商品对象重新执行硬过滤，再排序/截断；同步失败应暴露降级状态。
- 证据：`test_stale_vector_scalars_must_not_bypass_current_budget`。

#### F05 / P2：限定类目无命中时偷偷跨类目返回商品

- 位置：`ai-service/app/rag/product_index.py:276-279`。
- 当限定类目无 RRF 结果，代码直接取消 category 重新 BM25 召回，没有区分“用户明确指定”与“系统推断”。
- 复现：请求 LAPTOP + 拍照，类目内无命中时返回 PHONE 的拍照手机。
- 最小修复方向：明确指定的类目不应静默放宽；如需建议其他类目，应单独返回、显式说明并让用户选择。
- 证据：`test_explicit_category_must_not_be_silently_relaxed`。

#### F06 / P2：第四/第五款的详情指代回落到第一款

- 位置：`ai-service/app/tools/tools.py:218-226`。
- 工具默认缓存最多 5 件商品，但缺省 product_id 时只解析第二、第三，其余指代均回落第一件。
- 复现：缓存 ID 101…105，用户问“第四款的参数是什么”，未传显式 product_id，实际调用后端的是 101 而非 104。第二款对照检查正确。
- 边界：若模型显式传了正确 ID，不触发该分支；问题在确定性的 fallback，而不是所有第四款请求必错。
- 同文件 order_create 使用类似逻辑，是后续修复应一起验证的邻接风险，本次未对订单行为作复现结论。
- 最小修复方向：对支持的列表位置统一解析并检查范围；无法解析时澄清，不要默认为第一件。
- 证据：`test_fourth_product_reference_must_not_resolve_to_first`。

#### F07 / P2：AI 商品接口丢失数据库已存在的真实字段

- 位置：`backend/src/main/java/com/aimall/backend/internal/InternalToolController.java:207-224`；全量同步 DTO `:183-201` 也未提供这些字段。
- Product 实体和买家详情接口支持 origin、shipFrom、material、productionDate；AI product_detail 的手写 map 不包含它们，同步文本也没有这些事实。
- 复现：向真实 Product 实体赋齐四个字段，使用 mock mapper 调用真实 controller，返回 map 中四个字段全部缺失。
- 影响：前台有真实参数，但助手通过当前商品工具仍拿不到，无法稳定回答产地、发货地、材质、生产日期问题。
- 最小修复方向：同步扩展 AI 详情 DTO、全量语料 DTO 与 build_product_text；不要求顺带重构其他接口。
- 证据：`ProductInformationProbe20261027.java`。

#### F08 / P2：知识库版本校验服务异常被吞成“证据不足”

- 位置：`ai-service/app/clients/backend_client.py:177-184`；`app/rag/vectorstore.py:81-88`。
- kb_current_chunks 收到后端 error 时返回 {}，向量搜索将全部命中剔除后返回合法空结果，pipeline 不再知道向量腿实际不可用。
- 复现：向量命中 11，但后端 current 校验与 BM25 同时故障；最终 reason 为 insufficient_evidence，降级原因只含 bm25_unavailable，而非 retrieval_unavailable。
- 好的一面：异常时没有放行旧政策，安全侧 fail-closed 是正确的；错误在于故障原因和前端反馈被混淆。
- 最小修复方向：保留 fail-closed，但传播可识别的不可用异常，让 pipeline 区分合法空集与依赖故障。
- 证据：`test_current_chunk_validation_outage_must_be_reported_unavailable`。

#### F09 / P2 / 条件性：旧 collection 中已有向量被跳过，但搜索又不读旧 collection

- 位置：`ai-service/app/rag/ingest.py:123-124`、`app/rag/vectorstore.py:57`、`:94-111`。
- 摄取 existing_ids(include_legacy=True) 会把仅存在旧 collection 的 chunk 标记成已生成，跳过新 collection 写入；搜索却仅访问当前 collection。
- 复现：chunk 101 只在 audit_legacy，摄取结果 ACTIVE/vector_count=0，当前 collection 无写入，向量搜索为空。
- **当前本地 milvus_legacy_collections 为空，此配置下不触发。** 这是兼容性缺陷，不宣称线上正在发生。
- 最小修复方向：明确“复用旧向量”意味着复制到可搜索集合，或兼容搜索旧集合；不可只在去重时认可其存在。
- 证据：`test_legacy_only_vector_must_be_searchable_after_ingest`。

#### L01 / P2 / 设计局限：全局 top-20 后过滤可能把正确答案完全漏掉

- 位置：`ai-service/app/rag/retrieval.py:286-317`；后端 BM25 同样全局先取 top-K。
- 复现：两个召回腿前 20 条全是其他商品，第 21 条才属于 product_id=7；查询商品 7 得到 insufficient_evidence 且 degraded=false。将同一条有效候选放回召回窗口内，对照检查可回答。
- 这是现有 T10 设计文档明确要求的顺序，不是本次实现违反原 spec；但商品/文档规模变大后，确实存在“库里有答案却查不到”的设计性缺口。
- 修正此项需要确认检索设计：硬 metadata filter 前推、过滤感知的召回适配器，或可控的扩窗补召回，而非只调低回答阈值。
- 证据：`test_post_topk_filter_can_starve_an_existing_product_answer`。

### 其他风险观察（不计入以上已确认缺陷）

1. **BM25 降级后的阈值需要真实评测校准。** 本地配置 scale=8、min_score=0.45。真实 Java BM25 对唯一文档“退货期限是七天。”查询“退货期限”给出 raw=0.863046，转换后只有 0.097376，低于回答门槛。虽然命中了文字，纯关键词降级仍可能拒答。这是校准观察，不足以直接决定降低阈值；应使用真实 answerable/unanswerable 数据验证误答率与拒答率。
2. **Embedding fallback 的模型空间一致性。** FallbackEmbeddings 在切模型后仅记录需重建索引的 warning；维度相同不等于可以混用旧索引与新 query 向量。没有验证实际模型切换，故只登记为条件性风险，不宣称当前向量已混用。
3. **价格/库存新鲜度。** 本地商品同步间隔配置 600 秒，搜索直接返回 corpus 快照；即使无上述缺陷，也不能把搜索结果当实时成交数据。商品详情/下单应以业务库重新读取的结果为准。

### 修复顺序建议

1. F01、F02、F03：先解决无依据事实、引用错配、已不可售商品泄漏。
2. F04、F05、F06、F07：保证约束、指代、商品事实字段完整一致。
3. F08、F09：恢复准确的故障语义与旧索引兼容能力。
4. L01：确认检索设计后再实现，配合真实知识库规模与降级评测。

本轮没有修复上述问题，不能将“原有测试全部通过”解释为“功能没有问题”。

### 当前重跑方式

#### Python 专项（修复后：32 passed，退出码 0）

```powershell
Set-Location 'D:\studyAgent\AI Mall\ai-service'
python -m pytest ../docs/audits/retrieval_checks_20261027.py -q --disable-warnings --tb=short
```

该文件刻意置于 docs/audits，不会混入 ai-service/pytest.ini 的常规 tests 目录发现。

#### 前端真实规格模板（修复后：PASS，退出码 0）

```powershell
Set-Location 'D:\studyAgent\AI Mall'
node docs/audits/product_information_render_20261027.cjs
```

#### Java 真实 AI 详情 DTO（先运行相关 Maven 测试，修复后：PASS，退出码 0）

```powershell
Set-Location 'D:\studyAgent\AI Mall'
[xml]$x = Get-Content backend/target/surefire-reports/TEST-com.aimall.backend.internal.Bm25RetrieverTest.xml
$cp = ($x.testsuite.properties.property | Where-Object name -eq 'java.class.path').value
java -cp $cp docs/audits/ProductInformationProbe20261027.java
```

#### 原有测试实际执行命令

AI 服务目录：

```powershell
python -m pytest -q --disable-warnings
```

backend 目录：

```powershell
mvn -q '-Dtest=Bm25RetrieverTest,InternalKbSearchTest,InternalKbControllerVersionTest,InternalKbIngestTransactionTest,KbServiceContentTest,KbAdminControllerContentTest,ProductSearchPaginationTest,ProductSearchSortingTest,ProductSpecsValidationTest' test
```

frontend 目录：

```powershell
npm run test -- src/stores/chat.spec.ts src/composables/useSseChat.spec.ts src/components/chat/AiMessage.spec.ts src/views/ProductDetailView.spec.ts src/views/ChatView.spec.ts
```
