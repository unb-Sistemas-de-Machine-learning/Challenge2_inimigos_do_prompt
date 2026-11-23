"""Consulta rápida para conferir o índice (usa o mesmo embedder registrado no manifest).

Uso:  python -m pipeline.query "altura do monitor" -k 3
"""
import argparse
import json
from pathlib import Path

from .embed import get_embedder
from .ingest import COLECAO


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("pergunta")
    ap.add_argument("-k", type=int, default=3)
    ap.add_argument("--index-dir", default="data/index")
    ap.add_argument("--manifest", default="data/manifest.json")
    a = ap.parse_args(argv)

    import chromadb
    params = json.loads(Path(a.manifest).read_text(encoding="utf-8"))["parametros"]
    col = chromadb.PersistentClient(path=a.index_dir).get_collection(COLECAO)
    emb = get_embedder(params["embedder"]).encode([a.pergunta])
    res = col.query(query_embeddings=emb, n_results=a.k)
    for doc, meta, dist in zip(res["documents"][0], res["metadatas"][0], res["distances"][0]):
        doc_id = meta.get("document_id", meta.get("fonte_id", "?"))
        version = meta.get("version", meta.get("versao", ""))
        page = meta.get("page", meta.get("pagina", "?"))
        section = meta.get("section", "unspecified")
        print(f"--- {doc_id} (v: {version}) [{section}] pág. {page}  dist={dist:.3f}")
        print(doc[:400], "\n")


if __name__ == "__main__":
    main()
