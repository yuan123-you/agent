# 知识库与商品检索修复实施计划

> 执行方式：当前会话内按批次 TDD；不创建分支、不提交、不覆盖现有未提交修改。

**目标：** 修复审计 F01–F09 与 L01；同时阻止向量模型静默切换、对搜索候选实时复核。每项先观察失败测试，再最小实现，再跑回归。

## 约束与边界
- 保留当前前端加载状态及其他并行修改，只替换明确定位的片段。
- 不引入新依赖、不对生产环境执行迁移、不修改密钥或本地 .env。
- 置信阈值未经真实数据校准不得降低。BM25 降级仍遵守证据不足拒答，不用扩大误答率换取测试通过。
- 旧集合独有向量不能作为当前集合“已写入”的依据；当前集合缺失的 chunk 从原文重新生成，保留旧集合数据。
- 主 Embedding 模型失败时降级 BM25/SQL，不自动使用其他模型查询/写入原向量空间。手工换模型必须换集合并重建。

## Task 1：固化失败场景
Files: `ai-service/tests/test_retrieval_regressions.py`, `backend/src/test/java/com/aimall/backend/internal/InternalProductFactsTest.java`, `frontend/src/views/ProductDetailView.spec.ts`。
- 将审计隔离复现转为正常测试：空目录、类目、价格、位置指代、引用、多路故障。
- 加入并发引用、有效后失败查询、清理失败、真实商品复核、模型不得切换的测试。
- 商品接口测试实际执行 controller 后断言四项事实；前端挂载真实页面检查无依据声明消失、真实值保留。
- Run: `python -m pytest tests/test_retrieval_regressions.py -q`; `mvn -q -Dtest=InternalProductFactsTest test`; `npm run test -- src/views/ProductDetailView.spec.ts`。先确认 RED。

## Task 2：商品同步、候选约束、指代与实时信息
Files: `ai-service/app/rag/ingest.py`, `app/rag/product_index.py`, `app/tools/tools.py`, `app/api/products.py`。
- 成功空目录发布空语料，清理全部旧向量；失败保留旧语料并返回降级状态。
- rebuild([]) 清理，BM25 小语料/空分词不导致损坏的半发布快照。
- 不静默放宽类目；RRF 合并后用当前商品复验硬类目/价格，再截取候选。
- 一至十位置解析复用到详情和下单，越界/歧义要求明确选择，不默认第一件。
- 混合搜索命中逐件通过现有详情接口读取真实价格/库存/状态，再复验；失败不把缓存伪装成实时结果。
- status 独立报告内存 corpus，不因 Milvus 不可用显示商品数量为零。

## Task 3：请求级知识库引用与故障语义
Files: `ai-service/app/tools/tools.py`, `app/clients/backend_client.py`, `app/rag/vectorstore.py`。
- 每个请求维护唯一 S 编号，复用同 chunk 引用，重写工具 source id，保留历次成功证据；并发完成后不得覆盖。
- 校验服务 error/异常传播给 pipeline，继续 fail-closed，但 reason 区分 unavailable 与合法空集。
- 摄取仅以当前 collection 中存在的 ID 决定跳过生成。

## Task 4：过滤感知召回与完整商品事实
Files: `ai-service/app/rag/retrieval.py`, `app/rag/vectorstore.py`, `app/clients/backend_client.py`, `backend/.../internal/InternalKbController.java`, `InternalToolController.java`, `app/rag/ingest.py`。
- pipeline 向两路传递 doc_type/product_id；SQL 与 Milvus 在 LIMIT 前约束目标商品或通用资料，仍保留 pipeline 防御性过滤。
- 以“21 条其他商品 + 目标商品”的数据验证过滤前推；更新旧测试中“忽略过滤参数”的已废弃约定。
- 详情 DTO、全量 DTO、可检索文本纳入 origin/shipFrom/material/productionDate，不截断真实 description。

## Task 5：商品页面与模型空间安全
Files: `frontend/src/views/ProductDetailView.vue`, `ai-service/app/clients/llm.py`, `ai-service/tests/test_embeddings_fallback.py`, `ai-service/.env.example`。
- 所有缺失事实显示未提供/待确认；不补造标准、承诺、材质或批次，描述缺失显示空态。
- 保留已有页面加载组件和规格字段布局，避免无关改版。
- indexed embedding factory 仅实例化主模型；维度校验仍保留。主模型错误交由已有双路降级处理。

## Task 6：总验收与审计闭环
- AI 全量 pytest；backend 全量 Maven test；frontend 全量 Vitest + build。
- 重跑 docs/audits 的真实模板、真实 Java DTO 探针以及专项；不再保留“预期失败”的过时说明。
- 更新审计报告每项状态、证据、测试数量和环境限制，保留初次发现记录。
- 审阅 git diff，仅交付本次对应文件；不提交或回滚其他任务内容。

## 执行结果（2026-10-27）
- Tasks 1–5 已完成，审计专项转为 `ai-service/tests/test_retrieval_regressions.py` 的 32 个常规回归。
- 已观察原始场景及后续边界测试失败，再实施修复并确认通过。
- 独立复核发现非商品序数误判，追加第三方/第二代、混合问句及模型提示测试后修正。
- Task 6：AI 全量 366 通过；Java 本次 683 通过；原审计 32 通过；真实模板与 DTO 探针通过。前端最后一轮全量与构建结果记录在审计报告的修复闭环章节。
- 置信度校准仍需真实标注数据，不改保守拒答阈值；未进行线上部署或数据迁移。
