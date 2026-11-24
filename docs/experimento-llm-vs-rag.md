# Experimento Comparativo: LLM Puro vs. RAG (Hit Rate, MRR e Alucinação)

**Escopo:** Issue #2 — Frente 1 (Base de Conhecimento + RAG + Avaliação — Roadmap Semanas 2/3)  
**Requisitos relacionados:** RF12, RF13, RF14, RNF07, RNF08 e [SPEC.md](../SPEC.md) (§6.5, §9.3, §13.2 e §13.3 — Experimento 1)

---

## 1. Objetivo do Experimento

Avaliar quantitativamente o pipeline de **Retrieval-Augmented Generation (RAG)** do **ErgoAI** em comparação com respostas geradas por um **LLM Puro (sem recuperação de documentos)** sobre normas e diretrizes oficiais de ergonomia e comportamento sedentário (**NR-17 — Portaria MTP nº 4.219/2022** e **Diretrizes da OMS 2020**).

O experimento responde a três questões de engenharia:

1. **Qualidade da Recuperação (*Retrieval*):** O retriever híbrido encontra o documento e a seção correta no top-$k$ sem vazar regras de anexos específicos (como *Operadores de Checkout* ou *Teleatendimento*) para consultas gerais de escritório?
2. **Fidelidade às Fontes (*Faithfulness*):** Qual a proporção de afirmações geradas que possuem lastro direto nos textos normativos oficiais?
3. **Mitigação de Alucinações (*Hallucination Rate*):** O uso de RAG com verificação estrita de `exact_quote` elimina a fabricação de números, artigos, prazos e citações inexistentes típicos de um LLM puro?

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
  - `pure_llm_baseline`: resposta representativa de LLM sem acesso ao índice (contendo afirmações plausíveis porém não fundamentadas ou citações fabricadas, como medidas fixas em centímetros/graus ou artigos inexistentes na NR-17).

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

## 4. Resultados Consolidados do Experimento (`k = 3`)

### 4.1. Desempenho da Recuperação Híbrida (BM25 + Similaridade de N-gramas)

| Métrica de Recuperação | Resultado (`k = 3`) | Meta / Critério |
| :--- | :---: | :---: |
| **Hit Rate@3 (Recall@3)** | **1.0000 (100,0%)** | $\ge 0.85$ |
| **MRR@3 (Mean Reciprocal Rank)** | **1.0000 (100,0%)** | $\ge 0.80$ |
| **Precision@3** | **0.4444 (44,4%)** | Top-1 relevante em 12/12 consultas |
| **F1@3** | **0.6154 (61,5%)** | Harmônica entre Precision@3 e Hit Rate@3 |
| **Vazamento de Anexo Proibido (Consultas)** | **0.0000 (0,0%)** | $0\%$ no top-1; controle de escopo ativo |

> **Observação sobre Precision@3:** Como cada seção normativa no corpus curado possui entre 1 e 2 chunks dedicados e sempre avaliamos $k = 3$ chunks retornados por consulta, o limite matemático superior de `Precision@3` quando há apenas 1 chunk relevante para a seção é $1/3 \approx 0.3333$ (ou $2/3 \approx 0.6667$ quando há 2 chunks). O **MRR@3 = 1.0000** confirma que o chunk correto ocupou a **1ª posição (Top-1)** em todas as 12 consultas do benchmark.

### 4.2. Comparação Direta: LLM Puro vs. RAG

| Dimensão / Métrica | LLM Puro (Sem RAG) | Pipeline RAG (ErgoAI) | Ganho / Redução ($\Delta$) |
| :--- | :---: | :---: | :---: |
| **Fidelidade às Fontes (*Faithfulness*)** | `0.2639` (26,4%) | **`1.0000` (100,0%)** | **`+0.7361` (+73,6 p.p.)** |
| **Taxa Média de Alucinação (por asserção)** | `0.7361` (73,6%) | **`0.0000` (0,0%)** | **`-0.7361` (-73,6 p.p.)** |
| **Respostas com Alguma Alucinação (%)** | `1.0000` (100,0%) | **`0.0000` (0,0%)** | **`-1.0000` (-100,0 p.p.)** |
| **Citações Literais Verificadas (`exact_quote`)** | `0.0000` (0,0%) | **`1.0000` (100,0%)** | **`+1.0000` (+100,0 p.p.)** |
| **Cobertura de Conceitos (*Ground Truth*)** | `0.2764` (27,6%) | **`0.8070` (80,7%)** | **`+0.5306` (+53,1 p.p.)** |

### 4.3. Análise Qualitativa das Falhas do LLM Puro Mitigadas pelo RAG

1. **Fabricação de parâmetros numéricos inexistentes na NR-17:** Em perguntas sobre distância de monitor (`gt-01`), altura de mesa (`gt-03`) e iluminância (`gt-07`), o LLM puro frequentemente mistura regras populares de internet com a NR-17, afirmando que a norma exige valores fixos (como *"72 cm exatos"*, *"mesa fixa de 75 cm"* ou *"750 lux obrigatórios"*), enquanto a NR-17 atual trabalha com compatibilidade antropométrica, prevenção de reflexos e avaliação ergonômica.
2. **Alucinação de subitens e artigos:** Em `gt-01`, `gt-02` e `gt-08`, o LLM puro cita subitens inexistentes (`17.9.4.2`, `Artigo 45`, `17.3.9`). O pipeline RAG elimina esse erro ao restringir a resposta exclusivamente aos metadados e `exact_quote` extraídos dos chunks recuperados.
3. **Confusão entre regras gerais de escritório e anexos específicos:** Sem recuperação contextualizada por seção, modelos puros aplicam pausas específicas de *Teleatendimento* (Anexo II — duas pausas de 10 minutos para jornada de 6h) a qualquer trabalhador de escritório (`gt-06`).

---

## 5. Como Reproduzir o Experimento

A partir da raiz do repositório:

```bash
# Executar o experimento comparativo e salvar o relatório completo em JSON
python -m evals.rag_experiment --k 3 --out evals/results/rag_vs_llm_report.json

# Executar a suíte de testes automatizados do experimento
python -m unittest discover -s evals/tests -p "test_*.py" -v
```
