# Experimento Comparativo: LLM Puro vs. RAG (Hit Rate, MRR e Alucinação)

**Escopo:** Issue #2 — Frente 1 (Base de Conhecimento + RAG + Avaliação — Roadmap Semanas 2/3)  
**Requisitos relacionados:** RF12, RF13, RF14, RNF07, RNF08 e [SPEC.md](../SPEC.md) (§6.5, §9.3, §13.2, §13.3 — Experimento 1 e §19.5)

---

## 1. Escopo e Transparência Metodológica (`SPEC.md` §19.5)

> **Aviso de Transparência — Harness Determinístico Offline (`evaluation_mode: "offline_deterministic_harness"`):**
> Em estrita conformidade com o `SPEC.md` §19.5 (*Proibição de Implementação Fictícia*), este experimento é rotulado explicitamente como um **benchmark determinístico offline para CI e validação de métricas**, e **não** como resultado de chamadas em tempo real a um LLM em produção (`google-genai`):
> 1. **Corpus Curado Offline (`11 chunks`):** O índice avaliado por [`evals/rag_experiment.py`](../evals/rag_experiment.py) opera sobre os 11 excertos normativos curados em [`evals/datasets/rag_corpus_oficial.json`](../evals/datasets/rag_corpus_oficial.json) via `HybridErgonomicsRetriever` (BM25 + similaridade de n-gramas), de forma independente da ingestão completa de PDFs em `knowledge_base/`.
> 2. **Baseline Estático de LLM Puro (`pure_llm_baseline`):** As respostas avaliadas na coluna "LLM Puro" são **fixtures estáticas representativas** armazenadas em [`evals/datasets/rag_ground_truth.json`](../evals/datasets/rag_ground_truth.json), projetadas para exercitar o detector de alucinações normativas (números fixos inventados, subitens inexistentes e citações não verificáveis).
> 3. **Sintetizador RAG Extrativo Determinístico (`synthesize_grounded_rag_response`):** As respostas na coluna "RAG Extrativo" são construídas por seleção determinística das sentenças de maior interseção lexical dentro do chunk top-1 recuperado, preenchendo `exact_quote` literalmente a partir do texto oficial.

O objetivo deste harness é garantir que as funções de cálculo de **Hit Rate@$k$**, **MRR@$k$**, **Faithfulness**, **Hallucination Rate** e **verificação estrita de `exact_quote`** estejam matematicamente validadas e executáveis no CI sem depender de chaves de API externas.

---

## 2. Conjunto de Dados com Resposta de Referência (*Ground Truth*)

- **Corpus oficial curado:** [`evals/datasets/rag_corpus_oficial.json`](../evals/datasets/rag_corpus_oficial.json) — 11 chunks estruturados segundo o contrato de metadados do `SPEC.md` §6.5 (`document_id`, `title`, `source`, `section`, `page`, `url`, `document_type`), cobrindo:
  - **NR-17 Corpo Principal:** `17.3 Avaliação das situações de trabalho (AEP vs. AET)`, `17.4 Organização do trabalho (sobrecarga muscular e pausas psicofisiológicas)`, `17.6 Mobiliário dos postos de trabalho (bancadas, distância visual, assentos e apoio para os pés)`, `17.7 Equipamentos com terminais de vídeo e computadores portáteis (notebooks)` e `17.8 Condições de conforto (iluminação, reflexos, conforto acústico e térmico)`.
  - **NR-17 Anexos Específicos:** `Anexo I - Trabalho dos Operadores de Checkout` e `Anexo II - Trabalho em Teleatendimento/Telemarketing`.
  - **OMS (2020):** Recomendações para adultos sobre limitação do comportamento sedentário, pausas ativas e volume semanal de atividade física aeróbica moderada/vigorosa.
