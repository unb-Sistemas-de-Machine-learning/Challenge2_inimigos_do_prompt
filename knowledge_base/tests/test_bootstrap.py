import json
from pathlib import Path

import pytest

from knowledge_base.bootstrap import main as bootstrap_main
from knowledge_base.ingest import DEFAULT_CORPUS_CHUNKS, caminho_relativo
from knowledge_base.ingest import main as ingest_main


def test_bootstrap_reconstroi_chroma_a_partir_de_chunks_jsonl_em_tmp_path(tmp_path):
    pytest.importorskip("chromadb")
    import chromadb

    corpus_dir = tmp_path / "corpus"
    corpus_dir.mkdir()
    chunks_path = corpus_dir / "chunks.jsonl"
    registros = [
        {
            "id": "nr17-p6-c0-abc12345",
            "text": "17.6 O mobiliário do posto de trabalho deve permitir regulagens.",
            "metadata": {
                "document_id": "nr17",
                "title": "NR-17 - Ergonomia",
                "source": "Ministério do Trabalho e Emprego",
                "section": "17.6 Mobiliário dos postos de trabalho",
                "page": 6,
                "url": "https://example.org/nr17",
                "document_type": "official",
                "version": "Portaria MTP nº 4.219/2022",
                "license": "Ato normativo oficial",
                "chunk": 0,
            },
        },
        {
            "id": "oms2020-p12-c0-def67890",
            "text": "Adults should limit the amount of time spent being sedentary.",
            "metadata": {
                "document_id": "oms2020",
                "title": "WHO guidelines",
                "source": "World Health Organization",
                "section": "unspecified",
                "page": 12,
                "url": "https://example.org/oms2020",
                "document_type": "official",
                "version": "2020",
                "license": "CC BY-NC-SA 3.0 IGO",
                "chunk": 0,
            },
        },
    ]
    chunks_path.write_text(
        "\n".join(json.dumps(r, ensure_ascii=False) for r in registros) + "\n",
        encoding="utf-8",
    )

    idx_dir = tmp_path / "chroma"
    manifest_path = tmp_path / "processed" / "manifest.json"
    chunks_out = tmp_path / "processed" / "chunks.jsonl"

    assert bootstrap_main([
        "--chunks", str(chunks_path),
        "--index-dir", str(idx_dir),
        "--manifest", str(manifest_path),
        "--chunks-out", str(chunks_out),
        "--embedder", "hash",
    ]) == 0

    col = chromadb.PersistentClient(path=str(idx_dir)).get_collection("ergonomia")
    assert col.count() == 2
    snap = col.get(ids=["nr17-p6-c0-abc12345"], include=["metadatas", "documents"])
    assert snap["metadatas"][0]["document_id"] == "nr17"
    assert snap["metadatas"][0]["section"] == "17.6 Mobiliário dos postos de trabalho"
    assert manifest_path.exists()
    m = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert m["parametros"]["embedder"] == "hash"
    assert set(m["fontes"].keys()) == {"nr17", "oms2020"}

    # Reexecutar bootstrap (via ingest --from-chunks) deve recriar a coleção sem duplicar
    assert ingest_main([
        "--from-chunks", str(chunks_path),
        "--index-dir", str(idx_dir),
        "--manifest", str(manifest_path),
        "--chunks-out", str(chunks_out),
        "--embedder", "hash",
    ]) == 0
    col = chromadb.PersistentClient(path=str(idx_dir)).get_collection("ergonomia")
    assert col.count() == 2


def test_bootstrap_corpus_versionado_completo_com_hash(tmp_path):
    pytest.importorskip("chromadb")
    import chromadb

    assert DEFAULT_CORPUS_CHUNKS.exists(), "knowledge_base/corpus/chunks.jsonl deve estar versionado"
    corpus_manifest = DEFAULT_CORPUS_CHUNKS.parent / "manifest.json"
    assert corpus_manifest.exists(), "knowledge_base/corpus/manifest.json deve estar versionado"
    cm = json.loads(corpus_manifest.read_text(encoding="utf-8"))
    assert not Path(cm["parametros"]["chunks_jsonl"]).is_absolute()

    idx_dir = tmp_path / "chroma"
    manifest_path = tmp_path / "manifest.json"
    chunks_out = tmp_path / "chunks.jsonl"
    assert bootstrap_main([
        "--chunks", str(DEFAULT_CORPUS_CHUNKS),
        "--index-dir", str(idx_dir),
        "--manifest", str(manifest_path),
        "--chunks-out", str(chunks_out),
        "--embedder", "hash",
    ]) == 0

    col = chromadb.PersistentClient(path=str(idx_dir)).get_collection("ergonomia")
    assert col.count() == 507
    m = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert m["parametros"]["origem_bootstrap"] == "knowledge_base/corpus/chunks.jsonl"


def test_ingest_strict_falha_quando_sha256_diverge(tmp_path):
    pytest.importorskip("chromadb")

    raw = tmp_path / "raw"
    raw.mkdir()
    (raw / "doc.txt").write_text("Conteudo alterado.", encoding="utf-8")
    (tmp_path / "s.yaml").write_text(
        "fontes:\n"
        "  - id: doc\n"
        "    titulo: Doc\n"
        "    source: Orgao\n"
        "    document_type: official\n"
        "    url_oficial: https://example.org/doc\n"
        "    arquivo_local: doc.txt\n"
        "    sha256: '0000000000000000000000000000000000000000000000000000000000000000'\n"
        "    versao: v1\n"
        "    licenca: publica\n",
        encoding="utf-8",
    )
    rc = ingest_main([
        "--sources", str(tmp_path / "s.yaml"),
        "--raw-dir", str(raw),
        "--index-dir", str(tmp_path / "idx"),
        "--manifest", str(tmp_path / "m.json"),
        "--chunks-out", str(tmp_path / "chunks.jsonl"),
        "--embedder", "hash",
        "--strict",
    ])
    assert rc == 1


def test_caminho_relativo_remove_prefixo_absoluto_do_repo():
    rel = caminho_relativo(DEFAULT_CORPUS_CHUNKS)
    assert rel == "knowledge_base/corpus/chunks.jsonl"
    assert not Path(rel).is_absolute()
