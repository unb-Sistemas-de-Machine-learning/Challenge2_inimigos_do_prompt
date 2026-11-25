"""Limpeza do texto extraído de PDFs."""
import re
from collections import Counter

# Início de item numerado/lista (ex.: "17.1.1 ...", "a) ...", "- ..."): não juntar com a linha anterior.
ITEM = re.compile(r"^(\d+(\.\d+)+\.?|\d+\.|[a-z]\)|[-•–])\s")
SO_NUM_PAGINA = re.compile(r"\s*(p[áa]gina|page)?\s*\d+\s*(/\s*\d+)?\s*", re.I)


def remove_repeated_lines(pages, min_ratio=0.5, min_pages=3):
    """Remove linhas (cabeçalhos/rodapés) que se repetem na maioria das páginas."""
    if len(pages) < min_pages:
        return pages
    counts = Counter()
    for p in pages:
        for line in {l.strip() for l in p.splitlines() if l.strip()}:
            counts[line] += 1
    limite = len(pages) * min_ratio
    repetidas = {l for l, c in counts.items() if c >= limite}
    return ["\n".join(l for l in p.splitlines() if l.strip() not in repetidas) for p in pages]


def _juntar_linhas(text):
    """Junta quebras de linha simples dentro de um parágrafo, preservando itens numerados."""
    paragrafos = []
    for para in text.split("\n\n"):
        linhas = para.split("\n")
        atual, res = linhas[0], []
        for l in linhas[1:]:
            if ITEM.match(l.strip()):
                res.append(atual)
                atual = l.strip()
            else:
                atual += " " + l.strip()
        res.append(atual)
        paragrafos.append("\n".join(res))
    return "\n\n".join(paragrafos)


def clean_text(text):
    text = text.replace("\r", "")
    text = re.sub(r"-\n(?=[a-zà-ú])", "", text)  # hifenização no fim da linha
    text = "\n".join(l for l in text.splitlines() if not SO_NUM_PAGINA.fullmatch(l))
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return _juntar_linhas(text).strip()
