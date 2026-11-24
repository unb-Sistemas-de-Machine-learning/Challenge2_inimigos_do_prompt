"""Testes automatizados para a concordância do Agente de Visão com o checklist manual (Issue #4)."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from evals.vision_checklist_eval import (
    DEFAULT_DATASET_PATH,
    compute_binary_confusion_and_kappa,
    evaluate_vision_checklist_concordance,
    interpret_kappa,
    main,
)


class TestVisionChecklistConcordance(unittest.TestCase):
    def test_dataset_structure_and_six_ergonomic_dimensions(self) -> None:
        raw = json.loads(DEFAULT_DATASET_PATH.read_text(encoding="utf-8"))
        categories = raw["categories"]
        photos = raw["labeled_photos"]

        self.assertEqual(len(categories), 6)
        self.assertGreaterEqual(len(photos), 10)

        for photo in photos:
            manual = photo["manual_checklist"]
            self.assertEqual(set(manual.keys()), set(categories))
            obs_cats = {
                o["category"] for o in photo["vision_agent_analysis"]["observations"]
            }
            self.assertEqual(obs_cats, set(categories))
            self.assertGreaterEqual(len(photo["vision_agent_analysis"]["limitations"]), 1)

    def test_concordance_metrics_and_cohens_kappa(self) -> None:
        report = evaluate_vision_checklist_concordance()
        g = report["global_metrics"]
        cal = report["confidence_calibration"]

        # Concordância global >= 90% e Kappa > 0.80 (quase perfeita)
        self.assertEqual(report["total_evaluated_items"], 72)
        self.assertGreaterEqual(g["agreement_rate"], 0.90)
        self.assertGreaterEqual(g["cohens_kappa"], 0.85)
        self.assertEqual(g["kappa_interpretation"], "quase_perfeita")
        self.assertGreaterEqual(g["f1"], 0.90)

        # Casos onde o agente divergiu devem ter menor confiança média e exigir confirmação (RF16)
        self.assertLess(
            cal["mean_confidence_discordant"], cal["mean_confidence_concordant"]
        )
        self.assertEqual(cal["discordant_flagged_requires_confirmation_rate"], 1.0)

    def test_perfect_and_chance_kappa_calculation(self) -> None:
        perfect = compute_binary_confusion_and_kappa(
            ["inadequado", "adequado", "inadequado", "adequado"],
            ["inadequado", "adequado", "inadequado", "adequado"],
        )
        self.assertEqual(perfect["agreement_rate"], 1.0)
        self.assertEqual(perfect["cohens_kappa"], 1.0)
        self.assertEqual(interpret_kappa(perfect["cohens_kappa"]), "quase_perfeita")

    def test_cli_saves_report_json(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            out_path = Path(tmpdir) / "vision_report.json"
            code = main(["--out", str(out_path)])
            self.assertEqual(code, 0)
            self.assertTrue(out_path.exists())
            saved = json.loads(out_path.read_text(encoding="utf-8"))
            self.assertEqual(
                saved["experiment_id"], "EXP-04-VISION-CHECKLIST-CONCORDANCE"
            )


if __name__ == "__main__":
    unittest.main()
