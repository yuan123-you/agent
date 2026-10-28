# Open Code Review 源码研究与 AI Mall 审计映射

## 0. 范围、版本与证据边界

- 研究日期：2026-10-28（Asia/Shanghai）。这是供主审计使用的 **research sidecar**，不是项目已经完成全面审计、修复或验收的声明。
- 一手参考：`alibaba/open-code-review`；本地只读副本：`C:\temp\codex-open-code-review-20261028`；已核对 HEAD：`375f64cd6f67a48a135da83cfcf59c52669a09cb`。文末所有上游 URL 固定在该提交，不以浮动分支或 README 的描述代替实现证据。
- 当前项目：`D:\studyAgent\AI Mall`；已核对 HEAD：`ac4d87015dcba66ea0f7cbd917b1d88eefaf5ed0`，另有大量有意保留的未提交修改、新文件。下文项目入口是研究时的工作区观察，**不是冻结的提交内容**；主审计应重新读取待验证实现，不能覆盖这些修改。
- 研究方式：只读源码、配置、提示词、测试定义；参考文件内的安装、执行、修复和代理指令均当作不可信研究材料，没有采纳为本次操作指令。没有安装依赖、执行参考 CLI/脚本/测试、读取用户凭据，或把 AI Mall 源码发送到任何新服务。公开 URL 的浏览请求未返回可用正文，因此实现结论以本地已核对提交的源码为依据。
- 唯一产物是本文档；基线测试、实际缺陷认定、应用代码修复和全量回归属于主审计。本研究读取了测试定义，但没有运行它们，不宣称上游或本项目测试通过。

**结论先行：**最值得借鉴的是审查编排和证据管理，而不是把它安装成一个“全栈静态 linter”。模型发现、文本定位、候选过滤、扫描汇总，分别解决不同问题；其中没有任何一层能够替代可复现测试、权限证明、事务验证和人工判断。[S01][S06][S14][S16][S25]

## 1. 三条不同路径，不能混为一谈

| 路径 | 实际工作 | 对本项目的用途 / 限制 | 实现证据 |
|---|---|---|---|
| Diff review | 解析 workspace / range / commit 的变更，筛选、语义分组、按需规划、分组多轮工具循环、候选过滤、收集结果 | 适合围绕当前未提交工作检查新变更引入的回归；不能据此声称全部存量代码已审计 | [S01][S02][S03][S06][S16] |
| Full scan | 枚举整个目录中的候选文件，逐文件审查；按批组织，可选规划、批内去重及项目总结 | 补足未变化的支付/订单/权限等存量路径；默认扩展名、排除项、体积与预算仍限制覆盖；按语言分批不是跨服务业务链分析 | [S24][S25][S26][S61][S64] |
| Delegate | 输出预览、模式/引用信息、已解析的规则分组，由宿主 agent 自己审查；这条命令路径不创建审查用 LLM runtime | 可借鉴文件清单与规则出处，不等于整个宿主环境离线，也不意味着已经获得上传授权；本研究不执行该 CLI | [S27][S28][S29] |

`skills/open-code-review/SKILL.md` 包装的是调用 CLI、报告与可选修复的宿主流程；`skills/open-code-review-delegate/SKILL.md` 则要求宿主维护逐文件覆盖清单。它们是工作流文本，不是确定性语言分析器。仓库还存在 plugin 内的同名 skill 包装；研究其机制不需要安装、运行这些入口。[S29][S30]

## 2. Diff 审查编排：可直接移植的思路

### 2.1 输入先冻结，覆盖先于“发现数量”

`Agent.Run` 的主线是加载 diff、建立会话与覆盖状态、派发分组任务，最后收集发现。静态选择顺序很重要：二进制 → 内建敏感路径 → 用户 exclude → 显式 include → 扩展名及默认路径排除。显式 include 能让普通默认排除文件进入候选，但不能覆盖内建敏感路径拦截；用户 exclude 优先于 include。删除文件不作为普通主审查目标，删除造成的行为回归仍需结合其消费者分析。[S01][S02]

**对主审计的建议：**分别记录“所有变更文件”“实际审查文件”“仅作上下文读取”“排除/超预算/失败文件”。默认排除的测试不能从 AI Mall 的审计清单中消失。只审 HEAD 会遗漏本项目当前大量 untracked 文件；应把新增文件作为全新内容读取，不能仅依赖对 tracked 文件的 diff。[S02][S20][S29]

### 2.2 分组是语义上下文优化，不是模块依赖图

- 实现先决定是否值得调用模型分组：默认 `GROUPING_MIN_FILES=4`。少于该数量且总改动小于 `GROUPING_BUNDLE_LINE_THRESHOLD=200` 时可直接合成小变更组，否则逐文件；达到数量阈值才走模型分组。分组失败回退逐文件。[S03][S04][S05]
- 分组提示词描述接口/实现、生产者/消费者、同模块配置等关联；实现会检查索引有效性、重复与遗漏，限制每组文件数量（10），并用 token 预算拆分。模型分组不构成真实调用关系的证明。[S03][S07]
- 分组并发受 semaphore 控制，默认参数约定是 8；分组超时/错误隔离，不能因一个失败让其他成功发现消失。[S01][S06]

**AI Mall 分组应按业务不变量补充跨语言关联：**订单状态变更应连同 Java service、mapper、数据库迁移、Python tool callback、前端订单 DTO/页面一起看；SSE 应连同 Python 事件生产、Java 转发/恢复、前端解析/存储一起看。不要只按 `.java`、`.ts`、`.py` 分三组后就认定契约已核对。

### 2.3 规划是模型的工具使用计划，不是工具验证

`executeGroupPlanPhase` 把可用工具描述写入提示词，但实际发出的规划请求没有可执行 Tools 列表；它取回的是计划文本。默认规划阈值为单文件改动 50 行、组总改动 100 行；判断在 `PlanRequired` 中实现。规划失败继续无计划审查，不能把“计划里列出了验证”记作“已验证”。[S04][S05][S08]

### 2.4 多轮用来减少首轮锚定，不代表独立复核

- effort 预设控制轮数：low=1、medium=2、high=3，默认 medium；基础模板为 2。每轮重新构建主审查消息，第二轮起移除首轮计划，携带此前已保留发现，避免计划成为查找上限和反复报告同一问题。[S04][S06][S09]
- 每轮会等待对应异步 comment workers 完成，再运行候选过滤，按每个路径的基线计算本轮新增；没有新增发现会提前退出，达到确认数上限也会退出。因此不保证每次真的执行两轮，更不是每个候选经过两个独立审查者。[S06]
- 主循环以 `task_done` 判断正常完成，限制工具请求轮次、空响应、token 预算和压缩。耗尽工具/预算应被记录为覆盖限制，零发现不等于安全。[S10]
- 上下文压缩在 60%/80% 阈值触发异步/同步路径，保留固定消息与最近活动区、总结中间会话；压缩提示主要保留路径、结论、待办而非完整代码证据。可借鉴防止上下文失控的设计，但最终缺陷必须重新引用原始代码和测试，而不是只引用压缩摘要。[S11][S12][S63]

## 3. “候选验证”到底验证了什么

### 3.1 结构化发现：分类字段不是可信度分数

`code_comment` schema 要求内容、原代码、category、severity 和 path；类别包括 bug/security/performance/maintainability/test/style/documentation/other，severity 为 critical/high/medium/low。实际解析器比 schema 宽松：最终检查 path 和 content，其他字段可能缺失；未知显式 category 归为 other，未知显式 severity 归为 low。模型结果没有强制的复现步骤、测试 ID、调用链或数值 confidence 字段。因此“合法 JSON”不是“已证明缺陷”。[S13][S14][S15]

主审计可保留原始 category/severity，但应另设 `candidate → verified / rejected / unresolved` 状态。若采用 P0–P3，这是本项目额外约定，不是该仓库的原生 schema。高严重度应由可达攻击/故障条件和影响支持，不能把缺少注释、`any` 或风格偏好自动提升成阻断项。

### 3.2 定位：先确定性匹配，后模型辅助；定位成功不等于语义正确

实际顺序：

1. 在声明的文件中用 `ExistingCode` 匹配 diff hunk / 新文件内容，尝试确定行号。
2. 若失败，跨本次可用 diff 查找原代码；**只在命中唯一其他文件时**一起迁移 path 和行号。无命中或多文件歧义时不猜。
3. 若原路径有 diff 且配置了 relocation task，再调用模型提取片段重定位。
4. 无论最终是否成功定位，当前实现仍将 comment 加入 collector，并不以定位成功作为语义有效性的硬门槛。[S16][S17][S18]

