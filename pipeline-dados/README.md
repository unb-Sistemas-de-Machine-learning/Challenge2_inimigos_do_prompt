# Pipeline de dados (v0) — Desafio 2: Ergonomia com IA

Papel: Engenheiro de Dados. Este pipeline transforma os documentos oficiais em um índice de busca (base do RAG).

```
sources.yaml + data/raw/*.pdf  ->  extração de texto  ->  limpeza  ->  chunks + metadados
                                -> embeddings -> índice ChromaDB (data/index) + data/manifest.json
```

## Como rodar

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# 1) Baixe os PDFs oficiais e salve em data/raw/ com os nomes de sources.yaml (nr17.pdf, oms2020.pdf)
# 2) Preencha em sources.yaml: url_oficial da NR-17, data_acesso, versão e licença (itens marcados "CONFIRMAR")
python -m pipeline.ingest                 # indexa só o que mudou (usa hash do arquivo)
python -m pipeline.ingest --force         # reindexa tudo
python -m pipeline.query "altura do monitor" -k 3   # confere o índice
pytest                                    # testes (usam o embedder "hash", sem baixar modelo)
```

Teste rápido sem baixar modelo: `python -m pipeline.ingest --embedder hash` (o índice resultante NÃO serve para avaliar a recuperação).

## Contrato do índice (para Engenheiro de IA, Cientista e MLOps)

- Vector store: ChromaDB persistente em `data/index`, coleção `ergonomia`.
- Metadados de cada chunk: `fonte_id`, `titulo`, `versao`, `licenca`, `pagina`, `chunk`.
- `data/manifest.json` registra: sha256 de cada fonte, versão, licença, nº de páginas e chunks, e os parâmetros (embedder, tamanho do chunk, sobreposição).
- **A consulta deve usar o mesmo embedder do manifest** (`python -m pipeline.query` faz isso). Trocar o embedder exige reindexar (`--force`).

## Automação já embutida
- Idempotente: se o arquivo e os parâmetros não mudaram, a fonte é pulada.
- Ao reindexar uma fonte, os chunks antigos dela são removidos (não duplica).
- `--strict` retorna erro se algum arquivo de fonte estiver ausente (útil para CI).
- Próximo passo (semana 5, com o MLOps): gatilho automático ao mudar um documento e checagens de qualidade dos dados.

## O que foi e o que NÃO foi testado
Testado: limpeza, chunking, ingestão ponta a ponta e idempotência (com embedder `hash`), e extração de um PDF simples gerado para teste.
**Não testado:** download do modelo de embeddings real (o ambiente de desenvolvimento não tinha acesso) e os PDFs oficiais (NR-17, OMS). O nome do modelo em `pipeline/embed.py` é provisório: confirme na documentação.
Também não conferi a API do ChromaDB e do sentence-transformers na versão que vocês vão instalar: se algo falhar, verifique a documentação atual.

## Limitações conhecidas (v0)
- Chunking por página: um item que atravessa duas páginas é cortado (a página fica no metadado para citação).
- Remoção de cabeçalho/rodapé é heurística (linha repetida em ≥50% das páginas): confira amostras, porque texto legítimo repetido também seria removido.
- PDF escaneado (sem texto) não é lido: precisaria de OCR.
- Sempre confira manualmente uma amostra dos chunks de cada documento antes de usar na avaliação.

## Próximos passos
1. Baixar NR-17 e OMS, preencher `sources.yaml`, rodar o pipeline e inspecionar os chunks.
2. Definir com o grupo o embedder e o chunking em ADR (`docs/adr/0001-...`), com testes comparativos.
3. Pipeline das fotos (semana 4): padronização, remoção de EXIF, conjunto de teste fixo.
