# Avaliação e Métricas (`evals/`)

Esta pasta centraliza datasets rotulados (sem mídia ou dados pessoais) e scripts de avaliação quantitativa do sistema (RNF07 / `SPEC.md` §13.1, §13.2 e §13.3):

- **Visão / Motor Postural (Parte A):** executa diretamente [frontend/src/posture-engine/postureEngine.ts](../frontend/src/posture-engine/postureEngine.ts) via Node.js v24+ (`evals/run_posture_engine.mjs`) sobre cenários numéricos de landmarks (`evals/datasets/postura_cenarios.json`) e calcula Precision, Recall, F1-score e FPR.
- **RAG e Cartões (Parte B):** avalia o índice vetorial (`backend/data/chroma`) com perguntas rotuladas (`evals/datasets/rag_perguntas.yaml`), medindo Precision@k, Recall@k / Hit Rate@k, F1@k, MRR@k, FPR de vazamento de anexos da NR-17 e cobertura dos cartões em `knowledge_base/cards/`.
- **Experimento Comparativo LLM Puro vs. RAG (`evals/rag_experiment.py`):** compara *Hit Rate@k*, *MRR@k*, *Precision@k*, fidelidade às fontes (*Faithfulness*), verificação estrita de `exact_quote` e taxa de alucinação sobre [`evals/datasets/rag_ground_truth.json`](./datasets/rag_ground_truth.json) e [`evals/datasets/rag_corpus_oficial.json`](./datasets/rag_corpus_oficial.json).

## Estrutura

- `datasets/postura_cenarios.json`: baseline sintético de regressão (22 cenários numéricos compatíveis com `frontend/src/types/coleta.ts`).
- `datasets/rag_perguntas.yaml`: 14 perguntas rotuladas (escritório geral com Anexos I/II proibidos, OMS 2020 e consultas específicas de Anexo I/II).
- `datasets/rag_corpus_oficial.json` e `datasets/rag_ground_truth.json`: corpus oficial e ground truth do experimento comparativo LLM puro vs. RAG (Issue #2).
- `run_posture_engine.mjs`: adaptador fino ESM em Node.js que importa `postureEngine.ts` nativamente.
- `eval_metrics.py`: cálculo das métricas RNF07 e CLI.
- `rag_experiment.py`: pipeline comparativo LLM puro vs. RAG.
- `tests/`: suíte de testes unitários e de integração da avaliação.

## Como executar (a partir da raiz do repositório)

```bash
# Testes automatizados (backend + knowledge_base + evals)
uv run --project backend --extra dev pytest backend/tests knowledge_base/tests evals/tests -rs

# Parte A: motor postural TS real sobre o baseline sintético
uv run --project backend python -m evals.eval_metrics --parte postura

# Parte B: recuperação RAG no índice local + cobertura de cartões
uv run --project backend --extra rag python -m evals.eval_metrics --parte rag -k 3

# Experimento comparativo LLM Puro vs. RAG (Issue #2)
python -m evals.rag_experiment --k 3 --out evals/results/rag_vs_llm_report.json
```

Para detalhes metodológicos, fórmulas e separação entre baseline sintético e coleta futura com voluntários, consulte [docs/protocolo-avaliacao-rnf07.md](../docs/protocolo-avaliacao-rnf07.md) e [docs/experimento-llm-vs-rag.md](../docs/experimento-llm-vs-rag.md).
