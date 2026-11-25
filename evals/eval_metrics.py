"""Avaliação quantitativa (RNF07 / SPEC.md §13.1 e §13.2).

Executa duas frentes de avaliação sem depender de mídia pessoal nem de LLM:
- Parte A (postura): executa o motor TS real (frontend/src/posture-engine/postureEngine.ts)
  via Node.js sobre um conjunto rotulado de landmarks numéricos e calcula Precision, Recall, F1 e FPR.
- Parte B (rag): consulta o índice ChromaDB com perguntas rotuladas (incluindo detecção
  de vazamento dos Anexos I e II da NR-17) e valida cobertura de cartões em knowledge_base/cards/*.yaml.

Uso (a partir da raiz do repositório):
  uv run --project backend python -m evals.eval_metrics --parte postura
  uv run --project backend --extra rag python -m evals.eval_metrics --parte rag -k 3
  uv run --project backend --extra rag python -m evals.eval_metrics --parte tudo -k 3 [--out relatorio.json]
"""
import argparse
import json
import subprocess
import sys
from pathlib import Path

import yaml

from knowledge_base.cards import DEFAULT_CARDS_DIR, carregar_cartoes
from knowledge_base.embed import get_embedder
from knowledge_base.ingest import COLECAO, DEFAULT_INDEX_DIR, DEFAULT_MANIFEST

EVALS_DIR = Path(__file__).resolve().parent
DEFAULT_POSTURA_DATASET = EVALS_DIR / "datasets" / "postura_cenarios.json"
DEFAULT_RAG_DATASET = EVALS_DIR / "datasets" / "rag_perguntas.yaml"
DEFAULT_RUNNER = EVALS_DIR / "run_posture_engine.mjs"

CLASSES_POSTURA = ("FORWARD_HEAD", "TOO_CLOSE", "SHOULDER_TILT", "HEAD_TILT")


def calcular_metricas_binarias(tp, fp, fn, tn):
    """Calcula Precision, Recall, F1-score e False Positive Rate (FPR) com proteção contra zero."""
    precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
    recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
    f1 = (2 * precision * recall / (precision + recall)) if (precision + recall) > 0 else 0.0
    fpr = fp / (fp + tn) if (fp + tn) > 0 else 0.0
    return {
        "tp": tp,
        "fp": fp,
        "fn": fn,
        "tn": tn,
        "precision": round(precision, 4),
        "recall": round(recall, 4),
        "f1": round(f1, 4),
        "fpr": round(fpr, 4),
    }


def agregar_metricas_postura(resultados, classes=CLASSES_POSTURA):
    """Agrega matriz de confusão e métricas por classe, macro, micro e binária (alerta vs. sem desvio)."""
    por_classe = {}
    tot_tp = tot_fp = tot_fn = tot_tn = 0

    for cls in classes:
        tp = fp = fn = tn = 0
        for r in resultados:
            esperado_pos = r["rotulo_esperado"] == cls
            predito_pos = cls in r["alerts_triggered"]
            if esperado_pos and predito_pos:
                tp += 1
            elif not esperado_pos and predito_pos:
                fp += 1
            elif esperado_pos and not predito_pos:
                fn += 1
            else:
                tn += 1
        por_classe[cls] = calcular_metricas_binarias(tp, fp, fn, tn)
        tot_tp += tp
        tot_fp += fp
        tot_fn += fn
        tot_tn += tn

    n_cls = len(classes)
    macro = {
        m: round(sum(por_classe[c][m] for c in classes) / n_cls, 4) if n_cls else 0.0
        for m in ("precision", "recall", "f1", "fpr")
    }
    micro = calcular_metricas_binarias(tot_tp, tot_fp, tot_fn, tot_tn)

    bin_tp = bin_fp = bin_fn = bin_tn = 0
    falsos_positivos_detalhes = []
    falsos_negativos_detalhes = []
    for r in resultados:
        esperado_desvio = r["rotulo_esperado"] in classes
        emitiu_alerta = len(r["alerts_triggered"]) > 0
        if esperado_desvio and emitiu_alerta:
            bin_tp += 1
        elif not esperado_desvio and emitiu_alerta:
            bin_fp += 1
            falsos_positivos_detalhes.append({"id": r["id"], "esperado": r["rotulo_esperado"], "alertas": r["alerts_triggered"]})
        elif esperado_desvio and not emitiu_alerta:
            bin_fn += 1
            falsos_negativos_detalhes.append({"id": r["id"], "esperado": r["rotulo_esperado"], "max_values": r.get("max_values", {})})
        else:
            bin_tn += 1

    total_frames = sum(r.get("total_frames", 0) for r in resultados)
    low_conf_frames = sum(r.get("low_confidence_frames", 0) for r in resultados)
    latencias = [r.get("elapsed_ms", 0.0) for r in resultados]

    return {
        "total_cenarios": len(resultados),
        "por_classe": por_classe,
        "macro": macro,
        "micro": micro,
        "binario_alerta": calcular_metricas_binarias(bin_tp, bin_fp, bin_fn, bin_tn),
        "taxa_frames_baixa_confianca": round(low_conf_frames / total_frames, 4) if total_frames else 0.0,
        "latencia_media_cenario_ms": round(sum(latencias) / len(latencias), 3) if latencias else 0.0,
        "falsos_positivos": falsos_positivos_detalhes,
        "falsos_negativos": falsos_negativos_detalhes,
    }


