# 语义路由专项验收（2026-10-31）

## 发布门禁

本报告先记录已通过的独立实例验收；生产 HTTP/SSE 验收结果在部署后补充。未把离线词表基线或 mock 测试分数当作模型准确率。

## 本轮修复范围

- 删除业务关键词路由与“不满意”词表追问，使用经过校验的意图/下一步决策。高置信首轮由现有向量模型匹配；歧义与多轮上下文交给专用意图模型。
- “未明确目标的购后求助”“询问资格/政策”“明确申请办理”分别进入受控澄清、证据检索、现有订单工具流程。订单/退款仍受归属校验与确认卡约束。
- 保留已部署的知识证据完整性、引用校验、防照搬、终端渲染优先于内部流式 JSON 等保护。
- 每轮重置临时决策/查询；多轮保留经校验的业务焦点；重生成清理失败轮次焦点。用户内容不升级到系统指令。

## 实际运行配置

- 意图模型：`qwen3:4b-instruct`，Ollama 模型 ID `0edcdef34593`，约 2.5 GB。指令专用模型，无思考输出；分类输出上限 128。
- 独立 Ollama 0.40.1，ARM64 CPU 推理，7 GiB 内存 / 2 CPU 上限，内网端点，无公共端口。
- 回答生成仍为 `qwen2.5:1.5b`；向量模型仍为 `shaw/dmeta-embedding-zh`、768 维，集合和业务数据不变。
- 路由使用 32 条固定语义示例，绝对 cosine 门槛 0.78、不同决策差值 0.06；上下文轮次主动交给模型。余弦分数不是概率，不承诺任意输入都正确。
- 实测专用意图进程约 3.59 GiB；已有生成进程约 2.03 GiB。专用模型首次加载/静态前缀预热 46.81 秒，启动预算提升到 180 秒，两个提供商预热失败相互隔离。就绪探针检查意图服务与指定模型是否可用。

## 真实语义链路验收

**45/45 通过**。实际调用向量与意图模型，再执行生产控制器和工具规划；不执行订单/退款/人工工具。包含原截图原句、未收录在语义示例中的口语表达、资格询问、明确办理、退货后补原因、预算补充、话题切换、规则指代、否定/假设/引用转人工、批评助手。

场景计时包含构造历史焦点所需的前序路由，**不是完整 HTTP 回答延迟**。本轮最小 0.06 秒，中位 3.82 秒，最大 19.53 秒。完整回答仍由已有 CPU 模型生成，不承诺即时或高并发响应。