- **Benchmark Ground Truth:** [`evals/datasets/rag_ground_truth.json`](../evals/datasets/rag_ground_truth.json) — 12 perguntas rotuladas (`gt-01` a `gt-12`), contendo:
  - `question`: pergunta natural sobre ergonomia, adaptação de posto de trabalho ou pausas;
  - `expected_document_id` e `expected_sections`: gabarito de recuperação;
  - `forbidden_sections`: seções que configuram falso positivo por vazamento de escopo;
  - `reference_answer`: resposta padrão-ouro redigida a partir do texto normativo;
  - `required_concepts`: conceitos-chave obrigatórios na resposta;
  - `pure_llm_baseline`: fixture estática de controle contendo desvios típicos de geração sem recuperação (como medidas fixas em centímetros/graus ou artigos inexistentes na NR-17).

---

## 3. Definição Formal das Métricas

### 3.1. Métricas de Recuperação (`k = 3`)

Um chunk recuperado $c$ é considerado **relevante** para a pergunta $q$ se, e somente se:
1. $c.\text{document\_id} = q.\text{expected\_document\_id}$;
2. $c.\text{section} \notin q.\text{forbidden\_sections}$;
3. $c.\text{section} \in q.\text{expected\_sections}$ (quando a lista de seções esperadas não é vazia).

- **Hit Rate@$k$ (Recall@$k$ por consulta):**
  $$\text{Hit Rate@}k = \frac{1}{|Q|} \sum_{q \in Q} \mathbb{I}\left(\exists \, i \le k : c_{q,i} \text{ é relevante}\right)$$
- **Precision@$k$:**
  $$\text{Precision@}k = \frac{1}{|Q|} \sum_{q \in Q} \frac{|\{i \le k : c_{q,i} \text{ é relevante}\}|}{k}$$
- **Mean Reciprocal Rank (MRR@$k$):**
  $$\text{MRR@}k = \frac{1}{|Q|} \sum_{q \in Q} \frac{1}{\text{rank}_q}$$
  onde $\text{rank}_q$ é a posição ($1 \le \text{rank}_q \le k$) do primeiro chunk relevante para a consulta $q$ (ou $\frac{1}{\text{rank}_q} = 0$ caso nenhum chunk relevante apareça no top-$k$).
- **Taxa de Vazamento de Seção Proibida:** proporção de consultas com `forbidden_sections` em que ao menos um chunk proibido apareceu no top-$k$.

### 3.2. Métricas de Geração, Fidelidade e Alucinação

Cada resposta avaliada é decomposta em afirmações atômicas (*claims*) e citações estruturadas (*citations* com `exact_quote`):

- **Verificação Estrita de Citação (`verify_exact_quote_in_corpus`):** uma citação só é válida se seu campo `exact_quote` existir **literalmente como substring normalizada** dentro do chunk do documento e seção citados (`SPEC.md` §9.3: *"Nunca preencher `exact_quote` com texto gerado pelo modelo"*).
- **Suporte Factual de Afirmação (`is_claim_supported_by_texts`):** verifica se os tokens de conteúdo ($\ge 55\%$) e todos os numerais/termos normativos estritos da afirmação constam nos trechos oficiais de suporte.
- **Fidelidade às Fontes (*Faithfulness*):**
  $$\text{Faithfulness} = \frac{\text{Afirmações Suportadas} + \text{Citações Verificadas}}{\text{Total de Afirmações} + \text{Total de Citações}}$$
- **Taxa de Alucinação (*Hallucination Rate*):**
  $$\text{Hallucination Rate} = 1 - \text{Faithfulness} = \frac{\text{Afirmações Sem Lastro} + \text{Citações Fabricadas}}{\text{Total de Afirmações} + \text{Total de Citações}}$$

---

## 4. Resultados Consolidados no Harness Determinístico Offline (`k = 3`)

### 4.1. Desempenho do `HybridErgonomicsRetriever` sobre o Corpus Curado (11 chunks)

