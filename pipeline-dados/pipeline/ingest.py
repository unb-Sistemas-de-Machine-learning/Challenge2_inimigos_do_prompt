"""Pipeline v0: fontes -> texto -> limpeza -> chunks com metadados -> embeddings -> índice (ChromaDB).

Uso:  python -m pipeline.ingest            (ingere só o que mudou)
      python -m pipeline.ingest --force    (reindexa tudo)
"""
import argparse
import datetime
import hashlib
import json
import re
import sys
from pathlib import Path

import yaml

from .chunk import chunk_text
from .clean import clean_text, remove_repeated_lines
from .embed import DEFAULT_MODEL, get_embedder

COLECAO = "ergonomia"
METADATA_SCHEMA_VERSION = "spec-6.5-v1"
UNSPECIFIED_SECTION = "unspecified"

# Cabeçalhos reais de anexo em caixa alta (evita casar "Anexo I" no sumário ou em referências no texto).
# Subtítulo em caixa alta exige palavras inteiras em maiúsculas (não captura o "S" de "Sumário").
_PALAVRA_MAIUSCULA = r"[A-ZÁÉÍÓÚÂÊÔÃÕÇ]{2,}(?:/[A-ZÁÉÍÓÚÂÊÔÃÕÇ]{2,})*"
_RE_ANEXO = re.compile(
    r"\bANEXO\s+([IVX]+)(?:\s+da\s+NR[\s-]*\d+)?"
    rf"(?:\s*[-–:]\s*([^\n]+)|\s+({_PALAVRA_MAIUSCULA}(?:[\s\-]+(?:{_PALAVRA_MAIUSCULA}|E|A|O|À))*))?"
)
# Seções principais de NR (ex.: "17.4 Organização do trabalho"), sem subitens ("17.4.1").
_RE_SECAO_NR = re.compile(r"^(\d+\.\d+)\s+([A-ZÁÉÍÓÚÂÊÔÃÕÇ][^\n]{2,90})$")


def _normalizar_titulo_anexo(subtitulo):
    if not subtitulo:
        return ""
    # Corta se clean_text tiver juntado "Sumário" ou item numerado ao final da linha.
    sub = re.split(r"\bSum[áa]rio\b|\b\d+\.\s", subtitulo, maxsplit=1)[0].strip(" -–:.")
    if not sub:
        return ""
    if sub.isupper():
        # Mantém preposições comuns em minúsculas para leitura limpa.
        minusculas = {"da", "das", "de", "do", "dos", "em", "e", "no", "nos", "na", "nas"}
        palavras = sub.lower().split()
        sub = " ".join(
            p if (idx > 0 and p in minusculas) else "/".join(parte.capitalize() for parte in p.split("/"))
            for idx, p in enumerate(palavras)
        )
    return sub


def atualizar_secao(texto_chunk, secao_atual):
    """Resolve (secao_chunk, proxima_secao) a partir de cabeçalhos reconhecidos no chunk.

    Regras explícitas e determinísticas:
    1. Cabeçalhos de ANEXO em caixa alta têm prioridade e fixam o contexto de anexo
       até outro ANEXO aparecer (itens internos "1.", "2." não sobrescrevem o anexo).
    2. Fora de anexos, cabeçalhos de seção principal de NR ("17.x Título") atualizam
       a seção, ignorando blocos de sumário (onde vários "17.x" aparecem em sequência).
    3. Se um cabeçalho de seção (ou anexo) aparecer no final do chunk sem texto de
       corpo depois dele, ele NÃO sobrescreve o metadado `section` do chunk atual —
       apenas atualiza `proxima_secao` propagada para o chunk seguinte.
    4. Quando nenhuma seção é reconhecida até o momento, retorna "unspecified".
    """
    atual = secao_atual or UNSPECIFIED_SECTION

    m_anexo = None
    for m in _RE_ANEXO.finditer(texto_chunk):
        m_anexo = m
    if m_anexo:
        romano = m_anexo.group(1)
        sub = _normalizar_titulo_anexo(m_anexo.group(2) or m_anexo.group(3))
        novo_anexo = f"Anexo {romano} - {sub}" if sub else f"Anexo {romano}"
        tem_corpo_depois = bool(texto_chunk[m_anexo.end():].strip())
        if tem_corpo_depois:
            return novo_anexo, novo_anexo
        return atual, novo_anexo

    if atual.startswith("Anexo "):
        return atual, atual

    linhas = [l.strip() for l in texto_chunk.splitlines() if l.strip()]
    secao_chunk = atual
    proxima_secao = atual
    for idx, linha in enumerate(linhas):
        m_sec = _RE_SECAO_NR.match(linha)
        if not m_sec:
            continue
        # Ignora linhas de sumário onde títulos "17.x ..." aparecem listados em sequência
        # (inclusive quando o último item do sumário cai no limite final de um chunk).
        anterior = linhas[idx - 1] if idx > 0 else ""
        proxima = linhas[idx + 1] if idx + 1 < len(linhas) else ""
        if (
            _RE_SECAO_NR.match(proxima)
            or proxima.startswith("Anexo ")
            or (not proxima and _RE_SECAO_NR.match(anterior))
        ):
            continue
        titulo = f"{m_sec.group(1)} {m_sec.group(2).rstrip('.')}"
        proxima_secao = titulo
        if proxima:  # só rotula o chunk atual se houver texto de corpo após o cabeçalho
            secao_chunk = titulo

    return secao_chunk, proxima_secao