这是很实用的“确定性优先”机制，尤其适合 AI Mall 的接口/实现分离；但不能把对上了代码片段理解成对上了问题。`ResolveComment` 甚至把已有正行号视为已定位，片段匹配也可能落在旧侧或文件其他位置。修复前必须重新核对当前新侧具体行及真实执行条件。[S17]

### 3.3 Review filter：保留优先的反证过滤，不是再做一次完整验证

过滤器只收到组内 diff 和待过滤 comment 列表，没有主审查中读取的完整调用链/上下文。系统提示要求只删除能被 diff 直接证明为事实错误的候选：主题文件根本没有所描述代码，或有一条直接反驳核心主张的 diff 行。缺少证据、价值低、无法验证都不构成删除理由。[S19][S21][S22]

特别注意两个设计取舍：

- 提示词先保护内存安全、并发、声明/链接一致性、行为兼容变化、未使用形参等主题；即使过滤模型自认为存在反证，也要求保留。这是提示策略，不是 Go 代码里确定性执行的主题识别器。[S22]
- 实现只针对本轮候选做索引映射和移除；过滤调用失败或没有有效移除索引会保留发现。已有测试定义覆盖无工具调用保留、模型报错保留和实际删除分支，但这些测试不能证明模型会遵守提示中的语义政策。[S19][S23]

**政策张力要如实说明：**Python 与 Mapper 规则强调生成时高精度；delegate skill 还建议宿主丢弃疑似误报；而 review filter 明确把避免误删真实发现放在首位。它们并非一个统一、机器强制执行的误报阈值。主审计应记录“何处收集到证据/何种反证驳回”，而不是把 filtered / confirmed 字样当成事实成立的标记。[S22][S29][S33][S34]

### 3.4 Full scan 的去重不是跨项目证明

Full scan 默认按语言批处理（批大小 50）、文件大小上限 2 MiB、至少 4 个评论时考虑批内去重。去重结果使用 ID、canonical 和 members；实现拒绝未知 ID、重复分配、漏项等非法分组，对跨文件合并保留原文件 checkpoint 来源。项目总结依据评论集合归纳热点，不会自动建立真实跨服务调用链。[S24][S25][S26]

scan 通过 `toLoopTemplate` 复用主循环时没有启用 diff review 的 `ReviewFilterTask`；不能声称扫描结果也经过相同的反证过滤。此外 scan 的 `RunManifest()` 明确返回 nil，不能把 diff-review 的版本化覆盖清单能力无条件套到 scan 上。[S25]

另一个覆盖边界：scan 枚举阶段会跳过超体积、无法读取、非普通文件等条目，部分路径仅写 warning；因此后续 selected/preview 不一定就是原始目录全部文件的分母。`FilesReviewed()` 在 scan 中返回 items 数量，也不等于每个文件已成功完成工具循环。主审计需要独立目录清单核对这些缺口。[S25][S61]

## 4. 上下文检索、版本一致性与覆盖盲点

| 工具 / 机制 | 真实实现与上限 | 审计注意事项 | 证据 |
|---|---|---|---|
| `file_read` | 默认最多 500 行，显式标记截断；workspace 读磁盘，range / commit 通过 git show 读取目标版本 | 要分页读取；不能只看首段就说整文件审完。工具配置文字概括为新版本，但实际也能读取相关上下文文件 | [S13][S35][S36] |
| `code_search` | git grep，文字/Perl regex，默认不区分大小写；结果全局上限 100，workspace 可搜未跟踪文件，引用模式搜指定 ref；超时限制 10 秒 | “未在前 100 条找到”不等于不存在；需收窄路径、关键词及调用上下文 | [S37] |
| `file_find` | git ls-files / 引用树，文件名或路径查询，最多 100 | 是路径发现，不是 AST、符号解析或依赖图 | [S38] |
| `file_read_diff` | 从已有 DiffMap 返回其他变更文件；scan 中注入完整文件内容 | “本组外变更文件”与“未变化但参与执行的依赖”要分别处理，后者需 read/search | [S25][S39] |
| 路径约束 | workspace FileReader 做 canonical root、词法和解析 symlink 后的根内检查；git 调用使用显式参数 / ref | 有价值但不是代码内容 DLP、提示注入防护或完整沙箱；不授权读取敏感内容 | [S36][S37] |

### 4.1 对 AI Mall 特别关键的默认排除

内建排除表包含 Java `src/test` / `*Test.java`，TypeScript `*.spec.*` / `*.test.*`，Python `test_*.py` 等，以及依赖、构建产物和锁文件。主任务要求全面审计/修复，并且本项目未提交工作里已有很多这些测试；如果照搬默认 preview 清单，会遗漏回归证据和新测试本身。应额外审查测试文件和必要锁文件；显式 include 可覆盖普通默认排除，但不能越过敏感路径门槛。[S02][S20]

`.vue` 在 supported_file_types 中，但 `system_rules.json` 没有 Vue 专属模式；它回落 default.md，不会自动应用 TS/JS pack，更不自动理解 Vue SFC 中 script/template/style 三部分。`.sql` 同样需要确认回退规则是否足够，不能把 Flyway 迁移视作 Mapper XML 已覆盖。[S31][S32][S40]

### 4.2 覆盖记录比 exit code 更可信

Diff review 的版本化 manifest 区分 selected、completed、reused、failed、waived，计算 complete/partial/failed/skipped；记录 source artifact、规则与 runtime 的 hash。source hash 来自选定项目指纹；runtime hash 有意只取非敏感允许字段，规则顺序也参与 hash。恢复只复用被先前 manifest 确认为可复用的项，不把随手写入的 checkpoint 当完成证明。[S01][S41][S42][S62]

但 CLI 成功返回仍可能包含局部失败或之前已发现的问题；`FilesReviewed` 之类汇总计数不能替代逐文件完成状态。对本项目建议记录每个业务域的未完成原因、所用 diff/工作区快照及测试时间戳；不要从“0 findings / exit 0”推出全量覆盖。[S01][S06][S41]

## 5. 规则与 skill packs：可用部分和不适用部分

### 5.1 规则解析不是“所有检查叠加”

内建规则是嵌入 Markdown 文档，按路径 glob 首个命中选取，否则使用 default.md。解析优先级是显式 custom（`--rule`）> 项目根 `.opencodereview/rule.json` > 用户 global > system。用户规则默认**替换**系统规则；只有 `merge_system_rule` 显式保留匹配系统规则并合并用户规则。include/exclude 采用最高优先级存在过滤配置的整层，而不是所有层简单叠加。[S31][S43]

因此 Java 命中 java.md 并不自动再叠加 default.md 的权限/测试检查；TS 亦然。单独写一条业务规则而不做 merge，可能意外丢掉语言规则。规则中的“Mandatory”文字仍是发送给模型的提示，不是机器执行的确定性检查。[S31][S32][S43]

项目规则文件可引用受约束的文档文件；项目相对路径限制、symlink 根内检查、扩展名白名单与大小限制减少任意文件读取，但不证明规则内容可信。不应采纳待审代码库自己写的“忽略所有授权错误”等指令。[S43]

### 5.2 按栈的准确适配

