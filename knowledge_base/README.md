# Base de Conhecimento (RAG) — ErgoAI

Esta pasta centraliza as fontes oficiais de ergonomia e pausas ativas, o pipeline de ingestão/indexação (ChromaDB + exportação JSONL para BM25) e os cartões de conhecimento validados contra o texto literal das fontes.

```text
knowledge_base/sources.yaml + knowledge_base/raw/*.pdf
  -> extração de texto -> limpeza -> chunks + metadados (§6.5)
  -> embeddings -> ChromaDB (backend/data/chroma)
                + knowledge_base/processed/manifest.json
                + knowledge_base/processed/chunks.jsonl (consumo BM25)
```

## Estrutura

- `raw/`: Documentos originais em PDF (ex.: `nr17.pdf`, `oms2020.pdf`), ignorados pelo Git. Não incluir materiais protegidos sem autorização de uso.
- `processed/`: Artefatos gerados pela ingestão (`manifest.json` e `chunks.jsonl`), ignorados pelo Git.
- `sources.yaml`: Catálogo versionado das fontes oficiais (título, órgão emissor, URL oficial, licença, versão e tipo de documento).
- `ingest.py`, `clean.py`, `chunk.py`, `embed.py`, `query.py`: Pipeline de extração, limpeza, chunking, detecção de seções/anexos e indexação.
- `cards/` e `cards.py`: Cartões de conhecimento em YAML (em `rascunho` até revisão do grupo) e validador automático de citações literais.
- `tests/`: Testes automatizados do pipeline e dos cartões.

## Como rodar (com `uv`)

Todas as dependências Python ficam centralizadas em `backend/pyproject.toml`. Execute os comandos a partir da **raiz do repositório**:

```bash
# Ambiente padrão (backend + validação de cartões + testes com embedder hash)
uv sync --project backend --extra dev

# Ambiente completo com embeddings locais (sentence-transformers / PyTorch)
uv sync --project backend --extra dev --extra rag
```

### Ingestão, consulta e validação

```bash
# 1) Coloque os PDFs oficiais em knowledge_base/raw/ (nr17.pdf, oms2020.pdf)

# 2) Ingestão com embeddings reais (requer --extra rag)
uv run --project backend --extra rag python -m knowledge_base.ingest --force --strict

# Alternativa rápida sem baixar modelo (somente para testar o fluxo; não usar para avaliar RAG)
uv run --project backend python -m knowledge_base.ingest --embedder hash --force --strict

# 3) Consulta rápida no índice (usa o mesmo embedder registrado no manifest.json)
uv run --project backend --extra rag python -m knowledge_base.query "altura do monitor" -k 3

# 4) Validação automática dos cartões YAML contra os PDFs oficiais
uv run --project backend python -m knowledge_base.cards

# 5) Testes automatizados (backend + knowledge_base, usando embedder hash)
uv run --project backend --extra dev pytest backend/tests knowledge_base/tests -rs
```

## Contrato do índice (para Backend, IA e Avaliação)

- **Vector store:** ChromaDB persistente em `backend/data/chroma` (alinhado ao `CHROMA_PERSIST_DIR=./data/chroma` de `backend/.env.example`), coleção `ergonomia`.
- **Exportação para BM25:** `knowledge_base/processed/chunks.jsonl` — um objeto JSON por linha (`{"id", "text", "metadata"}`) sincronizado com a coleção do ChromaDB.
- **Metadados de cada chunk (alinhados ao `SPEC.md` §6.5 + rastreabilidade):** `document_id`, `title`, `source`, `section`, `page`, `url`, `document_type`, `version`, `license`, `chunk`. Ver `docs/adr/0002-contrato-metadados-indice-e-secoes.md`.
- **Manifesto:** `knowledge_base/processed/manifest.json` registra SHA-256 de cada fonte, versão, licença, nº de páginas/chunks e parâmetros de indexação (embedder, chunking e versão do schema de metadados).
- **Consistência de embedder:** a consulta deve usar o mesmo embedder registrado no `manifest.json` (`knowledge_base.query` faz isso automaticamente). Trocar o embedder exige reindexar com `--force`.

## Limitações conhecidas

- Chunking por página: um item que atravessa duas páginas é cortado (o número da página permanece no metadado para citação).
- Remoção de cabeçalho/rodapé é heurística (linha repetida em pelo menos 50% das páginas).
- PDFs escaneados (somente imagem, sem camada de texto) não são lidos sem OCR.
- Na página 8 da NR-17, o chunk de fronteira entre a seção `17.8` e o início do `Anexo I` fica rotulado como `Anexo I` (detalhado na ADR 0002).
