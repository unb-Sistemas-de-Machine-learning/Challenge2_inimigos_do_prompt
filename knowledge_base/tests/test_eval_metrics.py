import json
import shutil

import pytest

from pipeline.eval_metrics import (
    agregar_metricas_postura,
    avaliar_postura,
    avaliar_resultados_rag,
    calcular_metricas_binarias,
    main,
)


def test_calcular_metricas_binarias_normal_e_zero():
    m = calcular_metricas_binarias(tp=3, fp=1, fn=1, tn=5)
    assert m["precision"] == 0.75
    assert m["recall"] == 0.75
    assert m["f1"] == 0.75
    assert m["fpr"] == round(1 / 6, 4)

    z = calcular_metricas_binarias(tp=0, fp=0, fn=0, tn=0)
    assert (z["precision"], z["recall"], z["f1"], z["fpr"]) == (0.0, 0.0, 0.0, 0.0)


def test_agregar_metricas_postura_por_classe_e_binario():
    resultados = [
        {"id": "c1", "rotulo_esperado": "FORWARD_HEAD", "alerts_triggered": ["FORWARD_HEAD"], "total_frames": 10, "low_confidence_frames": 0, "elapsed_ms": 1.0},
        {"id": "c2", "rotulo_esperado": "TOO_CLOSE", "alerts_triggered": [], "total_frames": 10, "low_confidence_frames": 0, "elapsed_ms": 2.0},
        {"id": "c3", "rotulo_esperado": "postura_adequada", "alerts_triggered": ["SHOULDER_TILT"], "total_frames": 10, "low_confidence_frames": 0, "elapsed_ms": 1.5},
        {"id": "c4", "rotulo_esperado": "baixa_confianca", "alerts_triggered": [], "total_frames": 10, "low_confidence_frames": 10, "elapsed_ms": 0.5},
    ]
    m = agregar_metricas_postura(resultados)
    assert m["por_classe"]["FORWARD_HEAD"]["tp"] == 1
    assert m["por_classe"]["TOO_CLOSE"]["fn"] == 1
    assert m["por_classe"]["SHOULDER_TILT"]["fp"] == 1
    assert m["binario_alerta"]["tp"] == 1
    assert m["binario_alerta"]["fp"] == 1
    assert m["binario_alerta"]["fn"] == 1
    assert m["binario_alerta"]["tn"] == 1
    assert m["taxa_frames_baixa_confianca"] == 0.25
    assert [x["id"] for x in m["falsos_positivos"]] == ["c3"]
    assert [x["id"] for x in m["falsos_negativos"]] == ["c2"]


def test_avaliar_postura_executa_motor_js_real_via_node():
    if shutil.which("node") is None:
        pytest.skip("Node.js nao disponivel no ambiente")
    rel = avaliar_postura("eval/datasets/postura_cenarios.json")
    assert rel["engine_path"].endswith("prototipo/js/posture-engine.js")
    assert "BASELINE SINTETICO" in rel["aviso_escopo"]
    m = rel["metricas"]
    assert m["total_cenarios"] == 22
    # Nenhum cenario negativo (postura adequada, momentaneo < 4s, baixa confianca) deve disparar falso alerta
    assert m["binario_alerta"]["fp"] == 0
    assert m["binario_alerta"]["fpr"] == 0.0
    assert m["taxa_frames_baixa_confianca"] > 0.0
    for cls in ("FORWARD_HEAD", "TOO_CLOSE", "SHOULDER_TILT", "HEAD_TILT"):
        assert m["por_classe"][cls]["tp"] >= 2