def avaliar_postura(dataset_path=DEFAULT_POSTURA_DATASET, runner_path=DEFAULT_RUNNER):
    """Executa o detector TS real via Node.js e retorna relatório estruturado."""
    dataset_path = Path(dataset_path).resolve()
    runner_path = Path(runner_path).resolve()

    proc = subprocess.run(
        ["node", str(runner_path), str(dataset_path)],
        capture_output=True,
        text=True,
        check=False,
    )
    if proc.returncode != 0:
        raise RuntimeError(f"Falha ao executar motor postural via Node.js:\n{proc.stderr or proc.stdout}")

    bruto = json.loads(proc.stdout)
    metricas = agregar_metricas_postura(bruto["resultados"], tuple(bruto["classes_avaliadas"]))
    return {
        "aviso_escopo": (
            "BASELINE SINTETICO DE REGRESSAO DO MOTOR (landmarks numericos sem midia; "
            "nao substitui a coleta real com voluntarios prevista em SPEC.md §13.1 e "
            "docs/protocolo-coleta-landmarks.md)."
        ),
        "engine_version": bruto["engine_version"],
        "engine_path": bruto["engine_path"],
        "dataset_tipo": bruto["dataset_tipo"],
        "dataset_versao": bruto["dataset_versao"],
        "metricas": metricas,
        "cenarios": bruto["resultados"],
    }


def _chunk_relevante(meta, pergunta):
    doc_id = meta.get("document_id", meta.get("fonte_id", ""))
    secao = meta.get("section", "unspecified")
    secoes_esperadas = pergunta.get("secoes_esperadas") or []
    secoes_proibidas = set(pergunta.get("secoes_proibidas") or [])
    if secao in secoes_proibidas:
        return False
    if doc_id != pergunta["document_id_esperado"]:
        return False
    if secoes_esperadas:
        return secao in secoes_esperadas
    return True


