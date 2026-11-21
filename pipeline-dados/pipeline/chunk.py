"""Divisão do texto em chunks respeitando parágrafos/itens."""


def _quebrar_unidade_longa(u, max_chars):
    partes = []
    while len(u) > max_chars:
        corte = u.rfind(". ", 0, max_chars)
        corte = corte + 1 if corte > max_chars // 2 else max_chars
        partes.append(u[:corte].strip())
        u = u[corte:].strip()
    if u:
        partes.append(u)
    return partes


def chunk_text(text, max_chars=1000, overlap_chars=150):
    unidades = []
    for u in (x.strip() for x in text.split("\n")):
        if u:
            unidades.extend(_quebrar_unidade_longa(u, max_chars))

    chunks, atual, tam = [], [], 0
    for u in unidades:
        if atual and tam + len(u) + 1 > max_chars:
            chunks.append("\n".join(atual))
            ov, t = [], 0  # sobreposição: últimas unidades até overlap_chars
            for x in reversed(atual):
                if t + len(x) > overlap_chars:
                    break
                ov.insert(0, x)
                t += len(x) + 1
            atual, tam = ov, t
        atual.append(u)
        tam += len(u) + 1
    if atual:
        chunks.append("\n".join(atual))
    return chunks
