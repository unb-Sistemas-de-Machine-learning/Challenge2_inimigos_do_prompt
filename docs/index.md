# ErgoAI — Documentação do Projeto

**ErgoAI** é um sistema web de monitoramento ergonômico e recomendações educativas fundamentadas em fontes oficiais (NR-17, OMS e literatura científica), desenvolvido para o **Challenge 2 — Inimigos do Prompt**.

## Visão Geral da Arquitetura

1. **Frontend (`frontend/`)**: Executa `@mediapipe/tasks-vision` (`PoseLandmarker`) 100% localmente no navegador para extrair coordenadas posturais (ombro, pescoço, inclinação da cabeça e proximidade) sem enviar frames da webcam ao servidor.
2. **Backend (`backend/`)**: API em FastAPI responsável pelo pipeline de **RAG** (busca híbrida vetorial + BM25), interpretação de eventos posturais por LLM, validação de segurança (*Safety Validator*) e análise complementar de foto do posto de trabalho.
3. **Base de Conhecimento (`knowledge_base/`)**: Fontes oficiais e scripts de ingestão/indexação.
4. **Avaliação (`evals/`)**: Datasets rotulados e métricas de recuperação (Hit Rate, MRR), geração e visão computacional.

## Documentos Principais

- [Especificação de Requisitos](especificacao-requisitos.md)
- [Roteiro de Implementação do Protótipo](roteiro-prototipo.md)
