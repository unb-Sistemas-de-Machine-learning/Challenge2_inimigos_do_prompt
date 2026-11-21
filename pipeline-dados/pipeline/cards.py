"""Validação dos cartões de conhecimento contra o texto das fontes oficiais.

Um cartão liga um tipo de desvio postural a uma recomendação curta, com fonte e trecho literal.
A validação confere que o trecho citado existe no documento (na versão registrada em sources.yaml).

Uso:  python -m pipeline.cards
      python -m pipeline.cards --cards-dir cards --sources sources.yaml --raw-dir data/raw

Regras:
- Cartão "aprovado": qualquer problema de conteúdo (trecho ausente, versão diferente, arquivo ausente) é ERRO.
- Cartão "rascunho": os mesmos problemas viram AVISO. Problemas estruturais (campos faltando) são sempre ERRO.
"""
import argparse
import re
import sys
import unicodedata
from pathlib import Path

import yaml

from .clean import clean_text, remove_repeated_lines
from .ingest import extrair_paginas

CAMPOS_OBRIGATORIOS = ["id", "tipo_desvio", "texto_curto", "fonte_id", "trecho",
                       "versao_fonte", "versao_cartao", "status"]
STATUS_VALIDOS = {"rascunho", "aprovado"}
MAX_TRECHO = 400   # trechos curtos: citação com atribuição, sem reproduzir o documento
MAX_TEXTO_CURTO = 280

_TRADUCAO = str.maketrans({"\u201c": '"', "\u201d": '"', "\u2018": "'", "\u2019": "'",
                           "\u2013": "-", "\u2014": "-"})


def normalizar(texto):
    """Normaliza para comparação: Unicode (inclui ligaturas), aspas/travessões, espaços e caixa."""
    t = unicodedata.normalize("NFKC", str(texto)).replace("\u00ad", "").translate(_TRADUCAO)
    return re.sub(r"\s+", " ", t).strip().lower()


def carregar_paginas_normalizadas(fonte, raw_dir):
    """Reaproveita a mesma extração e limpeza do pipeline de ingestão. Retorna None se o arquivo não existir."""
    caminho = Path(raw_dir) / fonte["arquivo_local"]
    if not caminho.exists():
        return None
    paginas = remove_repeated_lines(extrair_paginas(caminho))
    return [normalizar(clean_text(p)) for p in paginas]


def validar_cartao(card, fontes_por_id, paginas_por_fonte, tipos_validos):
    """Retorna (erros, avisos) de um cartão. paginas_por_fonte: {fonte_id: [texto_normalizado_por_pagina] | None}."""
    erros, avisos = [], []

    faltando = [c for c in CAMPOS_OBRIGATORIOS if card.get(c) in (None, "")]
    if faltando:
        return [f"campos obrigatórios ausentes: {', '.join(faltando)}"], avisos
    if card["status"] not in STATUS_VALIDOS:
        erros.append(f"status inválido '{card['status']}' (use: {', '.join(sorted(STATUS_VALIDOS))})")
    if tipos_validos and card["tipo_desvio"] not in tipos_validos:
        erros.append(f"tipo_desvio '{card['tipo_desvio']}' não está em cards/_tipos_desvio.yaml")
    if len(str(card["texto_curto"])) > MAX_TEXTO_CURTO:
        erros.append(f"texto_curto com mais de {MAX_TEXTO_CURTO} caracteres")
    if len(str(card["trecho"])) > MAX_TRECHO:
        erros.append(f"trecho com mais de {MAX_TRECHO} caracteres (use uma citação curta)")

    # Problemas de conteúdo: erro se aprovado, aviso se rascunho.
    destino = erros if card["status"] == "aprovado" else avisos
    fonte = fontes_por_id.get(card["fonte_id"])
    if fonte is None:
        erros.append(f"fonte_id '{card['fonte_id']}' não existe em sources.yaml")
        return erros, avisos
    if str(card["versao_fonte"]) != str(fonte.get("versao", "")):
        destino.append("versao_fonte difere do campo 'versao' em sources.yaml")
    paginas = paginas_por_fonte.get(card["fonte_id"])
    if paginas is None:
        destino.append(f"arquivo da fonte '{card['fonte_id']}' ausente em data/raw (não foi possível conferir o trecho)")
        return erros, avisos

    alvo = normalizar(card["trecho"])
    pagina = card.get("pagina")
    if pagina not in (None, ""):
        if not isinstance(pagina, int) or not 1 <= pagina <= len(paginas):
            destino.append(f"pagina {pagina} fora do intervalo 1..{len(paginas)}")
        elif alvo not in paginas[pagina - 1]:
            destino.append(f"trecho não encontrado na página {pagina}")
    elif not any(alvo in p for p in paginas):
        destino.append("trecho não encontrado no documento (precisa estar inteiro em uma única página)")
    return erros, avisos


def carregar_cartoes(cards_dir):
    cartoes = []
    for arq in sorted(Path(cards_dir).glob("*.yaml")):
        if arq.name.startswith("_"):
            continue
        dados = yaml.safe_load(arq.read_text(encoding="utf-8"))
        cartoes.append((arq.name, dados if isinstance(dados, dict) else {}))
    return cartoes


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--cards-dir", default="cards")
    ap.add_argument("--sources", default="sources.yaml")
    ap.add_argument("--raw-dir", default="data/raw")
    a = ap.parse_args(argv)

    fontes = yaml.safe_load(Path(a.sources).read_text(encoding="utf-8"))["fontes"]
    fontes_por_id = {f["id"]: f for f in fontes}
    tipos_arq = Path(a.cards_dir) / "_tipos_desvio.yaml"
    tipos = set(yaml.safe_load(tipos_arq.read_text(encoding="utf-8")).get("tipos", [])) if tipos_arq.exists() else set()
    paginas = {fid: carregar_paginas_normalizadas(f, a.raw_dir) for fid, f in fontes_por_id.items()}

    total_erros, ids_vistos = 0, {}
    cartoes = carregar_cartoes(a.cards_dir)
    for nome, card in cartoes:
        erros, avisos = validar_cartao(card, fontes_por_id, paginas, tipos)
        cid = card.get("id")
        if cid:
            if cid in ids_vistos:
                erros.append(f"id duplicado (também em {ids_vistos[cid]})")
            ids_vistos.setdefault(cid, nome)
        status = "ERRO" if erros else ("AVISO" if avisos else "OK")
        print(f"[{status}] {nome}")
        for m in erros:
            print(f"    erro: {m}")
        for m in avisos:
            print(f"    aviso: {m}")
        total_erros += len(erros)
    print(f"{len(cartoes)} cartão(ões) verificado(s), {total_erros} erro(s).")
    return 1 if total_erros else 0


if __name__ == "__main__":
    sys.exit(main())
