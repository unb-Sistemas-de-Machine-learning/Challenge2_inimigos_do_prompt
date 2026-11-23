# Protocolo de Avaliação Quantitativa — RNF07

**Escopo:** Issue #3 (Frente 1 — Base de Conhecimento + RAG + Avaliação)  
**Requisitos relacionados:** RNF07, RN03, RN04, RN05 e `SPEC.md` (§13.1 e §13.2)

---

## 1. Objetivo e separação entre baseline sintético e coleta real

Este protocolo padroniza o cálculo reproduzível de **Precision**, **Recall**, **F1-score**, **False Positive Rate (FPR)**, **Hit Rate@k** e **MRR** em duas frentes complementares:

1. **Parte A — Detecção de desvios posturais:** executa o motor determinístico real do protótipo (`prototipo/js/posture-engine.js`) via Node.js (`eval/run_posture_engine.mjs`), sem duplicar fórmulas em Python.
2. **Parte B — Recuperação RAG e recomendações por cartão:** avalia o índice vetorial (`data/index`) e o mapeamento de cartões (`cards/*.yaml`).

> **Separação obrigatória (sintético vs. voluntários reais):** o conjunto inicial da Parte A (`eval/datasets/postura_cenarios.json`) é um **baseline sintético de regressão do motor**, construído exclusivamente com coordenadas numéricas de landmarks (sem fotos, vídeos ou dados pessoais). Ele verifica a lógica de calibração, suavização EMA, histerese, persistência temporal (RN03) e filtros de confiança (RN04/RN05), mas **não substitui** o conjunto rotulado com voluntários reais em condições variadas de câmera e iluminação previsto em `SPEC.md` §13.1 e em [protocolo-coleta-landmarks.md](./protocolo-coleta-landmarks.md).

---

## 2. Parte A — Avaliação de desvios posturais

### 2.1. Escopo e formato do dataset

- **Arquivo:** `eval/datasets/postura_cenarios.json` (somente coordenadas numéricas compatíveis com `schema/coleta.ts`: `t_ms` e `pose` com 13 pontos `{ x, y, z, visibilidade }`).
- **Classes positivas avaliadas pelo motor geométrico:** `FORWARD_HEAD`, `TOO_CLOSE`, `SHOULDER_TILT` e `HEAD_TILT` (definidas em `BASE_THRESHOLDS` no `posture-engine.js`).
- **Classes negativas:** `postura_adequada`, `movimento_momentaneo` (desvio < `4000 ms`, testa RN03) e `baixa_confianca` (visibilidade abaixo de `0.40` ou enquadramento insuficiente, testa RN04/RN05).
- **`BREAK_NEEDED`:** por ser disparado por temporizador de sessão em `prototipo/js/app.js` (e não por landmarks geométricos), não integra a matriz geométrica da Parte A e é avaliado na Parte B (recuperação OMS 2020 + mapeamento de cartão).

### 2.2. Execução sem duplicação de regras

O adaptador `eval/run_posture_engine.mjs` importa diretamente `prototipo/js/posture-engine.js`, converte `visibilidade` (`schema/coleta.ts`) para `visibility` (MediaPipe/`posture-engine.js`), executa `CalibrationCollector` e `PostureComparator` com timestamps determinísticos e devolve o resultado em JSON para `pipeline/eval_metrics.py`. O mesmo formato aceita futuras gravações reais `.jsonl` convertidas para a estrutura de cenários.

### 2.3. Fórmulas das métricas (RNF07)

Para cada classe `c` em `{FORWARD_HEAD, TOO_CLOSE, SHOULDER_TILT, HEAD_TILT}` (e também para a visão binária global "qualquer alerta emitido" vs. "cenário sem desvio"):

- `TP`: cenário rotulado como `c` em que o motor disparou alerta para `c`.
- `FP`: cenário não rotulado como `c` em que o motor disparou alerta para `c`.
- `FN`: cenário rotulado como `c` em que o motor não disparou alerta para `c`.
- `TN`: cenário não rotulado como `c` em que o motor não disparou alerta para `c`.