def avaliar_resultados_rag(perguntas, recuperados_por_id, k, cartoes_por_tipo=None, tipos_oficiais=None):
    """Calcula métricas de recuperação (Precision@k, Recall@k/Hit Rate, F1@k, MRR e FPR de vazamento)."""
    detalhes = []
    soma_prec = 0.0
    soma_hit = 0.0
    soma_mrr = 0.0

    chunks_avaliados_com_proibicao = 0
    chunks_vazamento = 0
    consultas_com_proibicao = 0
    consultas_com_vazamento = 0

    for p in perguntas:
        metas = (recuperados_por_id.get(p["id"]) or [])[:k]
        secoes_proibidas = set(p.get("secoes_proibidas") or [])
        relevantes = [_chunk_relevante(m, p) for m in metas]
        vazamentos = [m.get("section", "unspecified") in secoes_proibidas for m in metas]

        n_ret = len(metas)
        prec_k = sum(relevantes) / n_ret if n_ret > 0 else 0.0
        hit_k = 1.0 if any(relevantes) else 0.0
        mrr = 0.0
        for rank, eh_rel in enumerate(relevantes, start=1):
            if eh_rel:
                mrr = 1.0 / rank
                break

        soma_prec += prec_k
        soma_hit += hit_k
        soma_mrr += mrr

        if secoes_proibidas:
            consultas_com_proibicao += 1
            chunks_avaliados_com_proibicao += n_ret
            chunks_vazamento += sum(vazamentos)
            if any(vazamentos):
                consultas_com_vazamento += 1

        detalhes.append({
            "id": p["id"],
            "pergunta": p["pergunta"],
            "document_id_esperado": p["document_id_esperado"],
            "hit_at_k": int(hit_k),
            "precision_at_k": round(prec_k, 4),
            "mrr": round(mrr, 4),
            "vazamento_secao_proibida": any(vazamentos),
            "recuperados": [
                {
                    "document_id": m.get("document_id", ""),
                    "section": m.get("section", "unspecified"),
                    "page": m.get("page", None),
                    "relevante": rel,
                    "secao_proibida": vaz,
                }
                for m, rel, vaz in zip(metas, relevantes, vazamentos)
            ],
        })

    n_perg = len(perguntas)
    precision_at_k = soma_prec / n_perg if n_perg else 0.0
    hit_rate_at_k = soma_hit / n_perg if n_perg else 0.0
    f1_at_k = (
        2 * precision_at_k * hit_rate_at_k / (precision_at_k + hit_rate_at_k)
        if (precision_at_k + hit_rate_at_k) > 0
        else 0.0
    )
    mrr_medio = soma_mrr / n_perg if n_perg else 0.0
    fpr_vazamento_chunks = (
        chunks_vazamento / chunks_avaliados_com_proibicao if chunks_avaliados_com_proibicao else 0.0
    )
    fpr_vazamento_consultas = (
        consultas_com_vazamento / consultas_com_proibicao if consultas_com_proibicao else 0.0
    )

    cobertura_cartoes = None
    if cartoes_por_tipo is not None:
        tipos = sorted(tipos_oficiais or cartoes_por_tipo.keys())
        mapeados = [t for t in tipos if t in cartoes_por_tipo]
        faltando = [t for t in tipos if t not in cartoes_por_tipo]
        erros_cartao = []
        for p in perguntas:
            cid_esp = p.get("cartao_esperado")
            tipo = p.get("tipo_desvio")
            if cid_esp and tipo:
                encontrado = cartoes_por_tipo.get(tipo)
                if not encontrado or encontrado.get("id") != cid_esp:
                    erros_cartao.append({"pergunta_id": p["id"], "tipo_desvio": tipo, "esperado": cid_esp})
        cobertura_cartoes = {
            "tipos_oficiais": len(tipos),
            "tipos_com_cartao": len(mapeados),
            "tipos_faltando": faltando,
            "status_por_tipo": {t: cartoes_por_tipo[t].get("status", "?") for t in mapeados},
            "divergencias_mapeamento": erros_cartao,
        }

    return {
        "k": k,
        "total_perguntas": n_perg,
        "precision_at_k": round(precision_at_k, 4),
        "recall_at_k_hit_rate": round(hit_rate_at_k, 4),
        "f1_at_k": round(f1_at_k, 4),
        "hit_rate_at_k": round(hit_rate_at_k, 4),
        "mrr": round(mrr_medio, 4),
        "fpr_vazamento_secao_proibida_chunks": round(fpr_vazamento_chunks, 4),
        "fpr_vazamento_secao_proibida_consultas": round(fpr_vazamento_consultas, 4),
        "chunks_vazamento": chunks_vazamento,
        "chunks_avaliados_com_proibicao": chunks_avaliados_com_proibicao,
        "consultas_com_vazamento": consultas_com_vazamento,
        "consultas_com_proibicao": consultas_com_proibicao,
        "cobertura_cartoes": cobertura_cartoes,
        "detalhes": detalhes,
    }