| Métrica de Recuperação | Resultado (`k = 3`) | Meta / Critério |
| :--- | :---: | :---: |
| **Hit Rate@3 (Recall@3)** | **1.0000 (100,0%)** | $\ge 0.85$ |
| **MRR@3 (Mean Reciprocal Rank)** | **1.0000 (100,0%)** | $\ge 0.80$ |
| **Precision@3** | **0.4444 (44,4%)** | Top-1 relevante em 12/12 consultas |
| **F1@3** | **0.6154 (61,5%)** | Harmônica entre Precision@3 e Hit Rate@3 |
| **Vazamento de Anexo Proibido (Consultas)** | **0.0000 (0,0%)** | $0\%$ no top-3; controle de escopo ativo |

> **Observação sobre Precision@3:** Como cada seção normativa no corpus curado possui entre 1 e 2 chunks dedicados e sempre avaliamos $k = 3$ chunks retornados por consulta, o limite matemático superior de `Precision@3` quando há apenas 1 chunk relevante para a seção é $1/3 \approx 0.3333$ (ou $2/3 \approx 0.6667$ quando há 2 chunks). O **MRR@3 = 1.0000** confirma que o chunk correto ocupou a **1ª posição (Top-1)** em todas as 12 consultas do benchmark.

### 4.2. Comparação no Harness: Baseline Estático (LLM Puro) vs. RAG Extrativo Determinístico

| Dimensão / Métrica | Baseline Estático (`pure_llm_baseline`) | RAG Extrativo Determinístico | Diferença Medida pelo Avaliador ($\Delta$) |
| :--- | :---: | :---: | :---: |
| **Fidelidade às Fontes (*Faithfulness*)** | `0.2639` (26,4%) | **`1.0000` (100,0%)** | **`+0.7361` (+73,6 p.p.)** |
| **Taxa Média de Alucinação (por asserção)** | `0.7361` (73,6%) | **`0.0000` (0,0%)** | **`-0.7361` (-73,6 p.p.)** |
| **Respostas com Alguma Alucinação (%)** | `1.0000` (100,0%) | **`0.0000` (0,0%)** | **`-1.0000` (-100,0 p.p.)** |
| **Citações Literais Verificadas (`exact_quote`)** | `0.0000` (0,0%) | **`1.0000` (100,0%)** | **`+1.0000` (+100,0 p.p.)** |
| **Cobertura de Conceitos (*Ground Truth*)** | `0.2764` (27,6%) | **`0.8070` (80,7%)** | **`+0.5306` (+53,1 p.p.)** |

### 4.3. Modos de Falha Representados no Baseline e Detectados pelo Harness

1. **Fabricação de parâmetros numéricos inexistentes na NR-17:** Nas fixtures sobre distância de monitor (`gt-01`), altura de mesa (`gt-03`) e iluminância (`gt-07`), o baseline de controle contém valores fixos inventados (*"72 cm exatos"*, *"mesa fixa de 75 cm"*, *"750 lux obrigatórios"*), confirmando que `is_claim_supported_by_texts` rejeita números ausentes da norma.
2. **Alucinação de subitens e artigos:** Em `gt-01`, `gt-02` e `gt-08`, as citações fabricadas (`17.9.4.2`, `Artigo 45`, `17.3.9`) são integralmente barradas por `verify_exact_quote_in_corpus`.
3. **Confusão entre regras gerais de escritório e anexos específicos:** Em `gt-06`, o controle de escopo impede que pausas específicas de *Teleatendimento* (Anexo II) vazem para consultas de escritório geral.

---

## 5. Como Reproduzir o Benchmark Offline

A partir da raiz do repositório:

```bash
# Executar o harness comparativo determinístico e salvar o relatório em JSON
python -m evals.rag_experiment --k 3 --out evals/results/rag_vs_llm_report.json

# Executar a suíte de testes automatizados do experimento
python -m unittest discover -s evals/tests -p "test_*.py" -v
```
