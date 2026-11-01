# 原生动作恢复与质量证据（2026-11-01）

## 发布状态与范围

- 工作分支：`codex/native-agent-recovery`，基线 `b81128a`；本次实现未推送/部署，未启用线上动作确认工作流。
- 两端 `ACTION_WORKFLOWS_ENABLED` 默认 `false`。上线不能只开一端；原生动作遇到不可用检查点、网关错误或关停开关均 fail closed，不降级到模型/旧工具直接确认。
- 面向 `ORDER_CREATE`、`ORDER_CANCEL`、`AFTER_SALE_APPLY` 的独立动作图；普通咨询不因一个待确认动作而冻结。
- 这是原生 LangGraph 中断/恢复，不是 SSE 重连、重新生成回答、或自动重发确认请求。也不承诺所有聊天节点的恢复、分布式 HA 或框架自带 exactly-once。

## 实现与信任边界

```text
服务端注入 tool_call_id → preparationKey → 后端提交不可变动作快照/准备响应
  → 原生图 START → review/interrupt → 等待人工
  → 买家确认接口 → Command(resume=固定决定/收货信息)
  → 同步持久化决定 → execute_decision → 既有后端事务/幂等检查 → END
```

- 使用真实 `AsyncSqliteSaver`，独立 `data/action-workflows/checkpoints.db`；`durability="sync"`。审批图不允许 MemorySaver 回退。
- SQLite 检查点挂载持久卷，仅支持单 AI 实例。检查点含收货信息，不进镜像、不进 Git；需按私密业务数据备份和限制访问。Windows `chmod` 不等同于已完成 NTFS ACL/磁盘加密。
- 后端 V20 持久化 native provenance（包括被采纳的旧 pending 动作），GET 状态明确返回 `nativeManaged`。历史重载不能把缺省字段当作旧链路，也不能拿 domain CONFIRMED 和旧收货地址冒充原生完成回执。
- 绑定 `(userId, conversationId, actionId, type, fingerprint)`；模型参数不提供身份/确认结果。只有后端鉴权后的买家接口可提交决定。
- 审阅节点在 `interrupt()` 前无业务副作用；恢复不接受结果、不生成批准、不替换已保存决定/收货信息。
- 一次工具调用用框架注入的稳定 ID 准备动作；唯一键与参数指纹防止节点/工具重放产生重复动作。
- 后端仍检查归属、会话、过期、报价、数量、库存及售后状态；幂等落点为原有 actionId 事务。AI 网络调用不持有业务数据库事务。
- 后续统一重试补齐后，执行节点复用统一 Full Jitter 执行器（base=0.5s、max_delay=2s、最多3次含首次），不再叠加 LangGraph RetryPolicy 与 HTTP/SDK 重试。支持 Retry-After、总 deadline、请求内共享额度；业务拒绝/协议验证错误不自动重试。当前机制与真实 TCP 验收见 `2026-11-01-unified-retry-budget.md`，下方原生阶段测试数保留为该阶段记录。
- 前端区分等待、执行、恢复、失败与过期。只在可信完整回执后显示成功；恢复按钮不发送新的 approve/reject 或本地表单，收货信息取服务端最终订单回执。

## 真实进程崩溃证据

原始记录：`docs/qa/2026-11-01-native-recovery-evidence.json`。

复现：在仓库根目录运行 `python -m eval.native_recovery_evidence`。
该工具剥离进程凭证环境，只使用真实 LangGraph/SQLite 和**合成幂等业务账本**，不联网、不调用模型、不创建实际订单。

| 阶段 | 原生检查点观察 | 合成业务 effect / 调用次数 |
|---|---|---:|
| 第一个进程 start | 真正的 review interrupt，未决定 | 0 / 0 |
| 新进程 approve 后强制 `os._exit(73)` | 在业务提交后、图执行结果返回前死亡 | 1 / 1 |
| 重启 inspect | 已保存 approve；下一节点 execute_decision | 1 / 1 |
| 新进程 recover | COMPLETED，下一节点为空 | 1 / 2 |
| 再次 recover | 使用已有完成结果，无重复业务调用 | 1 / 2 |
| 错误 owner | 拒绝恢复，进程按测试约定退出 23 | 不执行 |

