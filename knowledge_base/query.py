"""Consulta rápida para conferir o índice (usa o mesmo embedder registrado no manifest).

Por padrão, filtra por `--scope general` para evitar vazamento de regras específicas dos
Anexos I (checkout) e II (teleatendimento) da NR-17 em consultas gerais de escritório.

Uso (a partir da raiz do repositório):
  uv run --project backend --extra rag python -m knowledge_base.query "altura do monitor" -k 3
  uv run --project backend --extra rag python -m knowledge_base.query "altura do monitor" -k 3 --scope all
  uv run --project backend --extra rag python -m knowledge_base.query "operador de checkout" -k 3 --scope checkout
"""
import argparse
import json
from pathlib import Path

from .embed import get_embedder
from .ingest import COLECAO, DEFAULT_INDEX_DIR, DEFAULT_MANIFEST, SCOPES_VALIDOS


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("pergunta")
    ap.add_argument("-k", type=int, default=3)
    ap.add_argument(
        "--scope",
        choices=(*SCOPES_VALIDOS, "all"),
        default="general",
        help="filtra por escopo de aplicabilidade (padrão: general; use 'all' para sem filtro)",
    )
    ap.add_argument("--index-dir", default=str(DEFAULT_INDEX_DIR))
    ap.add_argument("--manifest", default=str(DEFAULT_MANIFEST))
    a = ap.parse_args(argv)

    import chromadb
    params = json.loads(Path(a.manifest).read_text(encoding="utf-8"))["parametros"]
    col = chromadb.PersistentClient(path=a.index_dir).get_collection(COLECAO)
    emb = get_embedder(params["embedder"]).encode([a.pergunta])
    query_kwargs = {"query_embeddings": emb, "n_results": a.k}
    if a.scope != "all":
        query_kwargs["where"] = {"scope": a.scope}
    res = col.query(**query_kwargs)
    for doc, meta, dist in zip(res["documents"][0], res["metadatas"][0], res["distances"][0]):
        doc_id = meta.get("document_id", meta.get("fonte_id", "?"))
        version = meta.get("version", meta.get("versao", ""))
        page = meta.get("page", meta.get("pagina", "?"))
        section = meta.get("section", "unspecified")
        scope = meta.get("scope", "general")
        print(f"--- {doc_id} (v: {version}) [{scope} | {section}] pág. {page}  dist={dist:.3f}")
        print(doc[:400], "\n")


if __name__ == "__main__":
    main()
