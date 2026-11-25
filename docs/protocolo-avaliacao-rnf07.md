# Protocolo de Avaliação Quantitativa — RNF07

**Escopo:** Issue #3 (Frente 1 — Base de Conhecimento + RAG + Avaliação)  
**Requisitos relacionados:** RNF07, RN03, RN04, RN05 e `SPEC.md` (§13.1 e §13.2)

---

## 1. Objetivo e separação entre baseline sintético e coleta real

Este protocolo padroniza o cálculo reproduzível de **Precision**, **Recall**, **F1-score**, **False Positive Rate (FPR)**, **Hit Rate@k** e **MRR** em duas frentes complementares:

1. **Parte A — Detecção de desvios posturais:** executa o motor determinístico real em TypeScript (`frontend/src/posture-engine/postureEngine.ts`) via Node.js v24+ (`evals/run_posture_engine.mjs`), sem duplicar fórmulas em Python.
2. **Parte B — Recuperação RAG e recomendações por cartão:** avalia o índice vetorial (`backend/data/chroma`) e o mapeamento de cartões (`knowledge_base/cards/*.yaml`).

> **Separação obrigatória (sintético vs. voluntários reais):** o conjunto inicial da Parte A (`evals/datasets/postura_cenarios.json`) é um **baseline sintético de regressão do motor**, construído exclusivamente com coordenadas numéricas de landmarks (sem fotos, vídeos ou dados pessoais). Ele verifica a lógica de calibração, suavização EMA, histerese, persistência temporal (RN03) e filtros de confiança (RN04/RN05), mas **não substitui** o conjunto rotulado com voluntários reais em condições variadas de câmera e iluminação previsto em `SPEC.md` §13.1 e em [protocolo-coleta-landmarks.md](./protocolo-coleta-landmarks.md).

---

## 2. Parte A — Avaliação de desvios posturais

### 2.1. Escopo, limiares atuais e formato do dataset

- **Arquivo:** `evals/datasets/postura_cenarios.json` (somente coordenadas numéricas compatíveis com `frontend/src/types/coleta.ts`: `t_ms` e `pose` com 13 pontos `{ x, y, z, visibilidade }`).
- **Classes positivas avaliadas pelo motor geométrico (`BASE_THRESHOLDS` em `frontend/src/posture-engine/postureEngine.ts`):**
  - `FORWARD_HEAD`: `thresholdOn = 18.0%` (`hysteresisRatio = 0.78`)
  - `TOO_CLOSE`: `thresholdOn = 18.0%` (`hysteresisRatio = 0.78`)
  - `SHOULDER_TILT`: `thresholdOn = 25.0%` via tangente (`tan(|Δângulo|) * 100`, equivalente a ~`14.04°`; `hysteresisRatio = 0.78`)
  - `HEAD_TILT`: `thresholdOn = 14.0°` (`hysteresisRatio = 0.78`)
- **Classes negativas:** `postura_adequada`, `movimento_momentaneo` (desvio < `4000 ms`, testa RN03) e `baixa_confianca` (visibilidade abaixo de `0.40` ou enquadramento insuficiente, testa RN04/RN05).
- **`BREAK_NEEDED`:** por ser disparado por temporizador de sessão no frontend (e não por landmarks geométricos), não integra a matriz geométrica da Parte A e é avaliado na Parte B (recuperação OMS 2020 + mapeamento de cartão).

### 2.2. Execução sem duplicação de regras

O adaptador `evals/run_posture_engine.mjs` importa diretamente `frontend/src/posture-engine/postureEngine.ts` (via type-stripping nativo do Node v24+), converte `visibilidade` (`frontend/src/types/coleta.ts`) para `visibility` (MediaPipe/`postureEngine.ts`), executa `CalibrationCollector` e `PostureComparator` com timestamps determinísticos e lê `measuredValues` e `activeAlerts` para devolver o resultado em JSON a `evals/eval_metrics.py`. O mesmo formato aceita futuras gravações reais `.jsonl` convertidas para a estrutura de cenários.

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

- **Arquivo:** `evals/datasets/rag_perguntas.yaml`
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
- **Cobertura de cartões:** verifica que todos os códigos em `knowledge_base/cards/_tipos_desvio.yaml` (incluindo `BREAK_NEEDED`) mapeiam para cartões existentes em `knowledge_base/cards/*.yaml`.

---

## 4. Como executar

A partir da **raiz do repositório**:

```bash
# Testes automatizados (backend + knowledge_base + evals; não exigem baixar modelo nem PDFs)
uv run --project backend --extra dev pytest backend/tests knowledge_base/tests evals/tests -rs

# Parte A: motor postural TS real sobre o baseline sintético de landmarks
uv run --project backend python -m evals.eval_metrics --parte postura

# Parte B: recuperação RAG no índice local + cobertura de cartões
uv run --project backend --extra rag python -m evals.eval_metrics --parte rag -k 3

# Ambas as frentes (e salvando JSON opcionalmente)
uv run --project backend --extra rag python -m evals.eval_metrics --parte tudo -k 3
uv run --project backend --extra rag python -m evals.eval_metrics --parte tudo -k 3 --out backend/data/eval_report.json
```

---

## 5. Evolução prevista (coleta com voluntários reais)

Quando a coleta real descrita em [protocolo-coleta-landmarks.md](./protocolo-coleta-landmarks.md) for executada:

1. Manter o dataset sintético (`evals/datasets/postura_cenarios.json`) congelado como teste de regressão determinístico no CI.
2. Armazenar o conjunto de voluntários fora do repositório público (conforme seção 6 do protocolo de coleta), separado por voluntário entre ajuste e teste congelado.
3. Executar `uv run --project backend python -m evals.eval_metrics --parte postura --postura-dataset <caminho_voluntarios.json>` com parâmetros congelados para obter as métricas finais de campo do RNF07.