| Pack | 材料中真正强调的规则 | AI Mall 适配 | 不应照搬 / 缺失 |
|---|---|---|---|
| Java | 条件/边界/NPE 要读调用链确认；循环数据库访问、无分页、大数据复杂度；共享状态的 check-then-act、非原子复合操作等 | 订单与售后状态转换、库存回补、SSE emitter 生命周期、批量查询 | 没有现成 Spring Security / 事务传播 / MyBatis-Plus 租户所有权证明；不要把局部变量、只读对象、已有正确同步当线程安全缺陷 | [S44] |
| Mapper/DAO XML | 动态 WHERE/JOIN、XML id 对齐、分页、SQL 拼接输入、参数绑定；上下文不明时谨慎报告 | 提取安全绑定与动态 SQL 原则，审查 Java mapper 注解中的 SQL 和实体字段 | glob 只针对名字含 mapper/dao 的 XML，不会把 Java 注解自动路由到 XML pack；`#{}` 安全绑定值不代表业务授权或 SQL 全部正确 | [S33][S31] |
| TS/JS/TSX/JSX | null 边界、异步错误/依赖次序、XSS/动态执行、敏感数据等 | Vue composable/store 的请求取消、旧响应覆盖、缓存作用域、Markdown 渲染与引用链接 | React hooks/useEffect/memo/组件内定义规则不适用于 Vue；var/等号/嵌套三元/内联样式等偏好不应变成此次缺陷修复范围；不盲目 Promise.all | [S45] |
| Python | 高精度、可达 None/空输入、共享可变默认/全局、资源清理、异步阻塞、后台任务异常、危险反序列化/命令/路径 | FastAPI streaming、LangGraph checkpoint、工具上下文、HTTP 客户端生命周期、检索和回调失败 | 不是 FastAPI/LangGraph 专属 pack；GIL 建议需结合实际解释器/工作负载；不能把所有共享缓存、受控后台任务或框架管理资源都报错 | [S34] |
| Default | 正确性、权限/注入/敏感信息、性能、可维护性、测试覆盖的通用问题 | Vue SFC / SQL 等回退文件的最低清单 | 不提供 Vue 模板编译、数据库执行计划、迁移回滚、跨服务 schema 验证 | [S32] |

## 6. 模型执行、源码上传与配置边界

**不安装、不运行，是本研究刻意保持的安全边界；delegate 不调用 OCR 模型也不等于允许绕道外传。**

| 边界 | 源码观察 | 对当前任务的处理 | 证据 |
|---|---|---|---|
| 普通 review / scan 模型调用 | 将 diff / 完整文件、业务背景、规则以及后续工具结果作为模型消息；客户端发送给解析到的 endpoint，支持不同 provider/protocol | 不调用参考工具，不新建 endpoint；“本地运行 CLI”不等于“本地推理” | [S08][S10][S25][S46][S47] |
| Endpoint / 凭据解析 | 显式 provider 选择与用户配置、OCR 环境、Claude Code 环境、shell rc 等策略；环境覆盖含部分 timeout/header 选项；有用户配置的 api_key_cmd / auth_token_cmd 路径 | 只阅读实现，不读取这些实际用户配置、shell rc、token 或执行 credential command | [S46][S48] |
| 本地会话留存 | 会话记录 resolved messages、responses、工具参数/结果，写入用户目录 `.opencodereview/sessions/...`；不是只有 findings | 即使不启用 telemetry/raw，也需考虑常规会话对源码与业务数据的留存 | [S49][S50] |
| Raw capture | `OCR_RAW_LOGGING=1` 为独立 opt-in，raw 记录包含完整请求/响应体；敏感 header 做脱敏；路径在 `.opencodereview/raw/...` | header 脱敏不是请求体源码/秘密脱敏；Unix 风格权限设置也不替代 Windows ACL 验证 | [S51][S52] |
| Telemetry | 默认 disabled；配置/环境可启用并导出 OTLP，content logging 默认关闭但可单独开启 | 默认关闭不代表所有部署都关闭；运行前需审核有效配置与导出目的地，本研究不运行 | [S53] |
| MCP | review 可连本地 stdio server 或远程 HTTP；本地 setup 可在 repoDir 运行配置脚本，再启动 server；tool allowlist 非空时筛选，空时注册所有非冲突工具 | 没有默认 shell built-in 不代表系统整体没有执行/网络能力；配置 MCP 需要单独执行与数据权限评估 | [S54][S55][S56] |
| 路径/秘密排除 | 内建秘密路径覆盖 SSH/private key/netrc/npmrc 等；`.env` 本身在支持扩展名中；FileReader 的约束是根目录，不是文件内容分类 | 这些不是完备秘密扫描。上下文 read/search 不应被假定自动复用审查入口的秘密排除；不能因此读取或发送真实 `.env`、数据库内容和用户文本 | [S02][S36][S37][S40][S57] |

以上是信任边界分析，不是宣称上游存在可利用漏洞。ASSURANCE_CASE 可作为作者声明背景，但执行边界以实际调用代码为准；本次没有尝试攻击、凭据探测或网络外传测试。

## 7. 给主审计的可执行映射（待验证假设，不是已确认缺陷）

以下测试场景由参考机制推导，是 AI Mall 的审计建议，不是声称上游实现了这些检测，也不声称项目目前存在这些问题。项目路径均为本地工作区，可能继续变化。

### 7.1 Spring / MyBatis：先验证钱、所有权、状态和原子性

入口：

- [OrderService.java](D:/studyAgent/AI%20Mall/backend/src/main/java/com/aimall/backend/order/OrderService.java)
- [AgentOrderActionService.java](D:/studyAgent/AI%20Mall/backend/src/main/java/com/aimall/backend/internal/AgentOrderActionService.java)
- [AfterSaleService.java](D:/studyAgent/AI%20Mall/backend/src/main/java/com/aimall/backend/aftersale/AfterSaleService.java)
- [OrderInfoMapper.java](D:/studyAgent/AI%20Mall/backend/src/main/java/com/aimall/backend/mapper/OrderInfoMapper.java)、[MallSkuMapper.java](D:/studyAgent/AI%20Mall/backend/src/main/java/com/aimall/backend/mapper/MallSkuMapper.java)
- [SseEmitterManager.java](D:/studyAgent/AI%20Mall/backend/src/main/java/com/aimall/backend/chat/SseEmitterManager.java)、[ChatService.java](D:/studyAgent/AI%20Mall/backend/src/main/java/com/aimall/backend/chat/ChatService.java)

研究时已看到 Java mapper 里的注解 SQL、订单行 `FOR UPDATE`、带 expectedStatus 的条件更新，以及 emitter 的条件 remove / synchronized；这些是必须纳入反证的现有机制，不能只因服务层存在多步代码就泛报竞态。

| 审计目标 | 必要调用链与反证 | 建议复现 / 验收 |
|---|---|---|
| 幂等状态转换 | controller → actor/ownership → service 事务边界 → 条件 UPDATE/受影响行数 → 库存、优惠券、退款副作用 | 同请求重复、两个 actor 并发、支付与取消竞争；最多一个成功转换，库存/优惠券/退款只发生一次 |
| 事务真正覆盖多表 | 查 Spring 代理入口、自调用、异常传播、锁顺序；不要仅凭 @Transactional 字样定论 | 第二个写操作失败后验证订单、SKU、促销、优惠券全部回滚；使用生产一致数据库语义，纯 mock 不能证明行锁 |
| 工具回调授权 | 外部身份 → internal token → userId/merchant ownership → action token 的绑定与过期 | 用户 A 操作 B 的订单、换 conversation、过期/重复确认均拒绝且不改变数据；不要信任模型给的身份 |
| SQL 安全和性能 | 跟到参数来源、动态列名/排序、分页上限、索引与实际数据量 | 对确实可达的拼接输入构造失败测试；`#{}` 绑定值不是注入证据；N+1 要确认循环中的调用确实发 SQL |
| 连接替换安全 | ChatService 生产事件与 emitter 注册/清理路径，比较 remove(key, instance) 与无条件 remove | 旧连接 completion/error/timeout 晚到时新连接仍存活；心跳与 token 并发发送不破坏帧；终结后不再发业务事件 |

可优先阅读现有测试（不是新建同名测试）：
[OrderLifecycleTransactionTest.java](D:/studyAgent/AI%20Mall/backend/src/test/java/com/aimall/backend/order/OrderLifecycleTransactionTest.java)、[AgentOrderActionTransactionTest.java](D:/studyAgent/AI%20Mall/backend/src/test/java/com/aimall/backend/internal/AgentOrderActionTransactionTest.java)、[SseEmitterManagerRecoveryTest.java](D:/studyAgent/AI%20Mall/backend/src/test/java/com/aimall/backend/chat/SseEmitterManagerRecoveryTest.java)。先理解预期，再对真正未覆盖的分支添加最小复现。[S33][S44]

### 7.2 Vue / TypeScript：用生命周期与事件契约替换 React 清单

入口：
[useSseChat.ts](D:/studyAgent/AI%20Mall/frontend/src/composables/useSseChat.ts)、[chat.ts](D:/studyAgent/AI%20Mall/frontend/src/stores/chat.ts)、[chatRecovery.ts](D:/studyAgent/AI%20Mall/frontend/src/stores/chatRecovery.ts)、[hotContentCache.ts](D:/studyAgent/AI%20Mall/frontend/src/api/hotContentCache.ts)、[AiMessage.vue](D:/studyAgent/AI%20Mall/frontend/src/components/chat/AiMessage.vue)、[request.ts](D:/studyAgent/AI%20Mall/frontend/src/api/request.ts)。

