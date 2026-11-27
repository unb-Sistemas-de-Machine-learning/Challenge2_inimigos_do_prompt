"""Bootstrap reproduzível do índice ChromaDB a partir do corpus versionado (knowledge_base/corpus/chunks.jsonl).

Dispensa os PDFs brutos em knowledge_base/raw/ para reconstruir o índice local ou de CI.

Uso (a partir da raiz do repositório):
  uv run --project backend --extra rag python -m knowledge_base.bootstrap
  uv run --project backend python -m knowledge_base.bootstrap --embedder hash
"""
import argparse
import sys

from .embed import DEFAULT_MODEL
from .ingest import (
    DEFAULT_CHUNKS_OUT,
    DEFAULT_CORPUS_CHUNKS,
    DEFAULT_INDEX_DIR,
    DEFAULT_MANIFEST,
    reconstruir_de_chunks,
)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--chunks", default=str(DEFAULT_CORPUS_CHUNKS), help="caminho do chunks.jsonl versionado")
    ap.add_argument("--index-dir", default=str(DEFAULT_INDEX_DIR), help="diretório persistente do ChromaDB")
    ap.add_argument("--manifest", default=str(DEFAULT_MANIFEST), help="manifesto local gerado para consulta")
    ap.add_argument("--chunks-out", default=str(DEFAULT_CHUNKS_OUT), help="cópia de trabalho em processed/chunks.jsonl")
    ap.add_argument("--embedder", default=DEFAULT_MODEL, help="nome do modelo ou 'hash' (somente testes/CI)")
    a = ap.parse_args(argv)

    reconstruir_de_chunks(
        chunks_path=a.chunks,
        index_dir=a.index_dir,
        manifest_path=a.manifest,
        embedder_name=a.embedder,
        chunks_out=a.chunks_out,
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
