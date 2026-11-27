"""Testes automatizados para validação de limiares, novos padrões posturais e perfis de calibração (Issue #13)."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from evals.posture_heuristics_eval import (
    CALIBRATION_PROFILES,
    DEVIATION_TYPES,
    PostureEngineSimulator,
    calibrate_from_frames,
    evaluate_too_close_weight_ablation,
    extract_features,
    main,
    make_pose_frame,
    run_posture_heuristics_evaluation,
)


class TestPostureHeuristicsAndEvolution(unittest.TestCase):
    def test_six_geometric_patterns_and_profiles_exist(self) -> None:
        self.assertEqual(
            set(DEVIATION_TYPES),
            {
                "FORWARD_HEAD",
                "TOO_CLOSE",
                "SHOULDER_TILT",
                "HEAD_TILT",
                "ELEVATED_SHOULDERS",
                "TRUNK_ROTATION",
            },
        )
        self.assertIn("notebook", CALIBRATION_PROFILES)
        self.assertIn("external_monitor", CALIBRATION_PROFILES)

    def test_too_close_60_40_weights_outperform_single_feature_baselines(self) -> None:
        ablation = evaluate_too_close_weight_ablation()
        by_name = {item["config_name"]: item for item in ablation}
        ergoai_60_40 = by_name["60% Olhos / 40% Ombros (ErgoAI)"]
        only_eyes = by_name["100% Olhos / 0% Ombros"]
        only_shoulders = by_name["0% Olhos / 100% Ombros"]
        equal_50_50 = by_name["50% Olhos / 50% Ombros"]

        self.assertEqual(ergoai_60_40["f1"], 1.0)
        self.assertEqual(ergoai_60_40["fpr"], 0.0)
        self.assertGreater(ergoai_60_40["f1"], only_eyes["f1"])
        self.assertGreater(ergoai_60_40["f1"], only_shoulders["f1"])
        self.assertGreater(ergoai_60_40["f1"], equal_50_50["f1"])

    def test_all_posture_scenarios_and_rnf01_latency_budget(self) -> None:
        report = run_posture_heuristics_evaluation(dataset_path=None)

        self.assertEqual(report["scenario_accuracy"], 1.0)
        self.assertEqual(report["macro_metrics"]["f1"], 1.0)
        self.assertEqual(report["macro_metrics"]["fpr"], 0.0)

        lat = report["latency_rnf01"]
        self.assertTrue(lat["meets_rnf01"])
        self.assertLess(lat["p99_ms"], 50.0)
        self.assertLess(lat["max_ms"], 500.0)

    def test_farther_from_camera_does_not_trigger_false_trunk_rotation(self) -> None:
        calib_frames = [{"t_ms": i * 250, "pose": make_pose_frame()} for i in range(12)]
        cal_ext = calibrate_from_frames(calib_frames, profile_id="external_monitor")["calibration"]
        sim_ext = PostureEngineSimulator(cal_ext, profile_id="external_monitor")

        # Usuário recua em linha reta (olhos e ombros diminuem 18% na mesma proporção, sem delta Z)
        far_pose = make_pose_frame(
            left_eye=(0.5205, 0.33, -0.02),
            right_eye=(0.4795, 0.33, -0.02),
            left_shoulder=(0.5984, 0.60, 0.00),
            right_shoulder=(0.4016, 0.60, 0.00),
        )
        for step in range(25):
            res = sim_ext.evaluate(extract_features(far_pose), 4000.0 + step * 250.0)
        self.assertNotIn("TRUNK_ROTATION", res["activeAlerts"])
        self.assertEqual(res["measuredValues"]["TRUNK_ROTATION"], 0.0)

    def test_calibration_profiles_sensitivity_difference(self) -> None:
        calib_frames = [{"t_ms": i * 250, "pose": make_pose_frame()} for i in range(12)]
        cal_nb = calibrate_from_frames(calib_frames, profile_id="notebook")["calibration"]
        cal_ext = calibrate_from_frames(calib_frames, profile_id="external_monitor")["calibration"]

        sim_nb = PostureEngineSimulator(cal_nb, profile_id="notebook")
        sim_ext = PostureEngineSimulator(cal_ext, profile_id="external_monitor")

        # Desvio moderado de rotação de tronco (entre o limiar de monitor externo 20.24% e notebook 23.1%)
        borderline_pose = make_pose_frame(
            left_shoulder=(0.602, 0.60, -0.032),
            right_shoulder=(0.398, 0.60, 0.032),
        )
        feat = extract_features(borderline_pose)
        res_nb = sim_nb.evaluate(feat, 5000.0)
        res_ext = sim_ext.evaluate(feat, 5000.0)

        self.assertGreater(
            res_ext["ratios"]["TRUNK_ROTATION"],
            res_nb["ratios"]["TRUNK_ROTATION"],
        )

    def test_cli_generates_report_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            ds_path = Path(tmpdir) / "scenarios.json"
            out_path = Path(tmpdir) / "report.json"
            exit_code = main(["--dataset", str(ds_path), "--out", str(out_path)])
            self.assertEqual(exit_code, 0)
            self.assertTrue(out_path.exists())


if __name__ == "__main__":
    unittest.main()
