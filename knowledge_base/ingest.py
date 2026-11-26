"""Pipeline de ingestão da base de conhecimento:
fontes -> texto -> limpeza -> chunks com metadados (§6.5) -> embeddings -> ChromaDB + chunks.jsonl (BM25).

Também suporta reconstrução do ChromaDB diretamente a partir de um corpus JSONL versionado
(--from-chunks), sem exigir PDFs locais em knowledge_base/raw/.

Uso (a partir da raiz do repositório):
  uv run --project backend --extra rag python -m knowledge_base.ingest
  uv run --project backend --extra rag python -m knowledge_base.ingest --force --strict
  uv run --project backend --extra rag python -m knowledge_base.ingest --from-chunks knowledge_base/corpus/chunks.jsonl
  uv run --project backend python -m knowledge_base.ingest --from-chunks knowledge_base/corpus/chunks.jsonl --embedder hash
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

KB_DIR = Path(__file__).resolve().parent
REPO_ROOT = KB_DIR.parent

DEFAULT_SOURCES = KB_DIR / "sources.yaml"
DEFAULT_RAW_DIR = KB_DIR / "raw"
DEFAULT_INDEX_DIR = REPO_ROOT / "backend" / "data" / "chroma"
DEFAULT_MANIFEST = KB_DIR / "processed" / "manifest.json"
DEFAULT_CHUNKS_OUT = KB_DIR / "processed" / "chunks.jsonl"
DEFAULT_CORPUS_CHUNKS = KB_DIR / "corpus" / "chunks.jsonl"

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


def caminho_relativo(path):
    """Retorna caminho POSIX relativo à raiz do repositório quando possível (evita vazar paths absolutos locais)."""
    p = Path(path).resolve()
    try:
        return p.relative_to(REPO_ROOT).as_posix()
    except ValueError:
        return Path(path).as_posix()


def _normalizar_titulo_anexo(subtitulo):
    if not subtitulo:
        return ""
    sub = re.split(r"\bSum[áa]rio\b|\b\d+\.\s", subtitulo, maxsplit=1)[0].strip(" -–:.")
    if not sub:
        return ""
    if sub.isupper():
        minusculas = {"da", "das", "de", "do", "dos", "em", "e", "no", "nos", "na", "nas"}
        palavras = sub.lower().split()
        sub = " ".join(
            p if (idx > 0 and p in minusculas) else "/".join(parte.capitalize() for parte in p.split("/"))
            for idx, p in enumerate(palavras)
        )
    return sub


def atualizar_secao(texto_chunk, secao_atual):
    """Resolve (secao_chunk, proxima_secao) a partir de cabeçalhos reconhecidos no chunk."""
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
        if proxima:
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


def exportar_chunks_jsonl(col, out_path):
    """Exporta todos os chunks indexados na coleção para JSONL (pronto para consumo BM25)."""
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    snap = col.get(include=["documents", "metadatas"])
    itens = sorted(
        zip(snap["ids"], snap["documents"], snap["metadatas"]),
        key=lambda x: (
            str(x[2].get("document_id", "")),
            int(x[2].get("page", 0)),
            int(x[2].get("chunk", 0)),
            x[0],
        ),
    )
    with out_path.open("w", encoding="utf-8") as f:
        for cid, doc, meta in itens:
            f.write(json.dumps({"id": cid, "text": doc, "metadata": meta}, ensure_ascii=False) + "\n")
    return len(itens)


def carregar_chunks_jsonl(chunks_path):
    """Carrega registros {'id', 'text', 'metadata'} de um arquivo JSONL."""
    p = Path(chunks_path)
    if not p.exists():
        raise FileNotFoundError(f"Arquivo chunks.jsonl não encontrado: {p}")
    registros = []
    for num_linha, linha in enumerate(p.read_text(encoding="utf-8").splitlines(), start=1):
        s = linha.strip()
        if not s:
            continue
        item = json.loads(s)
        if not all(k in item for k in ("id", "text", "metadata")):
            raise ValueError(f"Linha {num_linha} inválida em {p}: esperado id, text e metadata.")
        registros.append(item)
    return registros


def reconstruir_de_chunks(chunks_path, index_dir, manifest_path, embedder_name=DEFAULT_MODEL, chunks_out=None):
    """Reconstrói a coleção ChromaDB diretamente a partir de chunks.jsonl (sem precisar de PDFs em raw/)."""
    import chromadb

    chunks_path = Path(chunks_path)
    registros = carregar_chunks_jsonl(chunks_path)
    if not registros:
        raise ValueError(f"Nenhum chunk encontrado em {chunks_path}")

    Path(index_dir).mkdir(parents=True, exist_ok=True)
    cliente = chromadb.PersistentClient(path=str(index_dir))
    # Recria a coleção para evitar conflito de dimensão ao trocar de embedder (ex.: hash 64d <-> MiniLM 384d)
    try:
        cliente.delete_collection(COLECAO)
    except Exception:
        pass
    col = cliente.create_collection(COLECAO)

    embedder = get_embedder(embedder_name)
    for ini in range(0, len(registros), 500):
        lote = registros[ini:ini + 500]
        col.add(
            ids=[r["id"] for r in lote],
            documents=[r["text"] for r in lote],
            metadatas=[r["metadata"] for r in lote],
            embeddings=embedder.encode([r["text"] for r in lote]),
        )

    # Reaproveita metadados de fontes se existir manifest.json irmão do chunks.jsonl
    manifest_irmao = chunks_path.parent / "manifest.json"
    base_manifest = (
        json.loads(manifest_irmao.read_text(encoding="utf-8"))
        if manifest_irmao.exists()
        else {}
    )
    fontes_resumo = dict(base_manifest.get("fontes", {}))
    if not fontes_resumo:
        por_doc = {}
        for r in registros:
            m = r["metadata"]
            did = str(m.get("document_id", "desconhecido"))
            info = por_doc.setdefault(did, {"versao": str(m.get("version", "")), "licenca": str(m.get("license", "")), "paginas": set(), "chunks": 0})
            info["chunks"] += 1
            if m.get("page") is not None:
                info["paginas"].add(m["page"])
        fontes_resumo = {
            did: {"versao": v["versao"], "licenca": v["licenca"], "paginas": len(v["paginas"]), "chunks": v["chunks"]}
            for did, v in por_doc.items()
        }

    if chunks_out and Path(chunks_out).resolve() != chunks_path.resolve():
        exportar_chunks_jsonl(col, chunks_out)
        chunks_registrado = caminho_relativo(chunks_out)
    else:
        chunks_registrado = caminho_relativo(chunks_path)

    base_params = base_manifest.get("parametros", {})
    manifest = {
        "fontes": fontes_resumo,
        "parametros": {
            "embedder": embedder_name,
            "max_chars": base_params.get("max_chars", 1000),
            "overlap_chars": base_params.get("overlap_chars", 150),
            "colecao": COLECAO,
            "metadata_schema": base_params.get("metadata_schema", METADATA_SCHEMA_VERSION),
            "chunks_jsonl": chunks_registrado,
            "origem_bootstrap": caminho_relativo(chunks_path),
        },
        "gerado_em": datetime.datetime.now(datetime.timezone.utc).isoformat(),
    }
    mpath = Path(manifest_path)
    mpath.parent.mkdir(parents=True, exist_ok=True)
    mpath.write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"[BOOTSTRAP] {len(registros)} chunks indexados em {caminho_relativo(index_dir)} (embedder={embedder_name})")
    return len(registros)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--sources", default=str(DEFAULT_SOURCES))
    ap.add_argument("--raw-dir", default=str(DEFAULT_RAW_DIR))
    ap.add_argument("--index-dir", default=str(DEFAULT_INDEX_DIR))
    ap.add_argument("--manifest", default=str(DEFAULT_MANIFEST))
    ap.add_argument("--chunks-out", default=str(DEFAULT_CHUNKS_OUT))
    ap.add_argument(
        "--from-chunks",
        default=None,
        help="reconstrói o ChromaDB diretamente a partir de um chunks.jsonl (dispensa PDFs em raw/)",
    )
    ap.add_argument("--embedder", default=DEFAULT_MODEL, help="nome do modelo ou 'hash' (só testes)")
    ap.add_argument("--max-chars", type=int, default=1000)
    ap.add_argument("--overlap-chars", type=int, default=150)
    ap.add_argument("--force", action="store_true")
    ap.add_argument("--strict", action="store_true", help="falha (exit 1) se algum PDF estiver ausente ou com sha256 divergente")
    a = ap.parse_args(argv)

    if a.from_chunks:
        reconstruir_de_chunks(
            chunks_path=a.from_chunks,
            index_dir=a.index_dir,
            manifest_path=a.manifest,
            embedder_name=a.embedder,
            chunks_out=a.chunks_out,
        )
        return 0

    import chromadb

    fontes = yaml.safe_load(Path(a.sources).read_text(encoding="utf-8"))["fontes"]
    mpath = Path(a.manifest)
    manifest = json.loads(mpath.read_text(encoding="utf-8")) if mpath.exists() else {"fontes": {}}

    Path(a.index_dir).mkdir(parents=True, exist_ok=True)
    cliente = chromadb.PersistentClient(path=a.index_dir)
    col = cliente.get_or_create_collection(COLECAO)
    embedder, problemas = None, 0

    for f in fontes:
        caminho = Path(a.raw_dir) / f["arquivo_local"]
        if not caminho.exists():
            print(f"[AVISO] {f['id']}: arquivo ausente em {caminho}")
            problemas += 1
            continue
        sha = sha256_arquivo(caminho)
        sha_esperado = f.get("sha256")
        if sha_esperado and sha != sha_esperado:
            print(f"[AVISO] {f['id']}: sha256 divergente do registrado em sources.yaml (obtido={sha}, esperado={sha_esperado})")
            problemas += 1
            if a.strict:
                continue

        impressao = f"{sha}|{a.embedder}|{a.max_chars}|{a.overlap_chars}|{METADATA_SCHEMA_VERSION}"
        if not a.force and manifest["fontes"].get(f["id"], {}).get("impressao") == impressao:
            print(f"[OK] {f['id']}: sem mudanças, pulando")
            continue

        registros, n_pag = montar_chunks(f, caminho, a.max_chars, a.overlap_chars)
        if not registros:
            print(f"[AVISO] {f['id']}: nenhum texto extraído (PDF escaneado?)")
            continue
        embedder = embedder or get_embedder(a.embedder)
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

    n_exportados = exportar_chunks_jsonl(col, a.chunks_out)
    print(f"[EXPORTADO] {n_exportados} chunks em {caminho_relativo(a.chunks_out)}")

    manifest["parametros"] = {
        "embedder": a.embedder,
        "max_chars": a.max_chars,
        "overlap_chars": a.overlap_chars,
        "colecao": COLECAO,
        "metadata_schema": METADATA_SCHEMA_VERSION,
        "chunks_jsonl": caminho_relativo(a.chunks_out),
    }
    manifest["gerado_em"] = datetime.datetime.now(datetime.timezone.utc).isoformat()
    mpath.parent.mkdir(parents=True, exist_ok=True)
    mpath.write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")
    return 1 if (a.strict and problemas) else 0


if __name__ == "__main__":
    sys.exit(main())