- **SSE 帧解析：**同一事件拆成多次 read、UTF-8 字符截断、CRLF、多条 data、注释心跳、最后一帧缺空行、网络断开而没有 done；确保不丢 token、不重复终结、不将未知帧当成功。HTTP 失败 / 非 event-stream 内容要走失败状态而非正常完成。
- **取消与陈旧响应：**切换 conversation、页面卸载、主动停止、恢复/重试后旧 stream 晚到；验证 AbortController、reader 清理与 store 的 request/generation 身份一起生效，不覆盖新消息。不要仅因出现 abort 调用就认定链路已闭合。
- **账户隔离：**账号切换/退出时 in-flight 请求完成，确认缓存 owner/generation 与恢复描述符隔离；不是只检查缓存 key。商品展示缓存与订单/个人状态应分别验证，不能把延迟展示数据当实时可交易事实。
- **渲染信任：**追踪模型/知识库/搜索字符串到真正的 Markdown / HTML / 链接 sink，再验证消毒、协议和属性处理；不要假设一个组件叫 AiMessage 就一定存在或不存在 XSS。
- **契约：**Java/Python 的 done/error/action payload、消息状态、ID、恢复游标与前端类型和 UI 状态一致。类型断言不构成外部 payload 运行时验证。

先复用 [useSseChat.spec.ts](D:/studyAgent/AI%20Mall/frontend/src/composables/useSseChat.spec.ts)、[chat.recovery.spec.ts](D:/studyAgent/AI%20Mall/frontend/src/stores/chat.recovery.spec.ts)、[hotContent.spec.ts](D:/studyAgent/AI%20Mall/frontend/src/api/hotContent.spec.ts) 的场景，加入真实组件/路由层的失败路径；不照搬 React hooks、memo 或内联样式偏好。[S20][S32][S45]

### 7.3 FastAPI / LangGraph：证明会话隔离、取消和工具副作用

入口：
[graph.py](D:/studyAgent/AI%20Mall/ai-service/app/agent/graph.py)、[state.py](D:/studyAgent/AI%20Mall/ai-service/app/agent/state.py)、[nodes.py](D:/studyAgent/AI%20Mall/ai-service/app/agent/nodes.py)、[chat.py](D:/studyAgent/AI%20Mall/ai-service/app/api/chat.py)、[backend_client.py](D:/studyAgent/AI%20Mall/ai-service/app/clients/backend_client.py)、[web_search.py](D:/studyAgent/AI%20Mall/ai-service/app/tools/web_search.py)。

研究时观察到 chat 采用 `conv_<conversation_id>` checkpoint key、请求包含 user_id，graph 使用 checkpointer，stream 有总超时和客户端断开处理，backend client 带内部 token。**这些事实都不直接证明漏洞或安全：**例如会话 key 没有 user_id 不能单独判定串号，必须核对上游 conversation 全局唯一性、所有权和内部入口保护。

| 审计目标 | 最小证据 / 测试 |
|---|---|
| checkpoint / state 隔离 | 用户 A/B、会话 A/B、多轮/重试/重启、同会话并发；证明 checkpoint 不污染其他用户，恢复不会重复拼接消息，真正权限在可信边界验证 |
| 非阻塞与资源生命周期 | 跟踪 async def 中实际执行的同步存取/HTTP/SQLite 路径；并发慢请求时另一个请求可推进，断开后任务和连接按设计回收；不要无条件把框架管理资源判泄漏 |
| 取消/超时的语义 | 模拟 token 前后超时、断开、工具正在执行、最终 payload；失败状态不得伪装为成功完成，回调/落库不能越过已取消状态产生重复副作用 |
| 读重试与写重试分离 | 跟到 backend_client 的调用者和服务端幂等键；模拟“服务端提交但客户端没收到响应”，确认不会双下单、双取消、双退款；安全只读查询可使用不同策略 |
| 工具与检索内容是不可信数据 | 模型 prompt / 搜索内容不得升级为系统指令、身份或购买授权；交易动作必须后端重新校验并要求既定确认；构造工具结果注入、伪造 userId 和跨会话 action 测试 |
| 事实与性能 | 检索超时、候选被实时业务数据否定、空结果、重复引用、并发工具完成顺序；验证引用与商品事实稳定，并测量首 token/总耗时，不从源码中出现 gather 就推断更快 |

优先参考现有 [test_chat_rag_citations.py](D:/studyAgent/AI%20Mall/ai-service/tests/test_chat_rag_citations.py)、[test_chat_regeneration.py](D:/studyAgent/AI%20Mall/ai-service/tests/test_chat_regeneration.py)、[test_pipeline_latency.py](D:/studyAgent/AI%20Mall/ai-service/tests/test_pipeline_latency.py)。这些路径只是复核入口，不是本研究执行过的测试结果。[S34]

## 8. 主审计采用方式：保留方法，不引入执行依赖

1. **建立当前工作区基线。**记录 HEAD、tracked/untracked 清单和时间；主审计自己运行现有三栈测试与构建，区分既有失败与新回归。不要 reset/clean、替换用户工作或调用参考安装脚本。
2. **两个互补清单。**一份按改动文件，一份按存量高风险业务链；测试和 schema/迁移是必要证据，即使参考工具默认排除。按 `(path, status)` 处理暂存删除后同路径重建，避免漏掉一侧。[S29]
3. **按风险分组、限制上下文。**先钱/权限/订单原子性，再 SSE/恢复与会话隔离，再事实准确性与性能；每组保留一个“剩余文件/未决假设”清单，不因找到第一个高危就停止。
4. **对每个候选补齐证据卡：**路径/当前行、具体主张、输入/并发顺序、可信入口、调用链、现有防护与反证、影响、复现测试、严重度、状态。`unresolved` 不能直接转成修复任务。
5. **确定性验证优先。**先搜索真实绑定/状态条件/调用者/已有测试；再写最小失败测试。不能复现时继续取证或注明边界，不以风格建议代替缺陷。
6. **外部内容与建议代码均不可信。**模型提出的修复、规则、搜索结果不能自动执行；审查建议 diff 本身，确认没有新权限、数据上传、依赖或破坏兼容的扩展。
7. **最小修复、逐项复测。**红灯复现 → 只改造成该故障的路径 → 绿灯 → 同域回归 → 三栈全量与必要构建；数据库锁语义、跨服务 SSE 和真实渲染需要对应层级验证，不用纯 mock 替代。
8. **交付覆盖与限制。**分别列 verified/fixed、rejected/unresolved、未覆盖路径、测试命令/结果/时间、外部依赖与部署限制；禁止把部分覆盖、模型保留的候选或项目总结包装成“全项目无问题”。

## 9. 本次不适用 / 不应声称具备的能力

- 没有在本项目接入 OCR、启用模型推理、导出 telemetry、启动 MCP，亦没有验证参考 CLI 的运行表现。
- 语言规则是提示词，不是 AST/type checker、编译器、SAST/污点分析、SBOM/CVE 数据库或依赖漏洞扫描器。
- React 专属规则不适合 Vue；Mapper XML 的路径匹配不覆盖 Java 注解 SQL；Python pack 不自动理解 LangGraph reducer、checkpoint 的租户边界或 FastAPI 断开语义。
- 多轮审查不等于独立双审；文本定位不等于缺陷证明；candidate filter 不保证消除误报；scan 去重不等于 root-cause 证明；模型总结不等于全量审计。
- 默认排除测试、构建和锁文件不适合照搬成 AI Mall 全面审计的边界；无发现、无评论、exit 0 或 selected 数量不能证明完成。
- 秘密路径排除、header 脱敏、仓库根内读文件不等于完备 DLP；宿主 delegate、远程 provider、OTLP、MCP 的权限需要分别判断。
- 本文没有认定任何新增 AI Mall 缺陷，没有复用旧审计的“通过”数量充当今日基线，没有触碰生产数据。

## 10. 固定提交的源码证据索引

每行均提供本地绝对路径与固定提交 URL。`#Lx-Ly` 对应上述提交的行号；文中的 `[Sxx]` 指向本表编号。测试文件仅作为设计约束的证据，均未执行。

