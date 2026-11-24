# Avaliação e Métricas (`evals/`)

Espaço reservado para datasets rotulados e scripts de avaliação quantitativa do sistema:

- **RAG:** Hit Rate, MRR e fidelidade às fontes (LLM puro vs. RAG).
- **Visão Computacional (`evals/vision_checklist_eval.py`):** Avaliação de concordância do Agente de Visão (`SetupAnalysis`) com o checklist manual de 6 dimensões da NR-17 aplicado pela equipe em fotos rotuladas ([`evals/datasets/vision_setup_checklist.json`](./datasets/vision_setup_checklist.json)), calculando Taxa de Concordância, Kappa de Cohen ($\kappa$), Precision, Recall, F1-score e calibração de confiança.
- **Segurança:** Taxa de recusa correta para solicitações fora do escopo (diagnóstico/tratamento médico).

## Como Executar a Avaliação do Agente de Visão (Issue #4)

```bash
python -m evals.vision_checklist_eval --out evals/results/vision_checklist_report.json
python -m unittest discover -s evals/tests -p "test_*.py" -v
```