这证明指定故障窗口下的 **at-least-once 执行 + 业务幂等效果**，不是“框架保证 exactly-once”。
另外覆盖持久层打不开、等待时恢复不批准、变更批准内容、重复并发确认、调用方取消、重试耗尽后恢复、永久业务拒绝及过期终止。

独立审查又发现两个相邻故障窗口，均已修复并用独立子进程覆盖：

- **review 决定输出 pending writes 已提交、下一检查点未提交**：`state.next` 可能为空，仍必须将已保存 `approve + EXECUTING` 认作可恢复；恢复/相同决定重试只消费原收货信息，业务效果一次。
- **START pending writes 已提交、首个 review 检查点未提交**：以原生 `ainvoke(None)` 完成无副作用的初始化，恢复到真正的 interrupt，不能凭状态名伪造中断，也不能自动批准。

该矩阵 **5 个测试通过**。原始 `pending_write_traces` 也保存在同一 evidence JSON；测试只阻塞目标检查点写入以确定性注入故障，pending writes 是实际 SQLite 提交，随后实际 `os._exit(73)`，不是 MemorySaver 或假 checkpoint。

## 真实只读 RAG 消融

原始完整记录：`docs/qa/2026-11-01-rag-quality-live.json`（含每条 query、gold、完整候选池、真实重排分数、阶段时延、源码/语料 hash）。
数据集卡片：`docs/qa/2026-11-01-rag-quality-dataset.md`。

- 27 条冻结样本：20 正例、6 负例、1 未解决。dev/heldout 按问题族分离；`rq27` 明确排除，不偷改成负例。
- **AI 预标注，尚未人工复核**；gold 是小规模、可能不穷尽的相关性标注，不是盲测的人类标准答案。查询在看到实际召回结果前编写。
- 2026-11-01 在现有线上模型上进行显式只读测量；不改索引、不重建服务、不调用 Agent 业务工具、不触发订单/售后/支付/转人工。
- 41 个当前已发布平台政策 chunk；整个引用文档的切块、正文、标题、hash 校验通过，前后语料指纹一致。
- 每个问题共享 dense20/BM2520 的实际召回池；RRF10 后真实 HTTP 重排，共 260 个 query-document 对，final4。未从各路重新抽样择优。
- 受测线上代码为 `2dbf495ba7aa77a098d8dd10d1d6180af6b102dd`，测后 10 个服务仍运行，原生动作开关未设置；线上仍是原确认链路。
- 运行配置：embedding `shaw/dmeta-embedding-zh` / 768 维；reranker 配置为 `BAAI/bge-reranker-v2-m3`。评测报告明确区分配置标识与模型权重指纹验证。测后只读核验的 model.onnx/tokenizer/config 均匹配固定 revision 的锁文件；独立记录见 `2026-11-01-rag-quality-postcheck.json`，不是运行当时的权重证明。
- 未做阈值调优；单轮、固定顺序、无专门 warmup；没有运行生成器、没有给答案正确率评分。

### held-out（10 正例 + 3 负例）

| 检索路径 | Recall@4 | MRR@4 | nDCG@4 | 正例门控放行 | 负例拒答 |
|---|---:|---:|---:|---:|---:|
| 仅 dense | 0.70 | 0.4833 | 0.5361 | 9/10 | 2/3 |
| 仅 BM25 | 0.60 | 0.5500 | 0.5631 | 4/10 | 3/3 |
| RRF 混合 | 0.80 | 0.6333 | 0.6762 | 9/10 | 2/3 |
| RRF + 真实重排 | **0.90** | **0.7750** | **0.8062** | **1/10** | **3/3** |

### 全部已解决样本（20 正例 + 6 负例，不能替代 held-out）

| 检索路径 | Recall@4 | MRR@4 | nDCG@4 | 正例门控放行 | 负例拒答 |
|---|---:|---:|---:|---:|---:|
| 仅 dense | 0.75 | 0.4708 | 0.5408 | 16/20 | 4/6 |
| 仅 BM25 | 0.50 | 0.4167 | 0.4381 | 7/20 | 6/6 |
| RRF 混合 | 0.85 | 0.5917 | 0.6577 | 16/20 | 3/6 |
| RRF + 真实重排 | **0.90** | **0.6792** | **0.7342** | **3/20** | **6/6** |

