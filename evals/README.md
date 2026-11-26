# Avaliação e Métricas (`evals/`)

Esta pasta centraliza datasets rotulados (sem mídia ou dados pessoais) e scripts de avaliação quantitativa do sistema (RNF07 / `SPEC.md` §13.1, §13.2 e §13.3):

- **Visão / Motor Postural (Parte A — `evals/run_posture_engine.mjs` & `evals/eval_metrics.py`):** executa diretamente [frontend/src/posture-engine/postureEngine.ts](../frontend/src/posture-engine/postureEngine.ts) via Node.js v24+ sobre cenários numéricos de landmarks (`evals/datasets/postura_cenarios.json`) e calcula Precision, Recall, F1-score e FPR.
- **Validação de Limiares, Latência RNF01 e Evolução Pós-MVP (`evals/posture_heuristics_eval.py`):** validação dos limiares de `postureEngine.ts` (`v1.1.0-post-mvp`), ablação dos pesos `TOO_CLOSE` (60% olhos / 40% ombros), confirmação de latência `RNF01 <= 500 ms`, avaliação dos padrões pós-MVP (`ELEVATED_SHOULDERS`, `TRUNK_ROTATION`, `PROLONGED_ABSENCE`) e perfis de calibração (`notebook` vs. `external_monitor`).
- **RAG e Cartões (Parte B):** avalia o índice vetorial (`backend/data/chroma`) com perguntas rotuladas (`evals/datasets/rag_perguntas.yaml`), medindo Precision@k, Recall@k / Hit Rate@k, F1@k, MRR@k, FPR de vazamento de anexos da NR-17 e cobertura dos cartões em `knowledge_base/cards/`.

## Estrutura

- `datasets/postura_cenarios.json`: baseline sintético de regressão (22 cenários numéricos compatíveis com `frontend/src/types/coleta.ts`).
- `datasets/posture_heuristics_scenarios.json`: cenários temporais pós-MVP e perfis de calibração (Issue #13).
- `datasets/rag_perguntas.yaml`: 14 perguntas rotuladas (escritório geral com Anexos I/II proibidos, OMS 2020 e consultas específicas de Anexo I/II).
- `run_posture_engine.mjs`: adaptador fino ESM em Node.js que importa `postureEngine.ts` nativamente.
- `eval_metrics.py`: cálculo das métricas RNF07 e CLI.
- `posture_heuristics_eval.py`: validação de limiares, pesos `TOO_CLOSE`, latência e perfis de calibração.
- `tests/`: suíte de testes unitários e de integração da avaliação.

## Como executar (a partir da raiz do repositório)

```bash
# Testes automatizados (backend + knowledge_base + evals)
uv run --project backend --extra dev pytest backend/tests knowledge_base/tests evals/tests -rs

# Parte A: motor postural TS real sobre o baseline sintético
uv run --project backend python -m evals.eval_metrics --parte postura

# Parte B: recuperação RAG no índice local + cobertura de cartões
uv run --project backend --extra rag python -m evals.eval_metrics --parte rag -k 3

# Validação de limiares, ablação TOO_CLOSE e latência RNF01 (Issue #13)
python -m evals.posture_heuristics_eval --out evals/results/posture_heuristics_report.json
```

Para detalhes metodológicos, fórmulas e separação entre baseline sintético e coleta futura com voluntários, consulte [docs/protocolo-avaliacao-rnf07.md](../docs/protocolo-avaliacao-rnf07.md) e [docs/validacao-limiares-padroes-posturais.md](../docs/validacao-limiares-padroes-posturais.md).
