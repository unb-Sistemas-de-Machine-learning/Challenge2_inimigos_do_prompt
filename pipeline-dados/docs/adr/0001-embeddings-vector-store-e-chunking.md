# ADR 0001 — Embeddings, vector store e chunking (v0)

- **Status:** PROVISÓRIA — decidida para destravar o grupo; revisar após testes com os documentos reais.
- **Data:** 2026-11-16
- **Responsável:** Engenheiro de Dados

## Contexto
O RAG precisa de um índice dos documentos oficiais (NR-17 e diretrizes da OMS de 2020). O agente de RAG e a avaliação dependem do formato do índice.

## Decisão (provisória)
- **Vector store:** ChromaDB persistente e local (sem servidor, simples de reproduzir).
- **Embeddings:** `sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2` (roda local, sem chave de API; os documentos têm português e inglês). Nome do modelo a confirmar.
- **Chunking:** até 1000 caracteres, sobreposição de 150, respeitando parágrafos/itens, por página.

## Motivo
Preencher depois dos testes: comparar tamanhos de chunk e modelos com o conjunto de perguntas do Cientista (hit rate / MRR).

## Alternativas a considerar
Outros modelos de embeddings (inclusive hospedados), outros vector stores (FAISS, pgvector), chunking por seção da norma.

## Consequências
Trocar o modelo de embeddings obriga a reindexar tudo e a consulta precisa usar o mesmo modelo.
