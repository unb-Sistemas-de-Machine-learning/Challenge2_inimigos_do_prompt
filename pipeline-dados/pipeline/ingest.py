"""Pipeline v0: fontes -> texto -> limpeza -> chunks com metadados -> embeddings -> índice (ChromaDB).

Uso:  python -m pipeline.ingest            (ingere só o que mudou)
      python -m pipeline.ingest --force    (reindexa tudo)
"""
import argparse
import datetime
import hashlib
import json
import sys
from pathlib import Path

import yaml

from .chunk import chunk_text
from .clean import clean_text, remove_repeated_lines
from .embed import DEFAULT_MODEL, get_embedder

COLECAO = "ergonomia"


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
    for num, texto in enumerate(paginas, start=1):
        for i, ch in enumerate(chunk_text(clean_text(texto), max_chars, overlap_chars)):
            cid = f"{fonte['id']}-p{num}-c{i}-{hashlib.sha1(ch.encode()).hexdigest()[:8]}"
            registros.append({
                "id": cid,
                "texto": ch,
                "meta": {
                    "fonte_id": fonte["id"],
                    "titulo": fonte.get("titulo", ""),
                    "versao": str(fonte.get("versao", "")),
                    "licenca": str(fonte.get("licenca", "")),
                    "pagina": num,
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
        impressao = f"{sha}|{a.embedder}|{a.max_chars}|{a.overlap_chars}"
        if not a.force and manifest["fontes"].get(f["id"], {}).get("impressao") == impressao:
            print(f"[OK] {f['id']}: sem mudanças, pulando")
            continue

        registros, n_pag = montar_chunks(f, caminho, a.max_chars, a.overlap_chars)
        if not registros:
            print(f"[AVISO] {f['id']}: nenhum texto extraído (PDF escaneado?)")
            continue
        embedder = embedder or get_embedder(a.embedder)
        col.delete(where={"fonte_id": f["id"]})  # remove a versão antiga desta fonte
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

    manifest["parametros"] = {"embedder": a.embedder, "max_chars": a.max_chars,
                              "overlap_chars": a.overlap_chars, "colecao": COLECAO}
    manifest["gerado_em"] = datetime.datetime.now(datetime.timezone.utc).isoformat()
    mpath.parent.mkdir(parents=True, exist_ok=True)
    mpath.write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")
    return 1 if (a.strict and ausentes) else 0


if __name__ == "__main__":
    sys.exit(main())
