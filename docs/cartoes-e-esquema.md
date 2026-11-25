# Cartões de conhecimento, esquema de dados e validação

## Fluxo

- **Ao vivo (sem LLM):** features normalizadas -> comparação com a calibração -> filtro temporal/histerese -> alerta ligado a um **cartão de conhecimento**.
- **Sob demanda / pós-sessão:** RAG completo + agente crítico de segurança (perguntas livres, análise de foto, resumo da sessão).

## Cartão de conhecimento

Um arquivo YAML por cartão em `knowledge_base/cards/` (modelo em `knowledge_base/cards/_template.yaml`): tipo de desvio, texto curto para o alerta, fonte (`fonte_id` de `knowledge_base/sources.yaml`), trecho literal, versões e status (`rascunho` ou `aprovado`).

- Só cartões **aprovados pelo grupo** devem substituir os textos provisórios em `frontend/src/data/knowledgeCards.ts`.
- Trechos curtos (até 400 caracteres), com atribuição; respeitar a licença de cada fonte (a OMS usa CC BY-NC-SA 3.0 IGO).
- A lista oficial de códigos de desvio está em `knowledge_base/cards/_tipos_desvio.yaml`.

## Validação automática

A partir da raiz do repositório:

```bash
uv run --project backend python -m knowledge_base.cards
```

Confere, para cada cartão: campos obrigatórios, tipo de desvio válido, fonte existente, versão da fonte igual à de `knowledge_base/sources.yaml`, tamanho do texto e do trecho, ids únicos e, principalmente, que o **trecho citado existe no documento** (mesma extração e limpeza do pipeline de ingestão; comparação ignora caixa, espaços e quebras de linha).

- Cartão `aprovado` com problema de conteúdo: **erro** (exit code 1).
- Cartão `rascunho`: o mesmo problema vira **aviso**.
- O trecho precisa estar inteiro em uma única página.
- Requer os PDFs em `knowledge_base/raw/`. Sem o arquivo, cartões aprovados falham.

Sugestão para o MLOps: rodar `pytest` e `python -m knowledge_base.cards` no CI (nos PRs e quando `knowledge_base/sources.yaml` ou `knowledge_base/cards/` mudarem), para a falha avisar quando uma fonte mudar de versão e invalidar um cartão.

## Esquema de dados da sessão

Tipos TypeScript consolidados em `frontend/src/types/contracts.ts` (contratos JSON da API do `SPEC.md` §9 em `snake_case`, alinhados a `backend/app/schemas/contracts.py`, mais armazenamento local do `SPEC.md` §11.2 em `camelCase`: sessão, evento, feedback, parâmetros versionados e nomes dos stores do IndexedDB) e em `frontend/src/types/coleta.ts` (gravações de landmarks e rótulos do conjunto de avaliação).

- O feedback do usuário (`helpful` / `false_alert`) **não** é rótulo verdadeiro.
- Cada ajuste de tolerância cria uma nova versão de parâmetros (`UserParameters`).
- O evento (`SessionEvent`) guarda `cardId`, `cardVersion` e `knowledgeBaseVersion` para rastrear de onde veio cada orientação.
- Nada de imagens; o histórico local precisa de um botão para limpar tudo (RNF09).

## Protocolo de coleta

Ver [Protocolo de Coleta de Landmarks](./protocolo-coleta-landmarks.md).
