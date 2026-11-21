import json

import pytest

from pipeline.chunk import chunk_text
from pipeline.clean import clean_text, remove_repeated_lines


def test_chunks_respeitam_tamanho_e_nao_perdem_texto():
    texto = "\n".join(f"Item {i}. " + "palavra " * 20 for i in range(30))
    chunks = chunk_text(texto, max_chars=300, overlap_chars=50)
    assert len(chunks) > 1
    assert all(len(c) <= 300 + 60 for c in chunks)  # tolerância pela sobreposição
    junto = "\n".join(chunks)
    for i in range(30):
        assert f"Item {i}." in junto


def test_unidade_muito_longa_e_quebrada():
    chunks = chunk_text("a" * 2500, max_chars=1000, overlap_chars=0)
    assert len(chunks) == 3


def test_remove_cabecalho_repetido():
    paginas = [f"Ministério X\ntexto da página {i}\nrodapé" for i in range(5)]
    limpas = remove_repeated_lines(paginas)
    assert all("Ministério X" not in p and "rodapé" not in p for p in limpas)
    assert "texto da página 2" in limpas[2]


def test_clean_junta_linhas_mas_preserva_itens():
    bruto = "17.1 Esta norma\nestabelece parâmetros.\n17.2 Outro item\n12\n"
    limpo = clean_text(bruto)
    assert "17.1 Esta norma estabelece parâmetros." in limpo
    assert "\n17.2 Outro item" in limpo
    assert "\n12" not in limpo


def test_ingest_ponta_a_ponta_e_idempotente(tmp_path):
    pytest.importorskip("chromadb")
    from pipeline.ingest import main

    raw = tmp_path / "raw"
    raw.mkdir()
    (raw / "doc.txt").write_text("Item um sobre monitor.\nItem dois sobre cadeira.\n" * 5, encoding="utf-8")
    (tmp_path / "s.yaml").write_text(
        "fontes:\n  - id: doc\n    titulo: Doc\n    arquivo_local: doc.txt\n    versao: v1\n    licenca: teste\n",
        encoding="utf-8")
    args = ["--sources", str(tmp_path / "s.yaml"), "--raw-dir", str(raw),
            "--index-dir", str(tmp_path / "idx"), "--manifest", str(tmp_path / "m.json"),
            "--embedder", "hash", "--max-chars", "120", "--overlap-chars", "20"]
    assert main(args) == 0
    m1 = json.loads((tmp_path / "m.json").read_text())
    assert m1["fontes"]["doc"]["chunks"] >= 1
    assert main(args) == 0  # segunda execução: sem mudanças
    import chromadb
    col = chromadb.PersistentClient(path=str(tmp_path / "idx")).get_collection("ergonomia")
    assert col.count() == m1["fontes"]["doc"]["chunks"]  # não duplicou
    assert main(args + ["--strict"]) == 0
