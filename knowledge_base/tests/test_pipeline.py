import json

import pytest

from knowledge_base.chunk import chunk_text
from knowledge_base.clean import clean_text, remove_repeated_lines
from knowledge_base.ingest import UNSPECIFIED_SECTION, atualizar_secao


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


def test_atualizar_secao_nr17_corpo_sumario_e_anexos():
    sumario_cortado = (
        "SUMÁRIO\n"
        "17.6 Mobiliário dos postos de trabalho\n"
        "17.7 Trabalho com máquinas, equipamentos e ferramentas manuais"
    )
    assert atualizar_secao(sumario_cortado, UNSPECIFIED_SECTION) == (UNSPECIFIED_SECTION, UNSPECIFIED_SECTION)

    sumario_e_inicio = (
        "SUMÁRIO\n"
        "17.1 Objetivo\n"
        "17.2 Campo de Aplicação\n"
        "17.8 Condições de conforto no ambiente de trabalho\n"
        "Anexo I - Trabalho dos Operadores de Checkout\n"
        "17.1 Objetivo\n"
        "17.1.1 Esta Norma estabelece diretrizes."
    )
    sec_chunk, sec = atualizar_secao(sumario_e_inicio, UNSPECIFIED_SECTION)
    assert (sec_chunk, sec) == ("17.1 Objetivo", "17.1 Objetivo")

    sec_chunk, sec = atualizar_secao("17.8 Condições de conforto no ambiente de trabalho\n17.8.1 Iluminação.", sec)
    assert (sec_chunk, sec) == (
        "17.8 Condições de conforto no ambiente de trabalho",
        "17.8 Condições de conforto no ambiente de trabalho",
    )

    sec_chunk, sec = atualizar_secao("ANEXO I da NR 17 TRABALHO DOS OPERADORES DE CHECKOUT Sumário\n1. Objetivo", sec)
    assert (sec_chunk, sec) == (
        "Anexo I - Trabalho dos Operadores de Checkout",
        "Anexo I - Trabalho dos Operadores de Checkout",
    )

    sec_chunk, sec = atualizar_secao("2.1 O posto de trabalho deve permitir alternância de postura.", sec)
    assert (sec_chunk, sec) == (
        "Anexo I - Trabalho dos Operadores de Checkout",
        "Anexo I - Trabalho dos Operadores de Checkout",
    )

    sec_chunk, sec = atualizar_secao("ANEXO II da NR 17 TRABALHO EM TELEATENDIMENTO/TELEMARKETING\nSumário", sec)
    assert (sec_chunk, sec) == (
        "Anexo II - Trabalho em Teleatendimento/Telemarketing",
        "Anexo II - Trabalho em Teleatendimento/Telemarketing",
    )


def test_cabecalho_solto_no_fim_do_chunk_nao_sobrescreve_chunk_atual():
    c1 = (
        "17.1 Objetivo\n"
        "17.1.1 Esta Norma visa estabelecer diretrizes de ergonomia.\n"
        "17.2 Campo de Aplicação"
    )
    sec_c1, prox = atualizar_secao(c1, UNSPECIFIED_SECTION)
    assert sec_c1 == "17.1 Objetivo"
    assert prox == "17.2 Campo de Aplicação"

    c2 = (
        "17.2 Campo de Aplicação\n"
        "17.2.1 Esta Norma se aplica a todas as situações de trabalho.\n"
        "17.3 Avaliação das situações de trabalho"
    )
    sec_c2, prox = atualizar_secao(c2, prox)
    assert sec_c2 == "17.2 Campo de Aplicação"
    assert prox == "17.3 Avaliação das situações de trabalho"

    sec_c3, prox = atualizar_secao("17.3.1 A organização deve realizar avaliação ergonômica.", prox)
    assert sec_c3 == "17.3 Avaliação das situações de trabalho"
    assert prox == "17.3 Avaliação das situações de trabalho"

    c_anexo_fim = "17.8.4.2 Controle de temperatura.\nANEXO I da NR 17 TRABALHO DOS OPERADORES DE CHECKOUT"
    sec_ch, prox_anexo = atualizar_secao(c_anexo_fim, "17.8 Condições de conforto no ambiente de trabalho")
    assert sec_ch == "17.8 Condições de conforto no ambiente de trabalho"
    assert prox_anexo == "Anexo I - Trabalho dos Operadores de Checkout"


def test_atualizar_secao_fallback_unspecified():
    assert atualizar_secao(
        "Regular physical activity has health benefits.", UNSPECIFIED_SECTION
    ) == ("unspecified", "unspecified")


def test_ingest_ponta_a_ponta_idempotente_e_exporta_chunks_jsonl(tmp_path):
    pytest.importorskip("chromadb")
    from knowledge_base.ingest import main

    raw = tmp_path / "raw"
    raw.mkdir()
    (raw / "doc.txt").write_text("Item um sobre monitor.\nItem dois sobre cadeira.\n" * 5, encoding="utf-8")
    (tmp_path / "s.yaml").write_text(
        "fontes:\n"
        "  - id: doc\n"
        "    titulo: Doc\n"
        "    source: Orgao Teste\n"
        "    document_type: official\n"
        "    url_oficial: https://example.org/doc\n"
        "    arquivo_local: doc.txt\n"
        "    versao: v1\n"
        "    licenca: teste\n",
        encoding="utf-8",
    )
    chunks_out = tmp_path / "processed" / "chunks.jsonl"
    args = [
        "--sources", str(tmp_path / "s.yaml"),
        "--raw-dir", str(raw),
        "--index-dir", str(tmp_path / "idx"),
        "--manifest", str(tmp_path / "m.json"),
        "--chunks-out", str(chunks_out),
        "--embedder", "hash",
        "--max-chars", "120",
        "--overlap-chars", "20",
    ]

    # Simula chunk legado com fonte_id para garantir limpeza sem duplicação na migração
    import chromadb
    col = chromadb.PersistentClient(path=str(tmp_path / "idx")).get_or_create_collection("ergonomia")
    col.add(ids=["legacy-1"], documents=["antigo"], metadatas=[{"fonte_id": "doc"}], embeddings=[[0.0] * 64])

    assert main(args) == 0
    m1 = json.loads((tmp_path / "m.json").read_text(encoding="utf-8"))
    assert m1["fontes"]["doc"]["chunks"] >= 1
    assert main(args) == 0  # segunda execução: sem mudanças

    col = chromadb.PersistentClient(path=str(tmp_path / "idx")).get_collection("ergonomia")
    assert col.count() == m1["fontes"]["doc"]["chunks"]  # não duplicou e removeu legado
    sample_meta = col.get(limit=1)["metadatas"][0]
    for campo in ("document_id", "title", "source", "section", "page", "url", "document_type",
                  "version", "license", "chunk"):
        assert campo in sample_meta
    assert sample_meta["document_id"] == "doc"
    assert sample_meta["source"] == "Orgao Teste"
    assert sample_meta["document_type"] == "official"
    assert sample_meta["url"] == "https://example.org/doc"
    assert sample_meta["section"] == "unspecified"

    # Valida exportação JSONL para consumo do BM25
    linhas = [json.loads(l) for l in chunks_out.read_text(encoding="utf-8").splitlines() if l.strip()]
    assert len(linhas) == col.count()
    assert set(linhas[0].keys()) == {"id", "text", "metadata"}
    assert linhas[0]["metadata"]["document_id"] == "doc"
    assert main(args + ["--strict"]) == 0
