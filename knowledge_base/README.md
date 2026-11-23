# Base de Conhecimento (RAG)

Esta pasta centraliza as fontes oficiais de ergonomia e pausas ativas utilizadas pelo pipeline de RAG.

## Estrutura

- `raw/`: Documentos originais (ex.: textos oficiais da NR-17, guias da OMS). Não incluir materiais protegidos sem autorização de uso.
- `processed/`: Chunks limpos e metadados estruturados gerados pelo script de ingestão (ignorados no git).
- `ingest.py`: Script responsável por extrair texto, gerar chunks com metadados e indexar no banco vetorial + índice BM25.
