"""Avaliação de concordância do Agente de Visão com o checklist manual da equipe (Issue #4).

Responsabilidades:
1. Carregar o conjunto de fotos/cenários de postos de trabalho rotulados manualmente pela equipe
   segundo o checklist ergonômico de 6 dimensões (NR-17) e as saídas `SetupAnalysis` (SPEC.md §9.2)
   do Agente de Visão Multimodal.
2. Calcular métricas de concordância global e por categoria ergonômica:
   - Taxa de Concordância Bruta (Percent Agreement / Accuracy)
   - Coeficiente Kappa de Cohen (kappa) para concordância inter-avaliador descontando o acaso
   - Precision, Recall, F1-score e False Positive Rate (FPR) para detecção de inadequações (`inadequado`)
   - Análise de calibração de confiança (`confidence` e `requires_confirmation`) nos casos divergentes

Uso via CLI:
    python -m evals.vision_checklist_eval --out evals/results/vision_checklist_report.json
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

EVALS_DIR = Path(__file__).resolve().parent
DEFAULT_DATASET_PATH = EVALS_DIR / "datasets" / "vision_setup_checklist.json"
DEFAULT_REPORT_PATH = EVALS_DIR / "results" / "vision_checklist_report.json"

POSITIVE_LABEL = "inadequado"
NEGATIVE_LABEL = "adequado"


def compute_binary_confusion_and_kappa(
    manual_labels: list[str], agent_labels: list[str]
) -> dict[str, Any]:
    """Calcula matriz de confusão, concordância percentual, Kappa de Cohen, Precision, Recall, F1 e FPR.

    Convenção ergonômica:
    - Classe Positiva (`inadequado`): problema/risco ergonômico que precisa de ajuste.
    - Classe Negativa (`adequado`): item em conformidade com o checklist NR-17.
    """
    if len(manual_labels) != len(agent_labels):
        raise ValueError("As listas de rótulos manual e do agente devem ter o mesmo tamanho.")

    n = len(manual_labels)
    if n == 0:
        return {
            "total": 0,
            "tp": 0,
            "fp": 0,
            "fn": 0,
            "tn": 0,
            "agreement_rate": 0.0,
            "cohens_kappa": 0.0,
            "precision": 0.0,
            "recall": 0.0,
            "f1": 0.0,
            "fpr": 0.0,
        }

    tp = fp = fn = tn = 0
    for manual, agent in zip(manual_labels, agent_labels):
        m_pos = manual == POSITIVE_LABEL
        a_pos = agent == POSITIVE_LABEL
        if m_pos and a_pos:
            tp += 1
        elif not m_pos and a_pos:
            fp += 1
        elif m_pos and not a_pos:
            fn += 1
        else:
            tn += 1

    p_o = (tp + tn) / n
    p_yes_manual = (tp + fn) / n
    p_yes_agent = (tp + fp) / n
    p_no_manual = (tn + fp) / n
    p_no_agent = (tn + fn) / n
    p_e = (p_yes_manual * p_yes_agent) + (p_no_manual * p_no_agent)

    if abs(1.0 - p_e) < 1e-9:
        kappa = 1.0 if abs(1.0 - p_o) < 1e-9 else 0.0
    else:
        kappa = (p_o - p_e) / (1.0 - p_e)

    precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
    recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
    f1 = (2 * precision * recall / (precision + recall)) if (precision + recall) > 0 else 0.0
    fpr = fp / (fp + tn) if (fp + tn) > 0 else 0.0

    return {
        "total": n,
        "tp": tp,
        "fp": fp,
        "fn": fn,
        "tn": tn,
        "agreement_rate": round(p_o, 4),
        "cohens_kappa": round(kappa, 4),
        "precision": round(precision, 4),
        "recall": round(recall, 4),
        "f1": round(f1, 4),
        "fpr": round(fpr, 4),
    }


def interpret_kappa(kappa: float) -> str:
    """Classifica o nível de concordância segundo a escala clássica de Landis & Koch (1977)."""
    if kappa >= 0.81:
        return "quase_perfeita"
    if kappa >= 0.61:
        return "substancial"
    if kappa >= 0.41:
        return "moderada"
    if kappa >= 0.21:
        return "razoavel"
    return "fraca"


def evaluate_vision_checklist_concordance(
    dataset_path: Path = DEFAULT_DATASET_PATH,
) -> dict[str, Any]:
    """Avalia a concordância entre o Agente de Visão e o checklist manual aplicado pela equipe."""
    raw = json.loads(Path(dataset_path).read_text(encoding="utf-8"))
    categories: list[str] = raw["categories"]
    photos: list[dict[str, Any]] = raw["labeled_photos"]

    global_manual: list[str] = []
    global_agent: list[str] = []

    per_category_manual: dict[str, list[str]] = {cat: [] for cat in categories}
    per_category_agent: dict[str, list[str]] = {cat: [] for cat in categories}

    per_photo_results: list[dict[str, Any]] = []
    disagreements: list[dict[str, Any]] = []
    concordant_confidences: list[float] = []
    discordant_confidences: list[float] = []

    for photo in photos:
        photo_id = photo["photo_id"]
        manual_map: dict[str, str] = photo["manual_checklist"]
        analysis = photo["vision_agent_analysis"]
        obs_by_cat: dict[str, dict[str, Any]] = {
            obs["category"]: obs for obs in analysis.get("observations", [])
        }

        photo_matches = 0
        photo_items: list[dict[str, Any]] = []

        for cat in categories:
            manual_status = manual_map[cat]
            obs = obs_by_cat.get(cat, {})
            agent_status = obs.get("status", NEGATIVE_LABEL)
            confidence = float(obs.get("confidence", 0.0))
            requires_confirmation = bool(obs.get("requires_confirmation", True))

            global_manual.append(manual_status)
            global_agent.append(agent_status)
            per_category_manual[cat].append(manual_status)
            per_category_agent[cat].append(agent_status)

            matched = manual_status == agent_status
            if matched:
                photo_matches += 1
                concordant_confidences.append(confidence)
            else:
                discordant_confidences.append(confidence)
                disagreements.append(
                    {
                        "photo_id": photo_id,
                        "photo_title": photo["title"],
                        "camera_angle": photo.get("camera_angle", ""),
                        "lighting_condition": photo.get("lighting_condition", ""),
                        "category": cat,
                        "manual_label": manual_status,
                        "agent_label": agent_status,
                        "agent_confidence": confidence,
                        "requires_confirmation": requires_confirmation,
                        "agent_description": obs.get("description", ""),
                    }
                )

            photo_items.append(
                {
                    "category": cat,
                    "manual_label": manual_status,
                    "agent_label": agent_status,
                    "concordant": matched,
                    "confidence": confidence,
                    "requires_confirmation": requires_confirmation,
                }
            )

        photo_agreement = photo_matches / len(categories) if categories else 1.0
        per_photo_results.append(
            {
                "photo_id": photo_id,
                "title": photo["title"],
                "environment_type": photo.get("environment_type", ""),
                "camera_angle": photo.get("camera_angle", ""),
                "lighting_condition": photo.get("lighting_condition", ""),
                "matched_items": photo_matches,
                "total_items": len(categories),
                "agreement_rate": round(photo_agreement, 4),
                "items": photo_items,
            }
        )

    global_metrics = compute_binary_confusion_and_kappa(global_manual, global_agent)
    global_metrics["kappa_interpretation"] = interpret_kappa(global_metrics["cohens_kappa"])

    per_category_metrics: dict[str, dict[str, Any]] = {}
    for cat in categories:
        cat_m = compute_binary_confusion_and_kappa(
            per_category_manual[cat], per_category_agent[cat]
        )
        cat_m["kappa_interpretation"] = interpret_kappa(cat_m["cohens_kappa"])
        per_category_metrics[cat] = cat_m

    macro_agreement = (
        sum(m["agreement_rate"] for m in per_category_metrics.values()) / len(categories)
        if categories
        else 0.0
    )
    macro_kappa = (
        sum(m["cohens_kappa"] for m in per_category_metrics.values()) / len(categories)
        if categories
        else 0.0
    )
    macro_f1 = (
        sum(m["f1"] for m in per_category_metrics.values()) / len(categories)
        if categories
        else 0.0
    )

    mean_conf_concordant = (
        sum(concordant_confidences) / len(concordant_confidences)
        if concordant_confidences
        else 0.0
    )
    mean_conf_discordant = (
        sum(discordant_confidences) / len(discordant_confidences)
        if discordant_confidences
        else 0.0
    )
    discordant_flagged_for_confirmation_rate = (
        sum(1 for d in disagreements if d["requires_confirmation"]) / len(disagreements)
        if disagreements
        else 1.0
    )

    return {
        "experiment_id": raw.get("experiment_id", "EXP-04-VISION-CHECKLIST-CONCORDANCE"),
        "version": raw.get("version", "1.0.0"),
        "total_photos": len(photos),
        "categories_per_photo": len(categories),
        "total_evaluated_items": len(global_manual),
        "global_metrics": global_metrics,
        "macro_averages": {
            "macro_agreement_rate": round(macro_agreement, 4),
            "macro_cohens_kappa": round(macro_kappa, 4),
            "macro_f1": round(macro_f1, 4),
        },
        "confidence_calibration": {
            "mean_confidence_concordant": round(mean_conf_concordant, 4),
            "mean_confidence_discordant": round(mean_conf_discordant, 4),
            "discordant_flagged_requires_confirmation_rate": round(
                discordant_flagged_for_confirmation_rate, 4
            ),
        },
        "per_category_metrics": per_category_metrics,
        "disagreements": disagreements,
        "photos": per_photo_results,
    }


def print_vision_concordance_summary(report: dict[str, Any]) -> None:
    """Imprime relatório executivo de concordância do Agente de Visão no terminal."""
    g = report["global_metrics"]
    cal = report["confidence_calibration"]

    print("=== AVALIAÇÃO DO AGENTE DE VISÃO vs. CHECKLIST MANUAL DA EQUIPE (ISSUE #4) ===")
    print(
        f"Fotos rotuladas: {report['total_photos']} | "
        f"Dimensões por foto: {report['categories_per_photo']} | "
        f"Total de itens verificados: {report['total_evaluated_items']}"
    )
    print("\n--- 1. Métricas Globais de Concordância e Detecção de Inadequações ---")
    print(f"Taxa de Concordância Bruta (Agreement):  {g['agreement_rate']:.4f} ({g['tp'] + g['tn']}/{g['total']})")
    print(f"Kappa de Cohen (Inter-avaliador):        {g['cohens_kappa']:.4f} ({g['kappa_interpretation']})")
    print(f"Precision (classe 'inadequado'):         {g['precision']:.4f}")
    print(f"Recall (classe 'inadequado'):            {g['recall']:.4f}")
    print(f"F1-score (classe 'inadequado'):          {g['f1']:.4f}")
    print(f"False Positive Rate (FPR):               {g['fpr']:.4f}")
    print(f"Matriz de Confusão:                      TP={g['tp']} | FP={g['fp']} | FN={g['fn']} | TN={g['tn']}")

    print("\n--- 2. Concordância por Dimensão do Checklist Ergonômico (NR-17) ---")
    print(f"{'Categoria':<26} {'Concord.':>9} {'Kappa':>8} {'Prec':>8} {'Rec':>8} {'F1':>8}")
    print("-" * 74)
    for cat, m in report["per_category_metrics"].items():
        print(
            f"{cat:<26} {m['agreement_rate']:>9.4f} {m['cohens_kappa']:>8.4f} "
            f"{m['precision']:>8.4f} {m['recall']:>8.4f} {m['f1']:>8.4f}"
        )

    print("\n--- 3. Calibração de Confiança e Ressalvas (RF16 / SPEC.md §9.2) ---")
    print(f"Confiança média nos itens concordantes:  {cal['mean_confidence_concordant']:.4f}")
    print(f"Confiança média nos itens divergentes:   {cal['mean_confidence_discordant']:.4f}")
    print(
        f"Divergências com requires_confirmation:  "
        f"{cal['discordant_flagged_requires_confirmation_rate']:.4f}"
    )
    print("")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", type=Path, default=DEFAULT_DATASET_PATH)
    parser.add_argument("--out", type=Path, default=None, help="Caminho opcional para salvar JSON")
    args = parser.parse_args(argv)

    report = evaluate_vision_checklist_concordance(dataset_path=args.dataset)
    print_vision_concordance_summary(report)

    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
        print(f"[OK] Relatório salvo em {args.out}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
