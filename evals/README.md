# Avaliação e Métricas (`evals/`)

Espaço reservado para datasets rotulados e scripts de avaliação quantitativa do sistema:

- **RAG:** Hit Rate, MRR e fidelidade às fontes (LLM puro vs. RAG).
- **Visão Computacional & Motor Postural (`evals/posture_heuristics_eval.py`):** Validação empírica dos limiares de `frontend/src/posture-engine/postureEngine.ts` (`v1.1.0-post-mvp`), ablação dos pesos `TOO_CLOSE` (60% olhos / 40% ombros), confirmação de latência `RNF01 <= 500 ms`, avaliação dos novos padrões pós-MVP (`ELEVATED_SHOULDERS`, `TRUNK_ROTATION`, `PROLONGED_ABSENCE`) e perfis de calibração (`notebook` vs. `external_monitor`).
- **Segurança:** Taxa de recusa correta para solicitações fora do escopo (diagnóstico/tratamento médico).

## Como Executar a Validação de Limiares e Padrões Posturais (Issue #13)

```bash
python -m evals.posture_heuristics_eval --out evals/results/posture_heuristics_report.json
python -m unittest discover -s evals/tests -p "test_*.py" -v
```