**解释：排序改善不等于回答可用性达标。** 本轮重排提高了 gold chunk 排序，但当前门控对大多数改写正例拒答；这是明显的覆盖率短板，不能被负例全拒答或 Recall@4 掩盖。
`rq06` 与 `rq18` 的 gold 未进入最终 top4。标注可能不穷尽，失败仍原样保留，没有根据输出改标签。

单轮实际 CPU 时延（26 条，不含 LLM 生成）：

| 阶段 | p50 | p95 |
|---|---:|---:|
| dense | 0.271s | 0.879s |
| BM25 | 0.0106s | 0.0234s |
| 重排 | 8.732s | 10.072s |
| 每条消融总耗时 | 9.129s | 10.693s |

这些分位数只是该轮样本观察，不是负载测试、用户全链路响应时延或 SLA。

## 复现与未通过项

```powershell
# 仓库根目录
python -m pytest eval/tests tests deploy/test_action_workflow_config.py deploy/test_reranker_service.py -q
python -m eval.rag_quality
python -m eval.native_recovery_evidence
# ai-service 目录
python -m pytest tests -q
# 后端
mvn -o -f backend/pom.xml test
# 前端目录
npm test -- --run
npm run build
```

### 原生功能阶段本地验证（后续统一重试验证见新报告）

| 范围 | 结果 |
|---|---|
| AI 服务全量 | 618 passed |
| 前端全量 | 580 passed / 58 files |
| 前端 TypeScript / Vite | 两项退出码均为 0 |
| eval + 仓库卫生 + 重排服务 + 发布配置 | 81 passed |
| 原生故障窗口原始证据生成 | verified，源码 SHA-256 与当前文件一致 |
| 后端全量 | 836 passed，0 failures/errors/skips；88 个 JUnit report 文件 |
| 既有 production 静态门禁 | 11 passed，1 failed（见下） |

已知既有 `deploy/test_production.py` 的购物车“模拟支付”文案静态门禁失败；`CartView.vue` 与本任务基线完全一致，本次不顺手修改购物车。不能声称全仓门禁全绿。

### 独立审查闭环

审查发现的 pending-write 恢复漏洞、准备/状态缺少原生来源、历史页旧地址覆盖及旧终态动作被误接管问题均已修复。
最后一项在协调器与现有行锁事务内双重检查：未由原生图管理的旧 CONFIRMED/CANCELLED/EXPIRED 动作不能被接管；已原生管理的终态动作仍可取缓存回执。
源码与日志确认后端最后一轮 836 个测试全过；并未把这个结果当成未执行的跨服务/MySQL/线上验收。

## 启用前发布门禁

1. 人工复核 gold，补充多文档/多跳/对抗样本；已有 held-out 结果已可见，不可继续调参后把它重新包装成盲测。后续仅用 dev 校准，并冻结新的独立验收集。
2. 正例门控放行率过低与 CPU 重排时延必须单独验收；本次不为提高分数而放宽线上阈值，不更换/下载模型。
3. 在隔离环境实际连接 Java↔Python HTTP 与 MySQL 验证 V20/Flyway（现有业务数据库测试为 H2，不等同于 MySQL 验证）。
4. 私密检查点卷的 ACL/备份/恢复与过期数据保留策略；只允许一个工作流 AI 实例，禁止直接扩到多 worker/副本。
5. 两端一致启用、真实空白测试账号的人工决策验收、回滚演练；保留原生动作来源，回滚不可绕过已有批准。
6. 修复既有模拟支付文案门禁后再做发布总验收。本任务未执行生产确认链路切换。

可用于项目材料的准确表述：**“实现基于 LangGraph interrupt/Command 的人工确认工作流与 SQLite 持久化恢复，补充真实进程故障窗口的幂等回归，以及冻结样本上的 dense/BM25/RRF/重排消融证据。”** 不写成“已上线高可用、exactly-once、答案正确率 90%”。
