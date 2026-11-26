# Base de Conhecimento (RAG) — ErgoAI

Esta pasta centraliza as fontes oficiais de ergonomia e pausas ativas, o corpus processado versionado para bootstrap reproduzível, o pipeline de ingestão/indexação (ChromaDB + JSONL para BM25) e os cartões de conhecimento validados contra o texto literal das fontes.

```text
Fluxo 1 (bootstrap rápido, sem baixar PDFs):
  knowledge_base/corpus/chunks.jsonl
    -> embeddings -> ChromaDB (backend/data/chroma) + knowledge_base/processed/manifest.json

Fluxo 2 (reingestão completa a partir dos PDFs originais):
  knowledge_base/sources.yaml + knowledge_base/raw/*.pdf (checagem SHA-256)
    -> extração -> limpeza -> chunks + metadados (§6.5)
    -> embeddings -> ChromaDB (backend/data/chroma)
                  + knowledge_base/processed/manifest.json
                  + knowledge_base/processed/chunks.jsonl
```

## Estrutura

- `corpus/`: Corpus processado versionado (`chunks.jsonl`, `manifest.json` com caminhos relativos e `ATTRIBUTION.md` com atribuição e licença `CC BY-NC-SA 3.0 IGO` da OMS + referência oficial da NR-17).
- `raw/`: Documentos originais em PDF (`nr17.pdf`, `oms2020.pdf`), ignorados pelo Git. Necessários apenas para reingestão completa ou revalidação de cartões contra a fonte primária.
- `processed/`: Artefatos locais gerados pelo bootstrap/ingestão (`manifest.json` e `chunks.jsonl`), ignorados pelo Git.
- `sources.yaml`: Catálogo versionado das fontes oficiais, incluindo `sha256` esperado dos PDFs, licença, versão e tipo de documento.
- `bootstrap.py`: Reconstroi o índice local do ChromaDB diretamente a partir de `knowledge_base/corpus/chunks.jsonl`.
- `ingest.py`, `clean.py`, `chunk.py`, `embed.py`, `query.py`: Pipeline de extração, limpeza, chunking, detecção de seções/anexos, reconstrução (`--from-chunks`) e consulta.
- `cards/` e `cards.py`: Cartões de conhecimento em YAML (em `rascunho` até revisão do grupo) e validador automático de citações literais.
- `tests/`: Testes automatizados do pipeline, do bootstrap e dos cartões.

## Pré-requisitos

- **Python >= 3.11** e **`uv`** (todas as dependências Python ficam centralizadas em `backend/pyproject.toml`).
- **Node.js v24+** (usado pelos scripts de avaliação em `evals/` para importar diretamente `frontend/src/posture-engine/postureEngine.ts`).

```bash
# Ambiente padrão (backend + bootstrap/testes com embedder hash + validação de cartões)
uv sync --project backend --extra dev

# Ambiente completo com embeddings locais reais (sentence-transformers / PyTorch)
uv sync --project backend --extra dev --extra rag
```

## Como rodar (a partir da raiz do repositório)

### 1. Bootstrap reproduzível (sem precisar baixar os PDFs)

```bash
# Índice real local com sentence-transformers (requer --extra rag)
uv run --project backend --extra rag python -m knowledge_base.bootstrap

# Índice rápido para testes/CI sem baixar modelo (embedder hash — NÃO usar para avaliar qualidade RAG)
uv run --project backend python -m knowledge_base.bootstrap --embedder hash

# Alternativa equivalente via ingest.py:
uv run --project backend --extra rag python -m knowledge_base.ingest --from-chunks knowledge_base/corpus/chunks.jsonl
```

### 2. Consulta, reingestão completa a partir dos PDFs e testes

```bash
# Consulta rápida no índice (usa o mesmo embedder registrado em knowledge_base/processed/manifest.json)
uv run --project backend --extra rag python -m knowledge_base.query "altura do monitor" -k 3

# Reingestão completa a partir de knowledge_base/raw/*.pdf (valida SHA-256 quando --strict está ativo)
uv run --project backend --extra rag python -m knowledge_base.ingest --force --strict

# Validação automática dos cartões YAML contra os PDFs oficiais em knowledge_base/raw/
uv run --project backend python -m knowledge_base.cards

# Suíte de testes automatizados (backend + knowledge_base + evals; usa embedder hash)
uv run --project backend --extra dev pytest backend/tests knowledge_base/tests evals/tests -rs
```

## Contrato do índice (para Backend, IA e Avaliação)

- **Vector store:** ChromaDB persistente em `backend/data/chroma` (alinhado ao `CHROMA_PERSIST_DIR=./data/chroma` de `backend/.env.example`), coleção `ergonomia`.
- **Corpus JSONL para BM25:** `knowledge_base/corpus/chunks.jsonl` (versionado) e `knowledge_base/processed/chunks.jsonl` (cópia de trabalho gerada no ingest/bootstrap) — um objeto JSON por linha (`{"id", "text", "metadata"}`).
- **Metadados de cada chunk (alinhados ao `SPEC.md` §6.5 + rastreabilidade):** `document_id`, `title`, `source`, `section`, `page`, `url`, `document_type`, `version`, `license`, `chunk`. Ver `docs/adr/0002-contrato-metadados-indice-e-secoes.md`.
- **Manifesto:** `knowledge_base/processed/manifest.json` registra SHA-256 de cada fonte, versão, licença, nº de páginas/chunks e parâmetros de indexação com caminhos relativos.
- **Consistência de embedder:** a consulta deve usar o mesmo embedder registrado no `manifest.json` (`knowledge_base.query` faz isso automaticamente). Trocar o embedder exige rodar novamente `knowledge_base.bootstrap` ou `knowledge_base.ingest --force`.

## Limitações conhecidas

- Chunking por página: um item que atravessa duas páginas é cortado (o número da página permanece no metadado para citação).
- Remoção de cabeçalho/rodapé é heurística (linha repetida em pelo menos 50% das páginas).
- PDFs escaneados (somente imagem, sem camada de texto) não são lidos sem OCR.
- Na página 8 da NR-17, o chunk de fronteira entre a seção `17.8` e o início do `Anexo I` fica rotulado como `Anexo I` (detalhado na ADR 0002).