Fórmulas (com retorno `0.0` quando o denominador for zero):

- `Precision = TP / (TP + FP)`
- `Recall = TP / (TP + FN)`
- `F1 = 2 * Precision * Recall / (Precision + Recall)`
- `FPR = FP / (FP + TN)`

O relatório apresenta métricas **por classe**, **média macro**, **média micro**, **binário de alerta**, **taxa de quadros `LOW_CONFIDENCE`** e **latência média por cenário** (ressalvando que mede apenas o motor geométrico em Node.js, sem MediaPipe).

---

## 3. Parte B — Avaliação de recomendações e recuperação RAG

### 3.1. Formato do dataset

- **Arquivo:** `eval/datasets/rag_perguntas.yaml`
- Cada item define: `id`, `pergunta`, `document_id_esperado` (`nr17` ou `oms2020`), `secoes_esperadas`, `secoes_proibidas` e, quando aplicável, `tipo_desvio` e `cartao_esperado`.
- **Casos realistas e detecção de vazamento de anexo:** consultas de trabalho geral em escritório incluem `Anexo I - Trabalho dos Operadores de Checkout` e `Anexo II - Trabalho em Teleatendimento/Telemarketing` em `secoes_proibidas`, permitindo medir objetivamente falsos positivos quando regras específicas de checkout ou teleatendimento vazam para perguntas gerais.

### 3.2. Fórmulas das métricas (top-`k`)

Um chunk recuperado é **relevante** quando atende simultaneamente: `document_id == document_id_esperado`, não pertence a `secoes_proibidas` e (quando `secoes_esperadas` não é vazia) pertence a `secoes_esperadas`.

- `Precision@k`: média entre consultas de `(# chunks relevantes no top-k) / k`.
- `Recall@k / Hit Rate@k`: fração de consultas com ao menos 1 chunk relevante no top-`k`.
- `F1@k`: média harmônica entre `Precision@k` e `Hit Rate@k`.
- `MRR@k`: média entre consultas de `1 / rank` do primeiro chunk relevante (`0` se não houver acerto no top-`k`).
- `FPR de vazamento de seção proibida`:
  - **por chunk:** `chunks em secoes_proibidas / total de chunks avaliados nas consultas com secoes_proibidas`;
  - **por consulta:** `consultas com ao menos 1 chunk proibido / consultas com secoes_proibidas`.
- **Cobertura de cartões:** verifica que todos os códigos em `cards/_tipos_desvio.yaml` (incluindo `BREAK_NEEDED`) mapeiam para cartões existentes em `cards/*.yaml`.

---

## 4. Como executar

A partir da pasta `pipeline-dados/`:

```bash
# Testes automatizados (não exigem baixar modelo nem PDFs reais)
.venv/bin/python -m pytest -rs

# Parte A: motor postural real sobre o baseline sintético de landmarks
.venv/bin/python -m pipeline.eval_metrics --parte postura

# Parte B: recuperação RAG no índice local + cobertura de cartões
.venv/bin/python -m pipeline.eval_metrics --parte rag -k 3

# Ambas as frentes (e salvando JSON opcionalmente)
.venv/bin/python -m pipeline.eval_metrics --parte tudo -k 3
.venv/bin/python -m pipeline.eval_metrics --parte tudo -k 3 --out data/eval_report.json
```

---

## 5. Evolução prevista (coleta com voluntários reais)

Quando a coleta real descrita em [protocolo-coleta-landmarks.md](./protocolo-coleta-landmarks.md) for executada:

1. Manter o dataset sintético (`postura_cenarios.json`) congelado como teste de regressão determinístico no CI.
2. Armazenar o conjunto de voluntários fora do repositório público (conforme seção 6 do protocolo de coleta), separado por voluntário entre ajuste e teste congelado.
3. Executar `python -m pipeline.eval_metrics --parte postura --postura-dataset <caminho_voluntarios.json>` com parâmetros congelados para obter as métricas finais de campo do RNF07.