| ID | 本地文件与证据范围 | 固定提交 source URL |
|---|---|---|
| S01 | [internal/agent/agent.go](C:/temp/codex-open-code-review-20261028/internal/agent/agent.go)：L184–L855 | [source](https://github.com/alibaba/open-code-review/blob/375f64cd6f67a48a135da83cfcf59c52669a09cb/internal/agent/agent.go#L184-L855) |
| S02 | [internal/agent/selection.go](C:/temp/codex-open-code-review-20261028/internal/agent/selection.go)：L65–L103 | [source](https://github.com/alibaba/open-code-review/blob/375f64cd6f67a48a135da83cfcf59c52669a09cb/internal/agent/selection.go#L65-L103) |
| S03 | [internal/agent/grouping.go](C:/temp/codex-open-code-review-20261028/internal/agent/grouping.go)：L68–L368 | [source](https://github.com/alibaba/open-code-review/blob/375f64cd6f67a48a135da83cfcf59c52669a09cb/internal/agent/grouping.go#L68-L368) |
| S04 | [internal/config/template/task_template.json](C:/temp/codex-open-code-review-20261028/internal/config/template/task_template.json)：L1–L46 | [source](https://github.com/alibaba/open-code-review/blob/375f64cd6f67a48a135da83cfcf59c52669a09cb/internal/config/template/task_template.json#L1-L46) |
| S05 | [internal/config/template/template.go](C:/temp/codex-open-code-review-20261028/internal/config/template/template.go)：L45–L135 | [source](https://github.com/alibaba/open-code-review/blob/375f64cd6f67a48a135da83cfcf59c52669a09cb/internal/config/template/template.go#L45-L135) |
| S06 | [internal/agent/agent.go](C:/temp/codex-open-code-review-20261028/internal/agent/agent.go)：L1379–L1565 | [source](https://github.com/alibaba/open-code-review/blob/375f64cd6f67a48a135da83cfcf59c52669a09cb/internal/agent/agent.go#L1379-L1565) |
| S07 | [internal/config/template/prompts/grouping_task_system.md](C:/temp/codex-open-code-review-20261028/internal/config/template/prompts/grouping_task_system.md)：L1–L16 | [source](https://github.com/alibaba/open-code-review/blob/375f64cd6f67a48a135da83cfcf59c52669a09cb/internal/config/template/prompts/grouping_task_system.md#L1-L16) |
| S08 | [internal/agent/agent.go](C:/temp/codex-open-code-review-20261028/internal/agent/agent.go)：L1740–L1792 | [source](https://github.com/alibaba/open-code-review/blob/375f64cd6f67a48a135da83cfcf59c52669a09cb/internal/agent/agent.go#L1740-L1792) |
| S09 | [internal/config/template/effort.go](C:/temp/codex-open-code-review-20261028/internal/config/template/effort.go)：L11–L61 | [source](https://github.com/alibaba/open-code-review/blob/375f64cd6f67a48a135da83cfcf59c52669a09cb/internal/config/template/effort.go#L11-L61) |
| S10 | [internal/llmloop/loop.go](C:/temp/codex-open-code-review-20261028/internal/llmloop/loop.go)：L359–L672 | [source](https://github.com/alibaba/open-code-review/blob/375f64cd6f67a48a135da83cfcf59c52669a09cb/internal/llmloop/loop.go#L359-L672) |
| S11 | [internal/llmloop/compression.go](C:/temp/codex-open-code-review-20261028/internal/llmloop/compression.go)：L19–L30 | [source](https://github.com/alibaba/open-code-review/blob/375f64cd6f67a48a135da83cfcf59c52669a09cb/internal/llmloop/compression.go#L19-L30) |
| S12 | [internal/config/template/prompts/memory_compression_task_system.md](C:/temp/codex-open-code-review-20261028/internal/config/template/prompts/memory_compression_task_system.md)：L1–L30 | [source](https://github.com/alibaba/open-code-review/blob/375f64cd6f67a48a135da83cfcf59c52669a09cb/internal/config/template/prompts/memory_compression_task_system.md#L1-L30) |
| S13 | [internal/config/toolsconfig/tools.json](C:/temp/codex-open-code-review-20261028/internal/config/toolsconfig/tools.json)：L1–L214 | [source](https://github.com/alibaba/open-code-review/blob/375f64cd6f67a48a135da83cfcf59c52669a09cb/internal/config/toolsconfig/tools.json#L1-L214) |
| S14 | [internal/tool/code_comment.go](C:/temp/codex-open-code-review-20261028/internal/tool/code_comment.go)：L86–L196 | [source](https://github.com/alibaba/open-code-review/blob/375f64cd6f67a48a135da83cfcf59c52669a09cb/internal/tool/code_comment.go#L86-L196) |
| S15 | [internal/model/review.go](C:/temp/codex-open-code-review-20261028/internal/model/review.go)：L1–L29 | [source](https://github.com/alibaba/open-code-review/blob/375f64cd6f67a48a135da83cfcf59c52669a09cb/internal/model/review.go#L1-L29) |
| S16 | [internal/llmloop/loop.go](C:/temp/codex-open-code-review-20261028/internal/llmloop/loop.go)：L727–L837 | [source](https://github.com/alibaba/open-code-review/blob/375f64cd6f67a48a135da83cfcf59c52669a09cb/internal/llmloop/loop.go#L727-L837) |
| S17 | [internal/diff/resolver.go](C:/temp/codex-open-code-review-20261028/internal/diff/resolver.go)：L12–L145 | [source](https://github.com/alibaba/open-code-review/blob/375f64cd6f67a48a135da83cfcf59c52669a09cb/internal/diff/resolver.go#L12-L145) |
| S18 | [internal/diff/relocation.go](C:/temp/codex-open-code-review-20261028/internal/diff/relocation.go)：L1–L117 | [source](https://github.com/alibaba/open-code-review/blob/375f64cd6f67a48a135da83cfcf59c52669a09cb/internal/diff/relocation.go#L1-L117) |
| S19 | [internal/agent/agent.go](C:/temp/codex-open-code-review-20261028/internal/agent/agent.go)：L1794–L1923 | [source](https://github.com/alibaba/open-code-review/blob/375f64cd6f67a48a135da83cfcf59c52669a09cb/internal/agent/agent.go#L1794-L1923) |
| S20 | [internal/config/allowlist/default_exclude_patterns.json](C:/temp/codex-open-code-review-20261028/internal/config/allowlist/default_exclude_patterns.json)：L1–L110 | [source](https://github.com/alibaba/open-code-review/blob/375f64cd6f67a48a135da83cfcf59c52669a09cb/internal/config/allowlist/default_exclude_patterns.json#L1-L110) |
| S21 | [internal/config/template/prompts/review_filter_task_system.md](C:/temp/codex-open-code-review-20261028/internal/config/template/prompts/review_filter_task_system.md)：L1–L12 | [source](https://github.com/alibaba/open-code-review/blob/375f64cd6f67a48a135da83cfcf59c52669a09cb/internal/config/template/prompts/review_filter_task_system.md#L1-L12) |
| S22 | [internal/config/template/prompts/review_filter_task_user.md](C:/temp/codex-open-code-review-20261028/internal/config/template/prompts/review_filter_task_user.md)：L1–L85 | [source](https://github.com/alibaba/open-code-review/blob/375f64cd6f67a48a135da83cfcf59c52669a09cb/internal/config/template/prompts/review_filter_task_user.md#L1-L85) |
| S23 | [internal/agent/coverage_test.go](C:/temp/codex-open-code-review-20261028/internal/agent/coverage_test.go)：L271–L396 | [source](https://github.com/alibaba/open-code-review/blob/375f64cd6f67a48a135da83cfcf59c52669a09cb/internal/agent/coverage_test.go#L271-L396) |
| S24 | [internal/config/template/scan_template.json](C:/temp/codex-open-code-review-20261028/internal/config/template/scan_template.json)：L1–L87 | [source](https://github.com/alibaba/open-code-review/blob/375f64cd6f67a48a135da83cfcf59c52669a09cb/internal/config/template/scan_template.json#L1-L87) |
| S25 | [internal/scan/agent.go](C:/temp/codex-open-code-review-20261028/internal/scan/agent.go)：L98–L430 | [source](https://github.com/alibaba/open-code-review/blob/375f64cd6f67a48a135da83cfcf59c52669a09cb/internal/scan/agent.go#L98-L430) |
| S26 | [internal/scan/agent.go](C:/temp/codex-open-code-review-20261028/internal/scan/agent.go)：L990–L1154 | [source](https://github.com/alibaba/open-code-review/blob/375f64cd6f67a48a135da83cfcf59c52669a09cb/internal/scan/agent.go#L990-L1154) |
| S27 | [cmd/opencodereview/delegate_cmd.go](C:/temp/codex-open-code-review-20261028/cmd/opencodereview/delegate_cmd.go)：L30–L165 | [source](https://github.com/alibaba/open-code-review/blob/375f64cd6f67a48a135da83cfcf59c52669a09cb/cmd/opencodereview/delegate_cmd.go#L30-L165) |
| S28 | [internal/delegate/rulegroup.go](C:/temp/codex-open-code-review-20261028/internal/delegate/rulegroup.go)：L1–L62 | [source](https://github.com/alibaba/open-code-review/blob/375f64cd6f67a48a135da83cfcf59c52669a09cb/internal/delegate/rulegroup.go#L1-L62) |
| S29 | [skills/open-code-review-delegate/SKILL.md](C:/temp/codex-open-code-review-20261028/skills/open-code-review-delegate/SKILL.md)：L1–L207 | [source](https://github.com/alibaba/open-code-review/blob/375f64cd6f67a48a135da83cfcf59c52669a09cb/skills/open-code-review-delegate/SKILL.md#L1-L207) |
| S30 | [skills/open-code-review/SKILL.md](C:/temp/codex-open-code-review-20261028/skills/open-code-review/SKILL.md)：L1–L256 | [source](https://github.com/alibaba/open-code-review/blob/375f64cd6f67a48a135da83cfcf59c52669a09cb/skills/open-code-review/SKILL.md#L1-L256) |
| S31 | [internal/config/rules/system_rules.json](C:/temp/codex-open-code-review-20261028/internal/config/rules/system_rules.json)：L1–L62 | [source](https://github.com/alibaba/open-code-review/blob/375f64cd6f67a48a135da83cfcf59c52669a09cb/internal/config/rules/system_rules.json#L1-L62) |
| S32 | [internal/config/rules/rule_docs/default.md](C:/temp/codex-open-code-review-20261028/internal/config/rules/rule_docs/default.md)：L1–L22 | [source](https://github.com/alibaba/open-code-review/blob/375f64cd6f67a48a135da83cfcf59c52669a09cb/internal/config/rules/rule_docs/default.md#L1-L22) |
| S33 | [internal/config/rules/rule_docs/mapper_dao_xml.md](C:/temp/codex-open-code-review-20261028/internal/config/rules/rule_docs/mapper_dao_xml.md)：L1–L33 | [source](https://github.com/alibaba/open-code-review/blob/375f64cd6f67a48a135da83cfcf59c52669a09cb/internal/config/rules/rule_docs/mapper_dao_xml.md#L1-L33) |
| S34 | [internal/config/rules/rule_docs/python.md](C:/temp/codex-open-code-review-20261028/internal/config/rules/rule_docs/python.md)：L1–L77 | [source](https://github.com/alibaba/open-code-review/blob/375f64cd6f67a48a135da83cfcf59c52669a09cb/internal/config/rules/rule_docs/python.md#L1-L77) |
| S35 | [internal/tool/file_read.go](C:/temp/codex-open-code-review-20261028/internal/tool/file_read.go)：L1–L78 | [source](https://github.com/alibaba/open-code-review/blob/375f64cd6f67a48a135da83cfcf59c52669a09cb/internal/tool/file_read.go#L1-L78) |
| S36 | [internal/tool/filereader.go](C:/temp/codex-open-code-review-20261028/internal/tool/filereader.go)：L25–L140 | [source](https://github.com/alibaba/open-code-review/blob/375f64cd6f67a48a135da83cfcf59c52669a09cb/internal/tool/filereader.go#L25-L140) |
| S37 | [internal/tool/code_search.go](C:/temp/codex-open-code-review-20261028/internal/tool/code_search.go)：L17–L215 | [source](https://github.com/alibaba/open-code-review/blob/375f64cd6f67a48a135da83cfcf59c52669a09cb/internal/tool/code_search.go#L17-L215) |
| S38 | [internal/tool/file_find.go](C:/temp/codex-open-code-review-20261028/internal/tool/file_find.go)：L1–L155 | [source](https://github.com/alibaba/open-code-review/blob/375f64cd6f67a48a135da83cfcf59c52669a09cb/internal/tool/file_find.go#L1-L155) |
| S39 | [internal/tool/file_read_diff.go](C:/temp/codex-open-code-review-20261028/internal/tool/file_read_diff.go)：L1–L74 | [source](https://github.com/alibaba/open-code-review/blob/375f64cd6f67a48a135da83cfcf59c52669a09cb/internal/tool/file_read_diff.go#L1-L74) |
| S40 | [internal/config/allowlist/supported_file_types.json](C:/temp/codex-open-code-review-20261028/internal/config/allowlist/supported_file_types.json)：L1–L90 | [source](https://github.com/alibaba/open-code-review/blob/375f64cd6f67a48a135da83cfcf59c52669a09cb/internal/config/allowlist/supported_file_types.json#L1-L90) |
| S41 | [internal/session/manifest.go](C:/temp/codex-open-code-review-20261028/internal/session/manifest.go)：L159–L286 | [source](https://github.com/alibaba/open-code-review/blob/375f64cd6f67a48a135da83cfcf59c52669a09cb/internal/session/manifest.go#L159-L286) |
| S42 | [internal/agent/agent.go](C:/temp/codex-open-code-review-20261028/internal/agent/agent.go)：L874–L915 | [source](https://github.com/alibaba/open-code-review/blob/375f64cd6f67a48a135da83cfcf59c52669a09cb/internal/agent/agent.go#L874-L915) |
| S43 | [internal/config/rules/system_rules.go](C:/temp/codex-open-code-review-20261028/internal/config/rules/system_rules.go)：L310–L664 | [source](https://github.com/alibaba/open-code-review/blob/375f64cd6f67a48a135da83cfcf59c52669a09cb/internal/config/rules/system_rules.go#L310-L664) |
| S44 | [internal/config/rules/rule_docs/java.md](C:/temp/codex-open-code-review-20261028/internal/config/rules/rule_docs/java.md)：L1–L41 | [source](https://github.com/alibaba/open-code-review/blob/375f64cd6f67a48a135da83cfcf59c52669a09cb/internal/config/rules/rule_docs/java.md#L1-L41) |
| S45 | [internal/config/rules/rule_docs/ts_js_tsx_jsx.md](C:/temp/codex-open-code-review-20261028/internal/config/rules/rule_docs/ts_js_tsx_jsx.md)：L1–L40 | [source](https://github.com/alibaba/open-code-review/blob/375f64cd6f67a48a135da83cfcf59c52669a09cb/internal/config/rules/rule_docs/ts_js_tsx_jsx.md#L1-L40) |
| S46 | [internal/llm/resolver.go](C:/temp/codex-open-code-review-20261028/internal/llm/resolver.go)：L101–L205 | [source](https://github.com/alibaba/open-code-review/blob/375f64cd6f67a48a135da83cfcf59c52669a09cb/internal/llm/resolver.go#L101-L205) |
| S47 | [internal/llm/client.go](C:/temp/codex-open-code-review-20261028/internal/llm/client.go)：L486–L737 | [source](https://github.com/alibaba/open-code-review/blob/375f64cd6f67a48a135da83cfcf59c52669a09cb/internal/llm/client.go#L486-L737) |
| S48 | [internal/llm/keycmd_windows.go](C:/temp/codex-open-code-review-20261028/internal/llm/keycmd_windows.go)：L1–L50 | [source](https://github.com/alibaba/open-code-review/blob/375f64cd6f67a48a135da83cfcf59c52669a09cb/internal/llm/keycmd_windows.go#L1-L50) |
| S49 | [internal/session/history.go](C:/temp/codex-open-code-review-20261028/internal/session/history.go)：L367–L386 | [source](https://github.com/alibaba/open-code-review/blob/375f64cd6f67a48a135da83cfcf59c52669a09cb/internal/session/history.go#L367-L386) |
| S50 | [internal/session/persist.go](C:/temp/codex-open-code-review-20261028/internal/session/persist.go)：L228–L337 | [source](https://github.com/alibaba/open-code-review/blob/375f64cd6f67a48a135da83cfcf59c52669a09cb/internal/session/persist.go#L228-L337) |
| S51 | [internal/llm/raw.go](C:/temp/codex-open-code-review-20261028/internal/llm/raw.go)：L1–L110 | [source](https://github.com/alibaba/open-code-review/blob/375f64cd6f67a48a135da83cfcf59c52669a09cb/internal/llm/raw.go#L1-L110) |
| S52 | [internal/session/raw_writer.go](C:/temp/codex-open-code-review-20261028/internal/session/raw_writer.go)：L19–L65 | [source](https://github.com/alibaba/open-code-review/blob/375f64cd6f67a48a135da83cfcf59c52669a09cb/internal/session/raw_writer.go#L19-L65) |
| S53 | [internal/telemetry/config.go](C:/temp/codex-open-code-review-20261028/internal/telemetry/config.go)：L14–L100 | [source](https://github.com/alibaba/open-code-review/blob/375f64cd6f67a48a135da83cfcf59c52669a09cb/internal/telemetry/config.go#L14-L100) |
| S54 | [cmd/opencodereview/review_cmd.go](C:/temp/codex-open-code-review-20261028/cmd/opencodereview/review_cmd.go)：L531–L620 | [source](https://github.com/alibaba/open-code-review/blob/375f64cd6f67a48a135da83cfcf59c52669a09cb/cmd/opencodereview/review_cmd.go#L531-L620) |
| S55 | [internal/mcp/client.go](C:/temp/codex-open-code-review-20261028/internal/mcp/client.go)：L38–L126 | [source](https://github.com/alibaba/open-code-review/blob/375f64cd6f67a48a135da83cfcf59c52669a09cb/internal/mcp/client.go#L38-L126) |
| S56 | [internal/mcp/provider.go](C:/temp/codex-open-code-review-20261028/internal/mcp/provider.go)：L30–L66 | [source](https://github.com/alibaba/open-code-review/blob/375f64cd6f67a48a135da83cfcf59c52669a09cb/internal/mcp/provider.go#L30-L66) |
| S57 | [internal/config/allowlist/default_secret_patterns.json](C:/temp/codex-open-code-review-20261028/internal/config/allowlist/default_secret_patterns.json)：L1–L12 | [source](https://github.com/alibaba/open-code-review/blob/375f64cd6f67a48a135da83cfcf59c52669a09cb/internal/config/allowlist/default_secret_patterns.json#L1-L12) |
| S58 | [internal/diff/relocate_across_files_test.go](C:/temp/codex-open-code-review-20261028/internal/diff/relocate_across_files_test.go)：L43–L102 | [source](https://github.com/alibaba/open-code-review/blob/375f64cd6f67a48a135da83cfcf59c52669a09cb/internal/diff/relocate_across_files_test.go#L43-L102) |
| S59 | [internal/scan/dedup_test.go](C:/temp/codex-open-code-review-20261028/internal/scan/dedup_test.go)：L17–L92 | [source](https://github.com/alibaba/open-code-review/blob/375f64cd6f67a48a135da83cfcf59c52669a09cb/internal/scan/dedup_test.go#L17-L92) |
| S60 | [internal/agent/grouping_test.go](C:/temp/codex-open-code-review-20261028/internal/agent/grouping_test.go)：L60–L174 | [source](https://github.com/alibaba/open-code-review/blob/375f64cd6f67a48a135da83cfcf59c52669a09cb/internal/agent/grouping_test.go#L60-L174) |
| S61 | [internal/scan/provider.go](C:/temp/codex-open-code-review-20261028/internal/scan/provider.go)：L98–L173 | [source](https://github.com/alibaba/open-code-review/blob/375f64cd6f67a48a135da83cfcf59c52669a09cb/internal/scan/provider.go#L98-L173) |
| S62 | [internal/agent/agent.go](C:/temp/codex-open-code-review-20261028/internal/agent/agent.go)：L1020–L1108 | [source](https://github.com/alibaba/open-code-review/blob/375f64cd6f67a48a135da83cfcf59c52669a09cb/internal/agent/agent.go#L1020-L1108) |
| S63 | [internal/llmloop/compression.go](C:/temp/codex-open-code-review-20261028/internal/llmloop/compression.go)：L129–L295 | [source](https://github.com/alibaba/open-code-review/blob/375f64cd6f67a48a135da83cfcf59c52669a09cb/internal/llmloop/compression.go#L129-L295) |
| S64 | [internal/scan/batch.go](C:/temp/codex-open-code-review-20261028/internal/scan/batch.go)：L16–L110 | [source](https://github.com/alibaba/open-code-review/blob/375f64cd6f67a48a135da83cfcf59c52669a09cb/internal/scan/batch.go#L16-L110) |

补充交叉验证：唯一跨文件定位 / 歧义拒绝见 S58；去重非法分组拒绝见 S59；语义分组遗漏 / 重复 / 无效输出处理见 S60。上述测试定义帮助区分实现保证与模型提示约束，不代表本次执行过测试。

**研究产物验收：**来源 HEAD 已核对；上游源文件与行号范围已检查；本地项目链接应由主审计按继续变化的工作区复核；本文只提供审计方法和待验证目标，未执行应用测试或修改应用代码。

<!-- Pinned evidence reference links -->
[S01]: https://github.com/alibaba/open-code-review/blob/375f64cd6f67a48a135da83cfcf59c52669a09cb/internal/agent/agent.go#L184-L855
[S02]: https://github.com/alibaba/open-code-review/blob/375f64cd6f67a48a135da83cfcf59c52669a09cb/internal/agent/selection.go#L65-L103
[S03]: https://github.com/alibaba/open-code-review/blob/375f64cd6f67a48a135da83cfcf59c52669a09cb/internal/agent/grouping.go#L68-L368
[S04]: https://github.com/alibaba/open-code-review/blob/375f64cd6f67a48a135da83cfcf59c52669a09cb/internal/config/template/task_template.json#L1-L46
[S05]: https://github.com/alibaba/open-code-review/blob/375f64cd6f67a48a135da83cfcf59c52669a09cb/internal/config/template/template.go#L45-L135
[S06]: https://github.com/alibaba/open-code-review/blob/375f64cd6f67a48a135da83cfcf59c52669a09cb/internal/agent/agent.go#L1379-L1565
[S07]: https://github.com/alibaba/open-code-review/blob/375f64cd6f67a48a135da83cfcf59c52669a09cb/internal/config/template/prompts/grouping_task_system.md#L1-L16
[S08]: https://github.com/alibaba/open-code-review/blob/375f64cd6f67a48a135da83cfcf59c52669a09cb/internal/agent/agent.go#L1740-L1792
[S09]: https://github.com/alibaba/open-code-review/blob/375f64cd6f67a48a135da83cfcf59c52669a09cb/internal/config/template/effort.go#L11-L61
[S10]: https://github.com/alibaba/open-code-review/blob/375f64cd6f67a48a135da83cfcf59c52669a09cb/internal/llmloop/loop.go#L359-L672
[S11]: https://github.com/alibaba/open-code-review/blob/375f64cd6f67a48a135da83cfcf59c52669a09cb/internal/llmloop/compression.go#L19-L30
[S12]: https://github.com/alibaba/open-code-review/blob/375f64cd6f67a48a135da83cfcf59c52669a09cb/internal/config/template/prompts/memory_compression_task_system.md#L1-L30
[S13]: https://github.com/alibaba/open-code-review/blob/375f64cd6f67a48a135da83cfcf59c52669a09cb/internal/config/toolsconfig/tools.json#L1-L214
[S14]: https://github.com/alibaba/open-code-review/blob/375f64cd6f67a48a135da83cfcf59c52669a09cb/internal/tool/code_comment.go#L86-L196
[S15]: https://github.com/alibaba/open-code-review/blob/375f64cd6f67a48a135da83cfcf59c52669a09cb/internal/model/review.go#L1-L29
[S16]: https://github.com/alibaba/open-code-review/blob/375f64cd6f67a48a135da83cfcf59c52669a09cb/internal/llmloop/loop.go#L727-L837
[S17]: https://github.com/alibaba/open-code-review/blob/375f64cd6f67a48a135da83cfcf59c52669a09cb/internal/diff/resolver.go#L12-L145
[S18]: https://github.com/alibaba/open-code-review/blob/375f64cd6f67a48a135da83cfcf59c52669a09cb/internal/diff/relocation.go#L1-L117
[S19]: https://github.com/alibaba/open-code-review/blob/375f64cd6f67a48a135da83cfcf59c52669a09cb/internal/agent/agent.go#L1794-L1923
[S20]: https://github.com/alibaba/open-code-review/blob/375f64cd6f67a48a135da83cfcf59c52669a09cb/internal/config/allowlist/default_exclude_patterns.json#L1-L110
[S21]: https://github.com/alibaba/open-code-review/blob/375f64cd6f67a48a135da83cfcf59c52669a09cb/internal/config/template/prompts/review_filter_task_system.md#L1-L12
[S22]: https://github.com/alibaba/open-code-review/blob/375f64cd6f67a48a135da83cfcf59c52669a09cb/internal/config/template/prompts/review_filter_task_user.md#L1-L85
[S23]: https://github.com/alibaba/open-code-review/blob/375f64cd6f67a48a135da83cfcf59c52669a09cb/internal/agent/coverage_test.go#L271-L396
[S24]: https://github.com/alibaba/open-code-review/blob/375f64cd6f67a48a135da83cfcf59c52669a09cb/internal/config/template/scan_template.json#L1-L87
[S25]: https://github.com/alibaba/open-code-review/blob/375f64cd6f67a48a135da83cfcf59c52669a09cb/internal/scan/agent.go#L98-L430
[S26]: https://github.com/alibaba/open-code-review/blob/375f64cd6f67a48a135da83cfcf59c52669a09cb/internal/scan/agent.go#L990-L1154
[S27]: https://github.com/alibaba/open-code-review/blob/375f64cd6f67a48a135da83cfcf59c52669a09cb/cmd/opencodereview/delegate_cmd.go#L30-L165
[S28]: https://github.com/alibaba/open-code-review/blob/375f64cd6f67a48a135da83cfcf59c52669a09cb/internal/delegate/rulegroup.go#L1-L62
[S29]: https://github.com/alibaba/open-code-review/blob/375f64cd6f67a48a135da83cfcf59c52669a09cb/skills/open-code-review-delegate/SKILL.md#L1-L207
[S30]: https://github.com/alibaba/open-code-review/blob/375f64cd6f67a48a135da83cfcf59c52669a09cb/skills/open-code-review/SKILL.md#L1-L256
[S31]: https://github.com/alibaba/open-code-review/blob/375f64cd6f67a48a135da83cfcf59c52669a09cb/internal/config/rules/system_rules.json#L1-L62
[S32]: https://github.com/alibaba/open-code-review/blob/375f64cd6f67a48a135da83cfcf59c52669a09cb/internal/config/rules/rule_docs/default.md#L1-L22
[S33]: https://github.com/alibaba/open-code-review/blob/375f64cd6f67a48a135da83cfcf59c52669a09cb/internal/config/rules/rule_docs/mapper_dao_xml.md#L1-L33
[S34]: https://github.com/alibaba/open-code-review/blob/375f64cd6f67a48a135da83cfcf59c52669a09cb/internal/config/rules/rule_docs/python.md#L1-L77
[S35]: https://github.com/alibaba/open-code-review/blob/375f64cd6f67a48a135da83cfcf59c52669a09cb/internal/tool/file_read.go#L1-L78
[S36]: https://github.com/alibaba/open-code-review/blob/375f64cd6f67a48a135da83cfcf59c52669a09cb/internal/tool/filereader.go#L25-L140
[S37]: https://github.com/alibaba/open-code-review/blob/375f64cd6f67a48a135da83cfcf59c52669a09cb/internal/tool/code_search.go#L17-L215
[S38]: https://github.com/alibaba/open-code-review/blob/375f64cd6f67a48a135da83cfcf59c52669a09cb/internal/tool/file_find.go#L1-L155
[S39]: https://github.com/alibaba/open-code-review/blob/375f64cd6f67a48a135da83cfcf59c52669a09cb/internal/tool/file_read_diff.go#L1-L74
[S40]: https://github.com/alibaba/open-code-review/blob/375f64cd6f67a48a135da83cfcf59c52669a09cb/internal/config/allowlist/supported_file_types.json#L1-L90
[S41]: https://github.com/alibaba/open-code-review/blob/375f64cd6f67a48a135da83cfcf59c52669a09cb/internal/session/manifest.go#L159-L286
[S42]: https://github.com/alibaba/open-code-review/blob/375f64cd6f67a48a135da83cfcf59c52669a09cb/internal/agent/agent.go#L874-L915
[S43]: https://github.com/alibaba/open-code-review/blob/375f64cd6f67a48a135da83cfcf59c52669a09cb/internal/config/rules/system_rules.go#L310-L664
[S44]: https://github.com/alibaba/open-code-review/blob/375f64cd6f67a48a135da83cfcf59c52669a09cb/internal/config/rules/rule_docs/java.md#L1-L41
[S45]: https://github.com/alibaba/open-code-review/blob/375f64cd6f67a48a135da83cfcf59c52669a09cb/internal/config/rules/rule_docs/ts_js_tsx_jsx.md#L1-L40
[S46]: https://github.com/alibaba/open-code-review/blob/375f64cd6f67a48a135da83cfcf59c52669a09cb/internal/llm/resolver.go#L101-L205
[S47]: https://github.com/alibaba/open-code-review/blob/375f64cd6f67a48a135da83cfcf59c52669a09cb/internal/llm/client.go#L486-L737
[S48]: https://github.com/alibaba/open-code-review/blob/375f64cd6f67a48a135da83cfcf59c52669a09cb/internal/llm/keycmd_windows.go#L1-L50
[S49]: https://github.com/alibaba/open-code-review/blob/375f64cd6f67a48a135da83cfcf59c52669a09cb/internal/session/history.go#L367-L386
[S50]: https://github.com/alibaba/open-code-review/blob/375f64cd6f67a48a135da83cfcf59c52669a09cb/internal/session/persist.go#L228-L337
[S51]: https://github.com/alibaba/open-code-review/blob/375f64cd6f67a48a135da83cfcf59c52669a09cb/internal/llm/raw.go#L1-L110
[S52]: https://github.com/alibaba/open-code-review/blob/375f64cd6f67a48a135da83cfcf59c52669a09cb/internal/session/raw_writer.go#L19-L65
[S53]: https://github.com/alibaba/open-code-review/blob/375f64cd6f67a48a135da83cfcf59c52669a09cb/internal/telemetry/config.go#L14-L100
[S54]: https://github.com/alibaba/open-code-review/blob/375f64cd6f67a48a135da83cfcf59c52669a09cb/cmd/opencodereview/review_cmd.go#L531-L620
[S55]: https://github.com/alibaba/open-code-review/blob/375f64cd6f67a48a135da83cfcf59c52669a09cb/internal/mcp/client.go#L38-L126
[S56]: https://github.com/alibaba/open-code-review/blob/375f64cd6f67a48a135da83cfcf59c52669a09cb/internal/mcp/provider.go#L30-L66
[S57]: https://github.com/alibaba/open-code-review/blob/375f64cd6f67a48a135da83cfcf59c52669a09cb/internal/config/allowlist/default_secret_patterns.json#L1-L12
[S58]: https://github.com/alibaba/open-code-review/blob/375f64cd6f67a48a135da83cfcf59c52669a09cb/internal/diff/relocate_across_files_test.go#L43-L102
[S59]: https://github.com/alibaba/open-code-review/blob/375f64cd6f67a48a135da83cfcf59c52669a09cb/internal/scan/dedup_test.go#L17-L92
[S60]: https://github.com/alibaba/open-code-review/blob/375f64cd6f67a48a135da83cfcf59c52669a09cb/internal/agent/grouping_test.go#L60-L174
[S61]: https://github.com/alibaba/open-code-review/blob/375f64cd6f67a48a135da83cfcf59c52669a09cb/internal/scan/provider.go#L98-L173
[S62]: https://github.com/alibaba/open-code-review/blob/375f64cd6f67a48a135da83cfcf59c52669a09cb/internal/agent/agent.go#L1020-L1108
[S63]: https://github.com/alibaba/open-code-review/blob/375f64cd6f67a48a135da83cfcf59c52669a09cb/internal/llmloop/compression.go#L129-L295
[S64]: https://github.com/alibaba/open-code-review/blob/375f64cd6f67a48a135da83cfcf59c52669a09cb/internal/scan/batch.go#L16-L110