def sha256_arquivo(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for bloco in iter(lambda: f.read(1 << 20), b""):
            h.update(bloco)
    return h.hexdigest()


def extrair_paginas(path):
    path = Path(path)
    if path.suffix.lower() == ".pdf":
        from pypdf import PdfReader
        return [(p.extract_text() or "") for p in PdfReader(str(path)).pages]
    return [path.read_text(encoding="utf-8")]  # .txt/.md contam como uma página


def montar_chunks(fonte, caminho, max_chars, overlap_chars):
    paginas = remove_repeated_lines(extrair_paginas(caminho))
    registros = []
    secao_atual = UNSPECIFIED_SECTION
    for num, texto in enumerate(paginas, start=1):
        for i, ch in enumerate(chunk_text(clean_text(texto), max_chars, overlap_chars)):
            secao_chunk, secao_atual = atualizar_secao(ch, secao_atual)
            cid = f"{fonte['id']}-p{num}-c{i}-{hashlib.sha1(ch.encode()).hexdigest()[:8]}"
            registros.append({
                "id": cid,
                "texto": ch,
                "meta": {
                    "document_id": fonte["id"],
                    "title": str(fonte.get("titulo", "")),
                    "source": str(fonte.get("source", "")),
                    "section": secao_chunk,
                    "page": num,
                    "url": str(fonte.get("url_oficial", "")),
                    "document_type": str(fonte.get("document_type", "")),
                    "version": str(fonte.get("versao", "")),
                    "license": str(fonte.get("licenca", "")),
                    "chunk": i,
                },
            })
    return registros, len(paginas)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--sources", default="sources.yaml")
    ap.add_argument("--raw-dir", default="data/raw")
    ap.add_argument("--index-dir", default="data/index")
    ap.add_argument("--manifest", default="data/manifest.json")
    ap.add_argument("--embedder", default=DEFAULT_MODEL, help="nome do modelo ou 'hash' (só testes)")
    ap.add_argument("--max-chars", type=int, default=1000)
    ap.add_argument("--overlap-chars", type=int, default=150)
    ap.add_argument("--force", action="store_true")
    ap.add_argument("--strict", action="store_true", help="falha (exit 1) se algum arquivo de fonte estiver ausente")
    a = ap.parse_args(argv)

    import chromadb

    fontes = yaml.safe_load(Path(a.sources).read_text(encoding="utf-8"))["fontes"]
    mpath = Path(a.manifest)
    manifest = json.loads(mpath.read_text(encoding="utf-8")) if mpath.exists() else {"fontes": {}}

    cliente = chromadb.PersistentClient(path=a.index_dir)
    col = cliente.get_or_create_collection(COLECAO)
    embedder, ausentes = None, 0

    for f in fontes:
        caminho = Path(a.raw_dir) / f["arquivo_local"]
        if not caminho.exists():
            print(f"[AVISO] {f['id']}: arquivo ausente em {caminho}")
            ausentes += 1
            continue
        sha = sha256_arquivo(caminho)
        impressao = f"{sha}|{a.embedder}|{a.max_chars}|{a.overlap_chars}|{METADATA_SCHEMA_VERSION}"
        if not a.force and manifest["fontes"].get(f["id"], {}).get("impressao") == impressao:
            print(f"[OK] {f['id']}: sem mudanças, pulando")
            continue

        registros, n_pag = montar_chunks(f, caminho, a.max_chars, a.overlap_chars)
        if not registros:
            print(f"[AVISO] {f['id']}: nenhum texto extraído (PDF escaneado?)")
            continue
        embedder = embedder or get_embedder(a.embedder)
        # Remove versões anteriores desta fonte (contrato atual e legado v0 com fonte_id)
        col.delete(where={"document_id": f["id"]})
        col.delete(where={"fonte_id": f["id"]})
        for ini in range(0, len(registros), 500):
            lote = registros[ini:ini + 500]
            col.add(
                ids=[r["id"] for r in lote],
                documents=[r["texto"] for r in lote],
                metadatas=[r["meta"] for r in lote],
                embeddings=embedder.encode([r["texto"] for r in lote]),
            )
        manifest["fontes"][f["id"]] = {
            "sha256": sha, "versao": str(f.get("versao", "")), "licenca": str(f.get("licenca", "")),
            "data_acesso": str(f.get("data_acesso", "")), "paginas": n_pag, "chunks": len(registros),
            "impressao": impressao,
        }
        print(f"[INDEXADO] {f['id']}: {n_pag} páginas, {len(registros)} chunks")

    manifest["parametros"] = {
        "embedder": a.embedder,
        "max_chars": a.max_chars,
        "overlap_chars": a.overlap_chars,
        "colecao": COLECAO,
        "metadata_schema": METADATA_SCHEMA_VERSION,
    }
    manifest["gerado_em"] = datetime.datetime.now(datetime.timezone.utc).isoformat()
    mpath.parent.mkdir(parents=True, exist_ok=True)
    mpath.write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")
    return 1 if (a.strict and ausentes) else 0


if __name__ == "__main__":
    sys.exit(main())