| 场景 | 最新消息 | 预期意图 / 下一步 | 实际来源 | 秒 |
| --- | --- | --- | --- | ---: |
| screenshot | 到货后不满意怎么办 | AFTER_SALE_FAQ / clarify | embedding | 0.18 |
| dev-indirect | 实物和期待差了一截，能给我出个主意吗 | AFTER_SALE_FAQ / clarify | model | 5.67 |
| dev-qualify | 东西已经用过还能退吗 | AFTER_SALE_FAQ / retrieve | embedding | 0.13 |
| dev-return | 我决定把这件退掉，麻烦处理 | ORDER_QUERY / assist | model | 3.19 |
| dev-invoice | 发票要怎么弄 | AFTER_SALE_FAQ / retrieve | model | 3.36 |
| dev-description | 货跟页面说的根本对不上 | AFTER_SALE_FAQ / clarify | model | 3.09 |
| new-unhappy | 买回来的玩意儿看着就不舒坦，找你支个招 | AFTER_SALE_FAQ / clarify | model | 3.91 |
| new-package | 快递拿到了，但有种不是我想要的感觉 | AFTER_SALE_FAQ / clarify | model | 3.22 |
| new-fit | 上脚之后总感觉不对头，能帮我看看怎么办吗 | AFTER_SALE_FAQ / clarify | model | 3.82 |
| new-description | 发现外观跟下单时看的差不少，我现在怎么处理 | AFTER_SALE_FAQ / clarify | model | 3.95 |
| new-washed | 洗过一次之后还在可退的范围内不 | AFTER_SALE_FAQ / retrieve | model | 3.2 |
| new-postage | 讲一下返程邮费到底由哪边负担 | AFTER_SALE_FAQ / retrieve | embedding | 0.06 |
| new-return-goal | 不用再给方案了，直接帮我走退回这件的流程 | ORDER_QUERY / assist | model | 3.87 |
| new-money-goal | 东西我留不下，给我申请退回实付的金额 | ORDER_QUERY / assist | model | 3.77 |
| new-switch | 先停一下推荐，查查我上周的那单 | ORDER_QUERY / assist | model | 3.74 |
| new-criticism | 我说你回复得不对，跟商品没关系 | SMALL_TALK / assist | model | 3.28 |
| new-negative-human | 并不是要找真人，你先说说保修有多长 | AFTER_SALE_FAQ / retrieve | model | 3.49 |
| new-future-human | 以后有需要再找人工，现在不用转 | SMALL_TALK / assist | model | 3.24 |
| context-return | 就是试了下感觉不合脚 | ORDER_QUERY / assist | model | 12.5 |
| context-budget | 两千五上下 | PRODUCT_CONSULT / assist | model | 14.0 |
| context-policy | 如果是卖家漏发或者发错，我还得付运费吗 | AFTER_SALE_FAQ / retrieve | model | 15.28 |
| context-exchange | 我需要把这件换成相同规格的新件 | ORDER_QUERY / assist | model | 7.31 |
| holdout-unhappy | 这次购物给我的感觉不怎么样，想听听你的处理建议 | AFTER_SALE_FAQ / clarify | embedding | 0.2 |
| holdout-physical | 刚收到实物，心里有些落差，我该找你做点什么 | AFTER_SALE_FAQ / clarify | model | 5.0 |
| holdout-eligibility | 试穿过而且拆了包装，是否还具备申请资格 | AFTER_SALE_FAQ / retrieve | model | 3.46 |
| holdout-fee | 如果是卖家寄错了，回邮的费用该算哪一方 | AFTER_SALE_FAQ / retrieve | embedding | 0.25 |
| holdout-refund | 我不准备保留这个了，请协助我把付的钱退回来 | ORDER_QUERY / assist | model | 3.84 |
| holdout-complaint | 我是在说你回答不靠谱，不是在讲商品 | SMALL_TALK / assist | model | 3.1 |
| holdout-no-transfer | 先不用给我找客服，我还没提出这个要求 | SMALL_TALK / assist | model | 3.51 |
| holdout-return-reason | 穿着紧，主要就是这个原因 | ORDER_QUERY / assist | model | 13.8 |
| holdout-price | 最多三千五百 | PRODUCT_CONSULT / assist | model | 9.0 |
| holdout-policy-followup | 那寄送的费用呢 | AFTER_SALE_FAQ / retrieve | model | 19.53 |
| independent-policy-colloquial | 吊牌已经剪下来了，还能算在可换的条件里不 | AFTER_SALE_FAQ / retrieve | model | 6.36 |
| independent-problem-no-goal | 零件少了一个，心里有点堵，这事咋办比较好 | AFTER_SALE_FAQ / clarify | model | 3.92 |
| independent-request-exchange | 请把发来的这台换成一个没有瑕疵的 | ORDER_QUERY / assist | model | 3.31 |
| independent-order-tracking | 替我看看之前付过钱的那一单进展到哪一步了 | ORDER_QUERY / assist | model | 3.59 |
| independent-hypothetical-human | 真到需要人工那天我会再开口，现在不用 | SMALL_TALK / assist | model | 3.87 |
| independent-quoted-human | 你刚才说的“转人工”三个字是什么意思，我没有要求转接 | SMALL_TALK / assist | model | 4.11 |
| independent-complaint-only | 你老是答非所问，是你的理解出了问题 | SMALL_TALK / assist | model | 3.3 |
| independent-policy-denial | 不是要现在退，我只想确认拆了包装之后的适用条件 | AFTER_SALE_FAQ / retrieve | model | 3.6 |
| independent-shopping-paraphrase | 宿舍空间小，想挑一台不占地方的风扇 | PRODUCT_CONSULT / assist | model | 3.99 |
| independent-context-switch | 先不买了，我想看看上次订单的物流 | ORDER_QUERY / assist | model | 12.52 |
| independent-context-return-goal | 走路时脚趾被挤得难受 | ORDER_QUERY / assist | model | 14.39 |
| independent-context-shopping-switch | 换个事，想找一副运动时戴的耳机 | PRODUCT_CONSULT / assist | model | 14.33 |
| independent-context-policy-reference | 那超出期限之后呢 | AFTER_SALE_FAQ / retrieve | model | 14.86 |

## 未通过的实验（没有发布）

- 原 `qwen2.5:1.5b` 在真实多轮场景中遗忘已明确的退货目标，不能用单元测试通过掩盖。
- `qwen2.5:7b` 的固定 32 场景验收为 29/32：一次冷启动超时，两条资格询问误判。`qwen3:8b` 非思考诊断仍误判资格询问。未用于生产。
- 新指令模型在此前暂定的 0.70 向量门槛下为 44/45：缺件但未表明办理目标的求助被向量提前判成办理。恢复保守 0.78 门槛后完整重跑为 45/45；没有改提示词、添加匹配关键词或将失败句补成语义示例。
- 实验期间拒绝的关系门控、额外目标检查等未并入生产。

## 软件回归与审查

- `ai-service`: 663 通过。
- `eval/tests` + 凭据卫生：33 通过；旧词表比较器只留在显式标为历史/离线的评估代码，不再用于生产或冒充 live 分数。
- `git diff --check` 通过。
- 专用提供商集成审查发现并修复“意图预热失败会跳过生成预热”；HTTP 失败和实际超时均有红绿回归。专用意图模型缺失/服务不可达的就绪降级有测试。
- 额外历史部署静态测试 11 通过、1 既存失败：购物车缺少旧测试要求的“模拟支付”字样。已核对 HEAD，测试及两个相关前端文件均未改动；本轮不修改无关 UI，不宣称全仓库测试全部通过。

## 生产验收

待部署后补充。只使用既有专用 QA 账号并恢复禁用状态；不使用普通买家，不确认任何交易或售后卡片，不改写历史消息。