def test_avaliar_resultados_rag_detecta_vazamento_de_anexo_e_calcula_metricas():
    perguntas = [
        {
            "id": "q1",
            "pergunta": "altura do monitor",
            "tipo_desvio": "FORWARD_HEAD",
            "document_id_esperado": "nr17",
            "secoes_esperadas": ["17.6 Mobiliário dos postos de trabalho"],
            "secoes_proibidas": ["Anexo II - Trabalho em Teleatendimento/Telemarketing"],
            "cartao_esperado": "card-forward-head-v1",
        },
        {
            "id": "q2",
            "pergunta": "pausas sedentarismo",
            "tipo_desvio": "BREAK_NEEDED",
            "document_id_esperado": "oms2020",
            "secoes_esperadas": [],
            "secoes_proibidas": ["Anexo I - Trabalho dos Operadores de Checkout"],
            "cartao_esperado": "card-break-needed-v1",
        },
    ]
    recuperados = {
        "q1": [
            {"document_id": "nr17", "section": "Anexo II - Trabalho em Teleatendimento/Telemarketing", "page": 14},
            {"document_id": "nr17", "section": "17.6 Mobiliário dos postos de trabalho", "page": 6},
        ],
        "q2": [
            {"document_id": "oms2020", "section": "unspecified", "page": 12},
            {"document_id": "oms2020", "section": "unspecified", "page": 13},
        ],
    }
    cartoes = {
        "FORWARD_HEAD": {"id": "card-forward-head-v1", "status": "rascunho"},
        "BREAK_NEEDED": {"id": "card-break-needed-v1", "status": "rascunho"},
    }
    rel = avaliar_resultados_rag(
        perguntas, recuperados, k=2, cartoes_por_tipo=cartoes, tipos_oficiais=["FORWARD_HEAD", "BREAK_NEEDED"]
    )
    # q1: P@2 = 0.5, Hit = 1, MRR = 0.5, vazamento = 1 chunk; q2: P@2 = 1.0, Hit = 1, MRR = 1.0, vazamento = 0
    assert rel["precision_at_k"] == 0.75
    assert rel["hit_rate_at_k"] == 1.0
    assert rel["mrr"] == 0.75
    assert rel["fpr_vazamento_secao_proibida_chunks"] == 0.25
    assert rel["fpr_vazamento_secao_proibida_consultas"] == 0.5
    assert rel["cobertura_cartoes"]["tipos_com_cartao"] == 2
    assert rel["cobertura_cartoes"]["divergencias_mapeamento"] == []


def test_cli_eval_metrics_rag_ponta_a_ponta_com_hash_e_out(tmp_path):
    pytest.importorskip("chromadb")
    from pipeline.ingest import main as ingest_main

    raw = tmp_path / "raw"
    raw.mkdir()
    (raw / "nr17.txt").write_text(
        "17.6 Mobiliário dos postos de trabalho\n"
        "17.6.1 O mobiliário deve permitir ajuste adequado da tela e altura do assento.\n",
        encoding="utf-8",
    )
    (tmp_path / "sources.yaml").write_text(
        "fontes:\n"
        "  - id: nr17\n"
        "    titulo: NR-17\n"
        "    source: MTE\n"
        "    document_type: official\n"
        "    url_oficial: https://example.org/nr17\n"
        "    arquivo_local: nr17.txt\n"
        "    versao: v1\n"
        "    licenca: publica\n",
        encoding="utf-8",
    )
    idx_dir = tmp_path / "idx"
    manifest = tmp_path / "manifest.json"
    assert ingest_main([
        "--sources", str(tmp_path / "sources.yaml"),
        "--raw-dir", str(raw),
        "--index-dir", str(idx_dir),
        "--manifest", str(manifest),
        "--embedder", "hash",
    ]) == 0

    rag_yaml = tmp_path / "rag.yaml"
    rag_yaml.write_text(
        "versao: '1'\n"
        "perguntas:\n"
        "  - id: t1\n"
        "    pergunta: ajuste da tela e altura do assento\n"
        "    document_id_esperado: nr17\n"
        "    secoes_esperadas:\n"
        "      - '17.6 Mobiliário dos postos de trabalho'\n"
        "    secoes_proibidas:\n"
        "      - 'Anexo I - Trabalho dos Operadores de Checkout'\n",
        encoding="utf-8",
    )
    out_json = tmp_path / "out.json"
    assert main([
        "--parte", "rag",
        "-k", "1",
        "--rag-dataset", str(rag_yaml),
        "--index-dir", str(idx_dir),
        "--manifest", str(manifest),
        "--cards-dir", "cards",
        "--out", str(out_json),
    ]) == 0

    dados = json.loads(out_json.read_text(encoding="utf-8"))
    assert dados["rag"]["hit_rate_at_k"] == 1.0
    assert dados["rag"]["fpr_vazamento_secao_proibida_chunks"] == 0.0