def avaliar_rag(
    rag_dataset_path=DEFAULT_RAG_DATASET,
    index_dir=DEFAULT_INDEX_DIR,
    manifest_path=DEFAULT_MANIFEST,
    cards_dir=DEFAULT_CARDS_DIR,
    k=3,
    embedder_override=None,
):
    """Consulta o índice ChromaDB real e calcula métricas da Parte B."""
    import chromadb

    dados = yaml.safe_load(Path(rag_dataset_path).read_text(encoding="utf-8"))
    perguntas = dados["perguntas"]

    embedder_nome = embedder_override
    if not embedder_nome:
        params = json.loads(Path(manifest_path).read_text(encoding="utf-8"))["parametros"]
        embedder_nome = params["embedder"]

    col = chromadb.PersistentClient(path=str(index_dir)).get_collection(COLECAO)
    embedder = get_embedder(embedder_nome)
    vetores = embedder.encode([p["pergunta"] for p in perguntas])
    res = col.query(query_embeddings=vetores, n_results=k)

    recuperados_por_id = {
        p["id"]: metas for p, metas in zip(perguntas, res["metadatas"])
    }

    cartoes_por_tipo = {}
    tipos_oficiais = []
    cdir = Path(cards_dir)
    if cdir.exists():
        tipos_arq = cdir / "_tipos_desvio.yaml"
        if tipos_arq.exists():
            tipos_oficiais = yaml.safe_load(tipos_arq.read_text(encoding="utf-8")).get("tipos", [])
        for _, card in carregar_cartoes(cdir):
            if card.get("tipo_desvio"):
                cartoes_por_tipo[card["tipo_desvio"]] = card

    relatorio = avaliar_resultados_rag(
        perguntas, recuperados_por_id, k=k, cartoes_por_tipo=cartoes_por_tipo, tipos_oficiais=tipos_oficiais
    )
    relatorio["embedder"] = embedder_nome
    relatorio["index_chunks"] = col.count()
    return relatorio


def imprimir_relatorio_postura(rel):
    m = rel["metricas"]
    print("=== AVALIACAO PARTE A — DESVIOS POSTURAIS (RNF07) ===")
    print(f"AVISO: {rel['aviso_escopo']}")
    print(f"Motor: {rel['engine_path']} (v{rel['engine_version']}) | Cenarios: {m['total_cenarios']}")
    print("")
    print(f"{'Classe':<16} {'TP':>3} {'FP':>3} {'FN':>3} {'TN':>3} {'Prec':>7} {'Rec':>7} {'F1':>7} {'FPR':>7}")
    print("-" * 64)
    for cls, s in m["por_classe"].items():
        print(
            f"{cls:<16} {s['tp']:>3} {s['fp']:>3} {s['fn']:>3} {s['tn']:>3} "
            f"{s['precision']:>7.4f} {s['recall']:>7.4f} {s['f1']:>7.4f} {s['fpr']:>7.4f}"
        )
    print("-" * 64)
    mac = m["macro"]
    mic = m["micro"]
    b = m["binario_alerta"]
    print(f"{'MACRO':<16} {'-':>3} {'-':>3} {'-':>3} {'-':>3} {mac['precision']:>7.4f} {mac['recall']:>7.4f} {mac['f1']:>7.4f} {mac['fpr']:>7.4f}")
    print(f"{'MICRO':<16} {mic['tp']:>3} {mic['fp']:>3} {mic['fn']:>3} {mic['tn']:>3} {mic['precision']:>7.4f} {mic['recall']:>7.4f} {mic['f1']:>7.4f} {mic['fpr']:>7.4f}")
    print(f"{'BINARIO_ALERTA':<16} {b['tp']:>3} {b['fp']:>3} {b['fn']:>3} {b['tn']:>3} {b['precision']:>7.4f} {b['recall']:>7.4f} {b['f1']:>7.4f} {b['fpr']:>7.4f}")
    print("")
    print(
        f"Frames LOW_CONFIDENCE: {m['taxa_frames_baixa_confianca'] * 100:.2f}% | "
        f"Latencia media por cenario (motor puro Node.js): {m['latencia_media_cenario_ms']:.3f} ms"
    )
    if m["falsos_positivos"]:
        print("Falsos positivos:", [x["id"] for x in m["falsos_positivos"]])
    if m["falsos_negativos"]:
        print("Falsos negativos:", [x["id"] for x in m["falsos_negativos"]])
    print("")


