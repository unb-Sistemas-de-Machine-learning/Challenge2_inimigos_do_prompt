# Cartões de conhecimento, esquema de dados e validação

## Fluxo
- **Ao vivo (sem LLM):** features normalizadas -> comparação com a calibração -> filtro temporal/histerese -> alerta ligado a um **cartão de conhecimento**.
- **Sob demanda / pós-sessão:** RAG completo + agente crítico de segurança (perguntas livres, análise de foto, resumo da sessão).

## Cartão de conhecimento
Um arquivo YAML por cartão em `cards/` (modelo em `cards/_template.yaml`): tipo de desvio, texto curto para o alerta, fonte (`fonte_id` de `sources.yaml`), trecho literal, versões e status (`rascunho` ou `aprovado`).
- Só cartões **aprovados pelo grupo** devem ser usados no app.
- Trechos curtos (até 400 caracteres), com atribuição; respeitar a licença de cada fonte (a OMS usa CC BY-NC-SA 3.0 IGO).
- A lista de tipos de desvio está em `cards/_tipos_desvio.yaml` (proposta; o grupo fecha).

## Validação automática
```bash
python -m pipeline.cards
```
Confere, para cada cartão: campos obrigatórios, tipo de desvio válido, fonte existente, versão da fonte igual à de `sources.yaml`, tamanho do texto e do trecho, ids únicos e, principalmente, que o **trecho citado existe no documento** (mesma extração e limpeza do pipeline de ingestão; comparação ignora caixa, espaços e quebras de linha).
- Cartão `aprovado` com problema de conteúdo: **erro** (exit code 1).
- Cartão `rascunho`: o mesmo problema vira **aviso**.
- O trecho precisa estar inteiro em uma única página.
- Precisa dos PDFs em `data/raw/`. Sem o arquivo, cartões aprovados falham.
Sugestão para o MLOps: rodar `pytest` e `python -m pipeline.cards` no CI (nos PRs e quando `sources.yaml` ou `cards/` mudarem), para a falha avisar quando uma fonte mudar de versão e invalidar um cartão.

## Esquema de dados da sessão
Tipos TypeScript em `schema/sessao.ts` (sessão, evento, feedback, parâmetros versionados e nomes dos stores do IndexedDB) e em `schema/coleta.ts` (gravações de landmarks e rótulos do conjunto de avaliação).
- O feedback do usuário (útil / falso alerta) **não** é rótulo verdadeiro.
- Cada ajuste de tolerância cria uma nova versão de parâmetros.
- O evento (`SessionEvent`) guarda `cardId`, `cardVersion` e `knowledgeBaseVersion` para rastrear de onde veio cada orientação (alinhado ao `SPEC.md` §11.2 em `camelCase`; os contratos JSON da API do §9 permanecem em `snake_case` no mesmo arquivo).
- Nada de imagens; o histórico local precisa de um botão para limpar tudo (RNF09).

## Protocolo de coleta
Ver `docs/protocolo-coleta-landmarks.md` (proposta a validar pelo grupo).
