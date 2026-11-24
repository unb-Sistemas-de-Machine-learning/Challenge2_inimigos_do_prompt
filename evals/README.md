# Avaliação e Métricas (`evals/`)

Espaço reservado para datasets rotulados e scripts de avaliação quantitativa do sistema:

- **RAG (`evals/rag_experiment.py`):** Experimento comparativo **LLM puro vs. RAG** medindo *Hit Rate@k*, *MRR@k*, *Precision@k*, fidelidade às fontes (*Faithfulness*), verificação estrita de `exact_quote` e taxa de alucinação sobre o benchmark [`evals/datasets/rag_ground_truth.json`](./datasets/rag_ground_truth.json) e o corpus [`evals/datasets/rag_corpus_oficial.json`](./datasets/rag_corpus_oficial.json).
- **Visão Computacional:** Precision, Recall, F1-score, taxa de falsos positivos e concordância com checklist manual.
- **Segurança:** Taxa de recusa correta para solicitações fora do escopo (diagnóstico/tratamento médico).

## Como Executar o Experimento LLM Puro vs. RAG (Issue #2)

```bash
python -m evals.rag_experiment --k 3 --out evals/results/rag_vs_llm_report.json
python -m unittest discover -s evals/tests -p "test_*.py" -v
```