def imprimir_relatorio_rag(rel):
    k = rel["k"]
    print(f"=== AVALIACAO PARTE B — RECUPERACAO RAG E CARTOES (k={k}) ===")
    print(f"Embedder: {rel['embedder']} | Chunks no indice: {rel['index_chunks']} | Perguntas: {rel['total_perguntas']}")
    print("")
    print(f"Precision@{k} (chunks relevantes / {k}):           {rel['precision_at_k']:.4f}")
    print(f"Recall@{k} / Hit Rate@{k} (consultas com acerto):  {rel['hit_rate_at_k']:.4f}")
    print(f"F1@{k} (media harmonica Prec@{k} e Hit@{k}):       {rel['f1_at_k']:.4f}")
    print(f"MRR@{k}:                                         {rel['mrr']:.4f}")
    print(
        f"FPR vazamento secao proibida (chunks):          "
        f"{rel['fpr_vazamento_secao_proibida_chunks']:.4f} "
        f"({rel['chunks_vazamento']}/{rel['chunks_avaliados_com_proibicao']})"
    )
    print(
        f"FPR vazamento secao proibida (consultas):       "
        f"{rel['fpr_vazamento_secao_proibida_consultas']:.4f} "
        f"({rel['consultas_com_vazamento']}/{rel['consultas_com_proibicao']})"
    )
    if rel.get("cobertura_cartoes"):
        cc = rel["cobertura_cartoes"]
        print(
            f"Cobertura de cartoes (inclui BREAK_NEEDED):     "
            f"{cc['tipos_com_cartao']}/{cc['tipos_oficiais']} tipos "
            f"| divergencias={len(cc['divergencias_mapeamento'])}"
        )
    print("")
    print(f"{'ID':<8} {'Hit':>3} {'P@k':>6} {'MRR':>6} {'Vaz?':>5}  Top-1 recuperado")
    print("-" * 78)
    for d in rel["detalhes"]:
        top1 = d["recuperados"][0] if d["recuperados"] else {}
        top1_str = f"{top1.get('document_id', '?')} [{top1.get('section', '?')}] p.{top1.get('page', '?')}"
        vaz = "SIM" if d["vazamento_secao_proibida"] else "nao"
        print(f"{d['id']:<8} {d['hit_at_k']:>3} {d['precision_at_k']:>6.2f} {d['mrr']:>6.2f} {vaz:>5}  {top1_str}")
    print("")


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--parte", choices=("postura", "rag", "tudo"), default="tudo")
    ap.add_argument("-k", type=int, default=3)
    ap.add_argument("--postura-dataset", default=str(DEFAULT_POSTURA_DATASET))
    ap.add_argument("--rag-dataset", default=str(DEFAULT_RAG_DATASET))
    ap.add_argument("--index-dir", default=str(DEFAULT_INDEX_DIR))
    ap.add_argument("--manifest", default=str(DEFAULT_MANIFEST))
    ap.add_argument("--cards-dir", default=str(DEFAULT_CARDS_DIR))
    ap.add_argument("--embedder", default=None, help="sobrescreve o embedder do manifest (ex.: 'hash' em testes)")
    ap.add_argument("--out", default=None, help="grava o relatorio completo em JSON apenas quando informado")
    a = ap.parse_args(argv)

    saida = {}
    if a.parte in ("postura", "tudo"):
        rel_postura = avaliar_postura(a.postura_dataset)
        imprimir_relatorio_postura(rel_postura)
        saida["postura"] = rel_postura

    if a.parte in ("rag", "tudo"):
        rel_rag = avaliar_rag(
            a.rag_dataset,
            index_dir=a.index_dir,
            manifest_path=a.manifest,
            cards_dir=a.cards_dir,
            k=a.k,
            embedder_override=a.embedder,
        )
        imprimir_relatorio_rag(rel_rag)
        saida["rag"] = rel_rag

    if a.out:
        out_path = Path(a.out)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(json.dumps(saida, indent=2, ensure_ascii=False), encoding="utf-8")
        print(f"[SALVO] Relatorio gravado em {out_path}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
