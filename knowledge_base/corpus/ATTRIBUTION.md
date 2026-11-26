# Atribuição de Fontes e Licenças do Corpus (`knowledge_base/corpus/`)

Este diretório versiona o corpus processado (`chunks.jsonl` e `manifest.json`) utilizado pelo ErgoAI para reconstruir o índice vetorial (`backend/data/chroma`) e alimentar a busca lexical (BM25) sem versionar os PDFs brutos (`knowledge_base/raw/` permanece fora do Git).

## Fontes incluídas

### 1. OMS — *WHO guidelines on physical activity and sedentary behaviour* (`document_id: oms2020`)

- **Autor / Órgão emissor:** World Health Organization (WHO), 2020.
- **Página oficial da publicação:** https://www.who.int/publications/i/item/9789240015128
- **Licença original:** Creative Commons Attribution-NonCommercial-ShareAlike 3.0 IGO (**CC BY-NC-SA 3.0 IGO**) — https://creativecommons.org/licenses/by-nc-sa/3.0/igo/
- **Modificações realizadas:** extração automatizada de texto a partir do PDF oficial (`pypdf`), remoção heurística de cabeçalhos/rodapés repetidos, normalização de quebras de linha e segmentação em chunks (`max_chars=1000`, `overlap_chars=150`) com inclusão de metadados estruturados (`spec-6.5-v1`) em `chunks.jsonl`.
- **Condições de uso e compartilhamento (ShareAlike):** os chunks derivados desta obra incluídos em `chunks.jsonl` são distribuídos exclusivamente para fins **não comerciais** (uso acadêmico/educativo) sob a mesma licença **CC BY-NC-SA 3.0 IGO**. A utilização do texto neste projeto não implica endosso ou aprovação pela Organização Mundial da Saúde.

### 2. Ministério do Trabalho e Emprego — Norma Regulamentadora nº 17 — Ergonomia (`document_id: nr17`)

- **Órgão emissor:** Ministério do Trabalho e Emprego (Brasil).
- **Versão registrada:** Portaria MTP nº 4.219/2022 (20/12/2022).
- **Página oficial de referência:** https://www.gov.br/trabalho-e-emprego/pt-br/acesso-a-informacao/participacao-social/conselhos-e-orgaos-colegiados/comissao-tripartite-partitaria-permanente/normas-regulamentadora/normas-regulamentadoras-vigentes/norma-regulamentadora-no-17-nr-17
- **Regime de uso:** ato normativo oficial de acesso público (`gov.br`).
- **Modificações realizadas:** extração automatizada de texto a partir do PDF oficial (`pypdf`), limpeza de cabeçalhos/rodapés repetidos, segmentação em chunks (`max_chars=1000`, `overlap_chars=150`) e atribuição heurística de `section` (corpo geral `17.1`–`17.8`, Anexo I e Anexo II, conforme `docs/adr/0002-contrato-metadados-indice-e-secoes.md`).

## Integridade e fontes primárias

- Nenhum PDF bruto é versionado neste repositório.
- Os hashes `sha256` esperados dos PDFs originais estão registrados em `knowledge_base/sources.yaml` e `knowledge_base/corpus/manifest.json` para validação de integridade sempre que a ingestão for executada a partir de `knowledge_base/raw/`.
