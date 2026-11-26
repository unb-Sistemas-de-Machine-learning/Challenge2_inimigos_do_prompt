# ADR 0002 — Contrato de metadados do índice vetorial e heurística de `section`

- **Status:** ACEITA (v1)
- **Data:** 2026-11-21
- **Responsável:** Engenheiro de Dados
- **Relacionada a:** [ADR 0001](./0001-embeddings-vector-store-e-chunking.md), `SPEC.md` §6.5

## Contexto

Na v0 do pipeline de ingestão, os chunks gravados no ChromaDB usavam metadados em português (`fonte_id`, `titulo`, `versao`, `licenca`, `pagina`, `chunk`). Isso gerava dois problemas:

1. **Divergência com o `SPEC.md` §6.5**, que define o contrato de metadados com as chaves `document_id`, `title`, `source`, `section`, `page`, `url` e `document_type`.
2. **Contaminação de contexto na NR-17:** sem o campo `section`, trechos dos **Anexo I** (Trabalho dos Operadores de Checkout) e **Anexo II** (Trabalho em Teleatendimento/Telemarketing) eram recuperados pelo RAG sem indicação de anexo, misturando regras específicas desses regimes com o corpo geral da norma (ex.: consultas sobre altura/regulagem de monitor retornando regras específicas do Anexo II de teleatendimento).

## Decisão

### 1. Contrato de metadados no ChromaDB e `chunks.jsonl` (`METADATA_SCHEMA_VERSION = "spec-6.5-v1"`)

Cada chunk na coleção `ergonomia` (`backend/data/chroma`) e na exportação JSONL para BM25 (`knowledge_base/processed/chunks.jsonl`) grava os **7 campos obrigatórios do `SPEC.md` §6.5** mais **3 campos complementares** de rastreabilidade interna:

| Campo | Origem | Observação |
|---|---|---|
| `document_id` | `knowledge_base/sources.yaml` (`id`) | Substitui `fonte_id` |
| `title` | `knowledge_base/sources.yaml` (`titulo`) | Substitui `titulo` |
| `source` | `knowledge_base/sources.yaml` (`source`) | Órgão/entidade emissora |
| `section` | Heurística em `knowledge_base/ingest.py` | Ver seção 3 abaixo (`"unspecified"` quando não identificável) |
| `page` | Número da página (1-based) | Substitui `pagina` |
| `url` | `knowledge_base/sources.yaml` (`url_oficial`) | URL oficial da fonte |
| `document_type` | `knowledge_base/sources.yaml` (`document_type`) | Ver seção 2 abaixo |
| `version` | `knowledge_base/sources.yaml` (`versao`) | Complementar (rastreabilidade de versão da fonte por chunk) |
| `license` | `knowledge_base/sources.yaml` (`licenca`) | Complementar (governança de uso/citação) |
| `chunk` | Índice do chunk na página (0-based) | Complementar (ordenação intra-página) |

Em `knowledge_base/sources.yaml`, as chaves existentes em português (`id`, `titulo`, `url_oficial`, `arquivo_local`, `versao`, `licenca`, `data_acesso`) foram mantidas para preservar compatibilidade total com `knowledge_base/cards.py` e `knowledge_base/cards/*.yaml`, adicionando apenas `source` e `document_type`.

### 2. Valor de `document_type`

O `SPEC.md` §6.5 apresenta `"official"` como exemplo de estrutura, sem definir um enum fechado. Adotamos `"official"` para as duas fontes atuais (`nr17` e `oms2020`), por serem atos/diretrizes oficiais de órgãos públicos/intergovernamentais (MTE e OMS). Caso novas categorias de documentos sejam adicionadas no futuro (ex.: artigos científicos ou guias técnicos), a taxonomia poderá ser estendida explicitamente em `knowledge_base/sources.yaml` e documentada em revisão desta ADR.

### 3. Heurística transparente para `section`

Implementada na função pura e testável `atualizar_secao(texto_chunk, secao_atual) -> (secao_chunk, proxima_secao)` em `knowledge_base/ingest.py`, propagando a seção ativa ao longo das páginas e atualizando por chunk:

1. **Prioridade de Anexos (NR-17):** reconhece cabeçalhos reais de anexo em caixa alta (`ANEXO I da NR 17`, `ANEXO II da NR 17`) seguidos de título em caixa alta, normalizando para `"Anexo I - Trabalho dos Operadores de Checkout"` e `"Anexo II - Trabalho em Teleatendimento/Telemarketing"`. Exigir `ANEXO` em caixa alta evita falsos positivos em referências no corpo do texto ou no sumário (`Anexo I - ...`). Uma vez dentro de um anexo, subitens numerados internos (`1.`, `2.`, etc.) não sobrescrevem o rótulo do anexo.
2. **Seções principais de NR:** fora de anexos, reconhece cabeçalhos `^(\d+\.\d+)\s+([A-ZÁÉÍÓÚÂÊÔÃÕÇ]...)` (ex.: `"17.4 Organização do trabalho"`, `"17.8 Condições de conforto no ambiente de trabalho"`), ignorando sequências de títulos típicos de sumário.
3. **Cabeçalho solto no fim do chunk:** quando um cabeçalho de seção (ou anexo) aparece na última linha não vazia do chunk sem texto de corpo depois dele (caso observado na pág. 1 da NR-17 com `17.2` e `17.3`), ele **não** sobrescreve o `section` do chunk atual — apenas atualiza `proxima_secao` propagada ao chunk seguinte.
4. **Fallback explícito:** quando nenhuma seção é reconhecida com segurança (como em páginas de capa/sumário ou documentos sem estrutura numerada de NR, caso da `oms2020.pdf`), o campo recebe explicitamente `"unspecified"` — nunca um título inventado.

## Consequências e limitações conhecidas

- **Quebra de compatibilidade no índice:** consumidores do ChromaDB e de `knowledge_base/processed/chunks.jsonl` devem ler `document_id`, `page`, `section`, `version` etc. A impressão (`impressao`) em `knowledge_base/processed/manifest.json` inclui `METADATA_SCHEMA_VERSION`, forçando reingestão automática quando o contrato mudar.
- **Migração limpa sem duplicação:** `knowledge_base/ingest.py` remove tanto chunks pelo novo filtro (`where={"document_id": ...}`) quanto chunks legados (`where={"fonte_id": ...}`) antes de reindexar a fonte.
- **Limitação de fronteira na página 8 da NR-17:** na `nr17.pdf`, a seção `17.8` (Condições de conforto no ambiente de trabalho) termina e o `ANEXO I da NR 17` inicia na mesma página (pág. 8). Como o chunking atual é feito por tamanho/parágrafo dentro da página (ADR 0001), os chunks `c0` e `c1` da pág. 8 ficam corretamente em `"17.8 Condições de conforto no ambiente de trabalho"`, mas o chunk de fronteira `c2` contém o trecho final de `17.8.4.2` seguido do cabeçalho e itens iniciais do `ANEXO I da NR 17` e recebe o rótulo `"Anexo I - Trabalho dos Operadores de Checkout"`. Se avaliações futuras de RAG mostrarem impacto relevante desse chunk de fronteira, a evolução natural (citada na ADR 0001) será segmentar o texto por seção antes do chunking por tamanho.
- **OMS 2020 (`oms2020.pdf`):** todos os 436 chunks ficam marcados como `"unspecified"` nesta versão, de forma explícita e sem heurística frágil.
