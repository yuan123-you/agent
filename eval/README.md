# eval — AI 服务评估体系

让后续所有优化"可度量"。数据源取自 `backend` 真实商品库，覆盖**意图准确率 / 工具调用正确率 / RAG 命中率 / 回复质量**四项指标。

## 目录
- `dataset/` 种子数据集（由生成脚本产出，可提交、可复现）
  - `products.json` 商品语料（解析自 `V1__init.sql`）
  - `intent.jsonl` / `tool.jsonl` / `rag.jsonl` / `reply.jsonl` 四指标标注集
  - `kb_large_rag.jsonl` 300 条大规模知识库召回标注（direct/paraphrase/conditional/multi-hop/temporal-region/hard-negative）
- `scripts/generate_dataset.py` 确定性生成（固定随机种子，无需 LLM/外部服务）
- `scripts/run_eval.py` 评估框架，产出 `results/baseline.json`
- `results/baseline.json` 基准线（CI 生成，用于后续对比）

## 运行

```bash
# 1. 生成数据集（解析后端 SQL → 商品语料 + 190+ 条标注）
python scripts/generate_dataset.py

# 2. 跑评估（默认离线模式，CI/无外部服务可复现）
python scripts/run_eval.py            # 人类可读
python scripts/run_eval.py --json     # JSON 输出
```

## 模式与指标口径
- **offline（默认）**：CI 可复现基线。意图/工具/回复用规则代理，RAG 命中率用与上线一致的
  BM25 关键词召回腿计算（复用 `product_index.py` 的 CJK 双字窗切词）。
  真实数值需 live 模式。
- **live**：接真实 LLM + Milvus 管线后计算全量四指标（当前框架预留，未内置）。

| 指标 | 离线口径 |
|------|----------|
| intentAccuracy | 规则分类器命中预期意图的占比 |
| toolCorrectness | 预测工具集与期望工具集交非空占比 |
| ragHitRate | 查询在 BM25 top-5 召回命中期望商品占比 |
| replyQuality | 回复要点覆盖率的代理评分 |

## 与 Langfuse 结合
`ai-service` 已接入 Langfuse 全链路 tracing：
- 每个会话回合一条 trace（`session_id=conversation_id`，绑定 `user_id`），
  下钻可见 **意图(generation) → 工具(span) → RAG(retrieval) → 生成(generation)** 各节点。
- 优化前后跑同批 eval，对比 `baseline.json` 四指标即可量化收益，不再盲改。
## 大规模知识库评测

运行 `python backend/scripts/generate_kb_dataset.py` 会同时重建 300 份合成文档和 `dataset/kb_large_rag.jsonl`。每条标注给出 `expected_doc_key`、`must_hit`、`doc_type` 与难度，可用于 Milvus live 检索或 Agent 端到端回放。当前 `run_eval.py` 的离线商品 BM25 基线不混入该集合，避免把商品索引指标与知识库索引指标混为一谈。


## Answerability 阈值校准

`dataset/rag_answerability.jsonl` 每行是一个 JSON 对象，schema 为：

```json
{"query": "用户问题", "answerable": true, "top1": 0.82, "top2": 0.31}
{"query": "单候选问题", "answerable": true, "top1": 0.58, "top2": null}
```

- `query`：用于人工审阅的数据集问题。
- `answerable`：该问题是否应由当前知识库证据回答的人工标签。
- `top1` / `top2`：生产检索链路最终排序前两项的 evidence score；只有一个候选时 `top2` 必须为 JSON `null`，与生产规则一致，此时分差条件视为满足。

从仓库根目录运行有限阈值网格扫描：

```powershell
python eval/scripts/calibrate_answerability.py --input eval/dataset/rag_answerability.jsonl --output eval/results/answerability-calibration.json
```

输出仅包含按 F1、precision、reject rate 和参数元组稳定排序的 `best` 与 `candidates` 报告；每个候选包含 `min_score`、`high_score`、`min_margin`、`precision`、`recall`、`f1`、`reject_rate`。CLI 只写显式传给 `--output` 的报告，不会修改应用配置或 `.env`。当前生产默认阈值是**未经校准的可运行基线**；是否采用报告候选必须人工评审。
