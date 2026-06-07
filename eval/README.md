# Eval 工具说明

本目录放离线评估脚本和报告。评估只读商品数据，不调用真实 LLM。

## RAG Retrieval Eval

运行 keyword 模式：

```powershell
cd backend
uv run python ..\eval\rag_retrieval_runner.py --retriever-mode keyword --top-k 3
```

脚本会读取 `eval/rag_retrieval_cases.jsonl`，输出：

- `eval/rag_retrieval_report.md`
- `eval/rag_retrieval_report.json`

第一版指标是观察值，不作为强门禁；失败样本会写入报告，命令仍返回成功。核心指标包括 `hit@k`、`recall@k`、品类/品牌命中率、no results 率、负反馈排除命中率，以及候选/召回/最终数量均值。

运行 vector 模式：

```powershell
cd backend
uv run python ..\eval\rag_retrieval_runner.py --retriever-mode vector --top-k 3
```

vector 模式依赖本地 Chroma 索引和 embedding 配置；依赖不可用时样本会标记为 skipped，不误报为业务失败。

## Context Memory Eval

上下文记忆评估覆盖多轮偏好保留、跨品类切换、历史需求恢复和负反馈应用。脚本使用内存会话、固定推荐结果和确定性理解兜底，不调用真实 LLM。

运行：

```powershell
cd backend
uv run python ..\eval\context_memory_runner.py --min-pass-rate 1.0
```

脚本会读取 `eval/context_memory_cases.jsonl`，输出：

- `eval/context_memory_report.md`

`--min-pass-rate` 默认是 `1.0`；低于阈值时命令返回非零退出码，适合作为上下文工程的本地质量门禁。
