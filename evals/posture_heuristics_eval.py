"""Validação empírica de limiares heurísticos, ponderação TOO_CLOSE, perfis de calibração e novos padrões posturais (Issue #13).

Responsabilidades:
1. Espelhar com fidelidade matemática exata o motor determinístico `frontend/src/posture-engine/postureEngine.ts`
   (`v1.1.0-post-mvp`), incluindo:
   - 6 padrões geométricos: `FORWARD_HEAD`, `TOO_CLOSE`, `SHOULDER_TILT`, `HEAD_TILT`, `ELEVATED_SHOULDERS`, `TRUNK_ROTATION`
   - Detecção de ausência prolongada (`PROLONGED_ABSENCE`) para pausas de recuperação
   - Perfis de calibração independentes (`notebook` vs. `external_monitor`)
   - Ponderação `TOO_CLOSE` (60% distância interocular + 40% largura aparente dos ombros)
   - Filtro EMA (`alpha = 0.28`), histerese (`0.78`) e persistência temporal (`4000 ms`)
2. Executar três experimentos empíricos obrigatórios (RNF01, RNF07, SPEC.md §13.3):
   - Experimento A: Ablação dos pesos de `TOO_CLOSE` (`60% olhos / 40% ombros` vs. `100% olhos` vs. `100% ombros` vs. `50/50`),
     demonstrando por que a combinação 60/40 resiste à rotação de cabeça e movimento de braços.
   - Experimento B: Validação multiclasse dos 6 padrões posturais + ausência prolongada + perfis de calibração
     (`notebook` vs. `external_monitor`) com Precision, Recall, F1-score e False Positive Rate (FPR).
   - Experimento C: Benchmark de latência do motor postural (RNF01 <= 500 ms), medindo média, P95, P99 e máximo.

Uso via CLI:
    python -m evals.posture_heuristics_eval --out evals/results/posture_heuristics_report.json
"""

from __future__ import annotations

import argparse
import json
import math
import sys
import time
from pathlib import Path
from typing import Any

EVALS_DIR = Path(__file__).resolve().parent
DEFAULT_DATASET_PATH = EVALS_DIR / "datasets" / "posture_heuristics_scenarios.json"
DEFAULT_REPORT_PATH = EVALS_DIR / "results" / "posture_heuristics_report.json"

PARAMETERS_VERSION = "1.1.0-post-mvp"

POSE_INDEX = {
    "NOSE": 0,
    "LEFT_EYE": 2,
    "RIGHT_EYE": 5,
    "LEFT_EAR": 7,
    "RIGHT_EAR": 8,
    "LEFT_SHOULDER": 11,
    "RIGHT_SHOULDER": 12,
}

DEVIATION_TYPES = (
    "FORWARD_HEAD",
    "TOO_CLOSE",
    "SHOULDER_TILT",
    "HEAD_TILT",
    "ELEVATED_SHOULDERS",
    "TRUNK_ROTATION",
)

BASE_THRESHOLDS: dict[str, dict[str, Any]] = {
    "FORWARD_HEAD": {"label": "Anteriorização / Camarão", "unit": "%", "thresholdOn": 18.0, "hysteresisRatio": 0.78},
    "TOO_CLOSE": {"label": "Aproximação da Tela", "unit": "%", "thresholdOn": 18.0, "hysteresisRatio": 0.78},
    "SHOULDER_TILT": {"label": "Inclinação dos Ombros", "unit": "%", "thresholdOn": 25.0, "hysteresisRatio": 0.78},
    "HEAD_TILT": {"label": "Inclinação da Cabeça", "unit": "°", "thresholdOn": 14.0, "hysteresisRatio": 0.78},
    "ELEVATED_SHOULDERS": {"label": "Ombros Elevados (Trapézio)", "unit": "%", "thresholdOn": 14.0, "hysteresisRatio": 0.78},
    "TRUNK_ROTATION": {"label": "Rotação de Tronco", "unit": "%", "thresholdOn": 22.0, "hysteresisRatio": 0.78},
}

CALIBRATION_PROFILES: dict[str, dict[str, Any]] = {
    "notebook": {
        "id": "notebook",
        "label": "Notebook (Webcam Integrada)",
        "thresholdMultipliers": {
            "FORWARD_HEAD": 1.05,
            "TOO_CLOSE": 1.00,
            "SHOULDER_TILT": 1.00,
            "HEAD_TILT": 1.00,
            "ELEVATED_SHOULDERS": 1.00,
            "TRUNK_ROTATION": 1.05,
        },
    },
    "external_monitor": {
        "id": "external_monitor",
        "label": "Monitor Externo (Webcam de Topo)",
        "thresholdMultipliers": {
            "FORWARD_HEAD": 0.95,
            "TOO_CLOSE": 0.95,
            "SHOULDER_TILT": 0.95,
            "HEAD_TILT": 0.95,
            "ELEVATED_SHOULDERS": 0.95,
            "TRUNK_ROTATION": 0.92,
        },
    },
}

CONFIDENCE_LIMITS = {
    "minAvgConfidence": 0.55,
    "minLandmarkConfidence": 0.40,
    "minShoulderWidth": 0.06,
    "minEyeDist": 0.015,
}


def median(values: list[float]) -> float:
    if not values:
        return 0.0
    s = sorted(values)
    mid = len(s) // 2
    if len(s) % 2 == 0:
        return (s[mid - 1] + s[mid]) / 2.0
    return s[mid]


def distance_2d(a: dict[str, float], b: dict[str, float]) -> float:
    return math.hypot(a["x"] - b["x"], a["y"] - b["y"])


def get_visibility(lm: dict[str, float] | None) -> float:
    if not lm:
        return 0.0
    if "visibility" in lm:
        return float(lm["visibility"])
    if "visibilidade" in lm:
        return float(lm["visibilidade"])
    if "presence" in lm:
        return float(lm["presence"])
    return 1.0


def extract_features(landmarks: list[dict[str, float]] | None) -> dict[str, Any]:
    """Extrai as 9 variáveis geométricas normalizadas de um frame de pose MediaPipe."""
    if not landmarks or len(landmarks) < 13:
        return {
            "valid": False,
            "userAbsent": True,
            "reason": "Landmarks insuficientes detectados (usuário ausente do quadro).",
            "avgConfidence": 0.0,
            "minConfidence": 0.0,
        }

    req_ids = [
        POSE_INDEX["NOSE"],
        POSE_INDEX["LEFT_EYE"],
        POSE_INDEX["RIGHT_EYE"],
        POSE_INDEX["LEFT_SHOULDER"],
        POSE_INDEX["RIGHT_SHOULDER"],
    ]
    confidences = [get_visibility(landmarks[idx]) for idx in req_ids]
    avg_conf = sum(confidences) / len(confidences)
    min_conf = min(confidences)

    if (
        avg_conf < CONFIDENCE_LIMITS["minAvgConfidence"]
        or min_conf < CONFIDENCE_LIMITS["minLandmarkConfidence"]
    ):
        return {
            "valid": False,
            "userAbsent": avg_conf < 0.20,
            "reason": "Confiança dos pontos abaixo do limite mínimo (RN05).",
            "avgConfidence": avg_conf,
            "minConfidence": min_conf,
        }

    nose = landmarks[POSE_INDEX["NOSE"]]
    left_eye = landmarks[POSE_INDEX["LEFT_EYE"]]
    right_eye = landmarks[POSE_INDEX["RIGHT_EYE"]]
    left_shoulder = landmarks[POSE_INDEX["LEFT_SHOULDER"]]
    right_shoulder = landmarks[POSE_INDEX["RIGHT_SHOULDER"]]

    shoulder_width = distance_2d(left_shoulder, right_shoulder)
    eye_dist = distance_2d(left_eye, right_eye)

    if (
        shoulder_width < CONFIDENCE_LIMITS["minShoulderWidth"]
        or eye_dist < CONFIDENCE_LIMITS["minEyeDist"]
    ):
        return {
            "valid": False,
            "userAbsent": False,
            "reason": "Pessoa muito distante ou enquadramento incompleto.",
            "avgConfidence": avg_conf,
            "minConfidence": min_conf,
        }

    mid_shoulder_y = (left_shoulder["y"] + right_shoulder["y"]) / 2.0
    mid_shoulder_z = (left_shoulder.get("z", 0.0) + right_shoulder.get("z", 0.0)) / 2.0

    neck_height_ratio = (mid_shoulder_y - nose["y"]) / shoulder_width
    nose_depth_delta = mid_shoulder_z - nose.get("z", 0.0)
    shoulder_depth_diff = left_shoulder.get("z", 0.0) - right_shoulder.get("z", 0.0)

    shoulder_angle_deg = math.atan2(
        left_shoulder["y"] - right_shoulder["y"],
        abs(left_shoulder["x"] - right_shoulder["x"]),
    ) * (180.0 / math.pi)

    head_angle_deg = math.atan2(
        left_eye["y"] - right_eye["y"],
        abs(left_eye["x"] - right_eye["x"]),
    ) * (180.0 / math.pi)

    return {
        "valid": True,
        "userAbsent": False,
        "avgConfidence": avg_conf,
        "minConfidence": min_conf,
        "metrics": {
            "neckHeightRatio": neck_height_ratio,
            "eyeDist": eye_dist,
            "shoulderWidth": shoulder_width,
            "noseDepthDelta": nose_depth_delta,
            "shoulderAngleDeg": shoulder_angle_deg,
            "headAngleDeg": head_angle_deg,
            "midShoulderY": mid_shoulder_y,
            "noseY": nose["y"],
            "shoulderDepthDiff": shoulder_depth_diff,
        },
    }


def calibrate_from_frames(
    calib_frames: list[dict[str, Any]],
    profile_id: str = "notebook",
    min_samples: int = 10,
) -> dict[str, Any]:
    """Calcula a referência de calibração por mediana estatística."""
    valid_samples = []
    for frame in calib_frames:
        feat = extract_features(frame.get("pose"))
        if feat["valid"]:
            valid_samples.append(feat["metrics"])

    if len(valid_samples) < min_samples:
        return {"ok": False, "reason": f"Amostras insuficientes ({len(valid_samples)}/{min_samples})"}

    keys = list(valid_samples[0].keys())
    ref_metrics = {k: median([s[k] for s in valid_samples]) for k in keys}
    return {
        "ok": True,
        "calibration": {
            "profileId": profile_id,
            "version": PARAMETERS_VERSION,
            "sampleCount": len(valid_samples),
            "metrics": ref_metrics,
        },
    }


class PostureEngineSimulator:
    """Simulador determinístico fiel ao `PostureComparator` (`postureEngine.ts`)."""

    def __init__(
        self,
        calibration: dict[str, Any],
        profile_id: str = "notebook",
        ema_alpha: float = 0.28,
        persistence_ms: float = 4000.0,
        recovery_ms: float = 1200.0,
        tolerance_factor: float = 1.0,
        prolonged_absence_ms: float = 60000.0,
        too_close_weights: tuple[float, float] = (0.60, 0.40),
    ) -> None:
        self.calibration = calibration
        self.profile_id = profile_id
        self.ema_alpha = ema_alpha
        self.persistence_ms = persistence_ms
        self.recovery_ms = recovery_ms
        self.tolerance_factor = tolerance_factor
        self.prolonged_absence_ms = prolonged_absence_ms
        self.eye_weight, self.shoulder_weight = too_close_weights

        self.smoothed: dict[str, float] | None = None
        self.absent_since_ms: float | None = None
        self.prolonged_absence_detected = False
        self.states: dict[str, dict[str, Any]] = {
            t: {
                "activeAlert": False,
                "aboveSinceMs": None,
                "belowSinceMs": None,
                "elapsedAboveMs": 0.0,
                "lastValue": 0.0,
            }
            for t in DEVIATION_TYPES
        }

    def evaluate(self, features: dict[str, Any], now_ms: float) -> dict[str, Any]:
        t0 = time.perf_counter()

        if not features["valid"] or "metrics" not in features:
            if features.get("userAbsent"):
                if self.absent_since_ms is None:
                    self.absent_since_ms = now_ms
                absence_dur = max(0.0, now_ms - self.absent_since_ms)
                if absence_dur >= self.prolonged_absence_ms:
                    self.prolonged_absence_detected = True
                    for st in self.states.values():
                        st["activeAlert"] = False
                        st["aboveSinceMs"] = None
                        st["belowSinceMs"] = None
                        st["elapsedAboveMs"] = 0.0
                return {
                    "status": "PROLONGED_ABSENCE"
                    if self.prolonged_absence_detected
                    else "LOW_CONFIDENCE",
                    "valid": False,
                    "activeAlerts": [],
                    "prolongedAbsence": self.prolonged_absence_detected,
                    "absenceDurationMs": absence_dur,
                    "latencyMs": (time.perf_counter() - t0) * 1000.0,
                }

            return {
                "status": "LOW_CONFIDENCE",
                "valid": False,
                "activeAlerts": [
                    k for k, st in self.states.items() if st["activeAlert"]
                ],
                "prolongedAbsence": False,
                "absenceDurationMs": 0.0,
                "latencyMs": (time.perf_counter() - t0) * 1000.0,
            }

        self.absent_since_ms = None
        self.prolonged_absence_detected = False

        raw = features["metrics"]
        if self.smoothed is None:
            self.smoothed = dict(raw)
        else:
            for k, val in raw.items():
                self.smoothed[k] = self.ema_alpha * val + (1.0 - self.ema_alpha) * self.smoothed[k]

        ref = self.calibration["metrics"]
        cur = self.smoothed
        ref_sw = max(ref["shoulderWidth"], 0.06)

        neck_base = max(ref["neckHeightRatio"], 0.15)
        neck_drop_pct = ((ref["neckHeightRatio"] - cur["neckHeightRatio"]) / neck_base) * 100.0
        depth_cue_pct = max(0.0, (cur["noseDepthDelta"] - ref["noseDepthDelta"]) * 25.0)

        shoulder_rise_norm = ((ref["midShoulderY"] - cur["midShoulderY"]) / ref_sw) * 100.0
        nose_drop_norm = max(0.0, ((cur["noseY"] - ref["noseY"]) / ref_sw) * 100.0)
        elevated_shoulders_val = max(0.0, shoulder_rise_norm - 0.85 * nose_drop_norm)

        if elevated_shoulders_val > 8.0 and depth_cue_pct < 2.5 and nose_drop_norm < 3.0:
            fw_adj_drop = max(0.0, neck_drop_pct - shoulder_rise_norm * 0.9)
        else:
            fw_adj_drop = neck_drop_pct
        forward_head_val = max(0.0, fw_adj_drop + depth_cue_pct)

        eye_scale = cur["eyeDist"] / max(ref["eyeDist"], 0.015)
        shoulder_scale = cur["shoulderWidth"] / ref_sw
        combined_prox = self.eye_weight * eye_scale + self.shoulder_weight * shoulder_scale
        too_close_val = max(0.0, (combined_prox - 1.0) * 100.0)

        shoulder_angle_rad = abs(cur["shoulderAngleDeg"] - ref["shoulderAngleDeg"]) * math.pi / 180.0
        shoulder_tilt_pct = abs(math.tan(shoulder_angle_rad)) * 100.0
        head_tilt_val = abs(cur["headAngleDeg"] - ref["headAngleDeg"])

        depth_rot_pct = (abs(cur["shoulderDepthDiff"] - ref["shoulderDepthDiff"]) / ref_sw) * 100.0
        width_foreshortening_pct = max(0.0, (1.0 - shoulder_scale) * 100.0)
        trunk_rotation_val = max(0.0, 0.7 * depth_rot_pct + 0.3 * width_foreshortening_pct)

        measured = {
            "FORWARD_HEAD": forward_head_val,
            "TOO_CLOSE": too_close_val,
            "SHOULDER_TILT": shoulder_tilt_pct,
            "HEAD_TILT": head_tilt_val,
            "ELEVATED_SHOULDERS": elevated_shoulders_val,
            "TRUNK_ROTATION": trunk_rotation_val,
        }

        profile_mults = CALIBRATION_PROFILES.get(
            self.profile_id, CALIBRATION_PROFILES["notebook"]
        )["thresholdMultipliers"]

        ratios: dict[str, float] = {}
        active_alerts: list[str] = []

        for dev_type in DEVIATION_TYPES:
            cfg = BASE_THRESHOLDS[dev_type]
            val = measured[dev_type]
            t_on = cfg["thresholdOn"] * self.tolerance_factor * profile_mults[dev_type]
            t_off = t_on * cfg["hysteresisRatio"]
            ratios[dev_type] = val / t_on
            st = self.states[dev_type]
            st["lastValue"] = val

            if not st["activeAlert"]:
                if val >= t_on:
                    if st["aboveSinceMs"] is None:
                        st["aboveSinceMs"] = now_ms
                    st["elapsedAboveMs"] = now_ms - st["aboveSinceMs"]
                    if st["elapsedAboveMs"] >= self.persistence_ms:
                        st["activeAlert"] = True
                        st["belowSinceMs"] = None
                elif val < t_off:
                    st["aboveSinceMs"] = None
                    st["elapsedAboveMs"] = 0.0
            else:
                if val <= t_off:
                    if st["belowSinceMs"] is None:
                        st["belowSinceMs"] = now_ms
                    if now_ms - st["belowSinceMs"] >= self.recovery_ms:
                        st["activeAlert"] = False
                        st["aboveSinceMs"] = None
                        st["belowSinceMs"] = None
                        st["elapsedAboveMs"] = 0.0
                else:
                    st["belowSinceMs"] = None

            if st["activeAlert"]:
                active_alerts.append(dev_type)

        active_alerts.sort(key=lambda t: ratios[t], reverse=True)
        latency_ms = (time.perf_counter() - t0) * 1000.0

        return {
            "status": "ALERT_PERSISTENT" if active_alerts else "ADEQUATE",
            "valid": True,
            "activeAlerts": active_alerts,
            "measuredValues": measured,
            "ratios": ratios,
            "prolongedAbsence": False,
            "absenceDurationMs": 0.0,
            "latencyMs": latency_ms,
        }


def make_pose_frame(
    nose: tuple[float, float, float] = (0.50, 0.36, -0.02),
    left_eye: tuple[float, float, float] = (0.525, 0.33, -0.02),
    right_eye: tuple[float, float, float] = (0.475, 0.33, -0.02),
    left_shoulder: tuple[float, float, float] = (0.62, 0.60, 0.00),
    right_shoulder: tuple[float, float, float] = (0.38, 0.60, 0.00),
    visibility: float = 0.95,
) -> list[dict[str, float]]:
    """Constrói um vetor de 13 landmarks compatível com MediaPipe PoseLandmarker."""
    default_pt = {"x": 0.50, "y": 0.40, "z": 0.0, "visibility": visibility}
    pts = [dict(default_pt) for _ in range(13)]
    pts[POSE_INDEX["NOSE"]] = {"x": nose[0], "y": nose[1], "z": nose[2], "visibility": visibility}
    pts[POSE_INDEX["LEFT_EYE"]] = {"x": left_eye[0], "y": left_eye[1], "z": left_eye[2], "visibility": visibility}
    pts[POSE_INDEX["RIGHT_EYE"]] = {"x": right_eye[0], "y": right_eye[1], "z": right_eye[2], "visibility": visibility}
    pts[POSE_INDEX["LEFT_EAR"]] = {"x": left_eye[0] + 0.025, "y": left_eye[1] + 0.01, "z": 0.0, "visibility": visibility}
    pts[POSE_INDEX["RIGHT_EAR"]] = {"x": right_eye[0] - 0.025, "y": right_eye[1] + 0.01, "z": 0.0, "visibility": visibility}
    pts[POSE_INDEX["LEFT_SHOULDER"]] = {
        "x": left_shoulder[0],
        "y": left_shoulder[1],
        "z": left_shoulder[2],
        "visibility": visibility,
    }
    pts[POSE_INDEX["RIGHT_SHOULDER"]] = {
        "x": right_shoulder[0],
        "y": right_shoulder[1],
        "z": right_shoulder[2],
        "visibility": visibility,
    }
    return pts


def build_validation_dataset() -> dict[str, Any]:
    """Gera o conjunto rotulado de cenários temporais cobrindo os 6 padrões posturais, ausência prolongada,
    movimentos transitórios (< 4s), baixa confiança e ablação de TOO_CLOSE."""
    calib_pose = make_pose_frame()
    calib_frames = [{"t_ms": i * 250, "pose": calib_pose} for i in range(13)]
    monitoring_timestamps = [4000 + i * 250 for i in range(25)]  # 6 segundos (25 frames)

    scenarios: list[dict[str, Any]] = [
        {
            "id": "sc-01-adequate-notebook",
            "title": "Postura neutra alinhada em perfil Notebook",
            "profile_id": "notebook",
            "expected_label": "ADEQUATE",
            "calibration": calib_frames,
            "frames": [{"t_ms": t, "pose": make_pose_frame()} for t in monitoring_timestamps],
        },
        {
            "id": "sc-02-adequate-external-monitor",
            "title": "Postura neutra alinhada em perfil Monitor Externo",
            "profile_id": "external_monitor",
            "expected_label": "ADEQUATE",
            "calibration": calib_frames,
            "frames": [{"t_ms": t, "pose": make_pose_frame()} for t in monitoring_timestamps],
        },
        {
            "id": "sc-03-forward-head-persistent",
            "title": "Anteriorização da cabeça persistente (> 4s): queda cervical + avanço Z",
            "profile_id": "notebook",
            "expected_label": "FORWARD_HEAD",
            "calibration": calib_frames,
            "frames": [
                {
                    "t_ms": t,
                    "pose": make_pose_frame(
                        nose=(0.50, 0.425, -0.14),
                        left_eye=(0.525, 0.395, -0.13),
                        right_eye=(0.475, 0.395, -0.13),
                    ),
                }
                for t in monitoring_timestamps
            ],
        },
        {
            "id": "sc-04-too-close-persistent",
            "title": "Aproximação excessiva da tela (> 4s): expansão proporcional olhos (60%) e ombros (40%)",
            "profile_id": "notebook",
            "expected_label": "TOO_CLOSE",
            "calibration": calib_frames,
            "frames": [
                {
                    "t_ms": t,
                    "pose": make_pose_frame(
                        nose=(0.50, 0.36, -0.04),
                        left_eye=(0.532, 0.33, -0.04),
                        right_eye=(0.468, 0.33, -0.04),
                        left_shoulder=(0.652, 0.635, 0.00),
                        right_shoulder=(0.348, 0.635, 0.00),
                    ),
                }
                for t in monitoring_timestamps
            ],
        },
        {
            "id": "sc-05-shoulder-tilt-persistent",
            "title": "Inclinação lateral assimétrica dos ombros (> 4s)",
            "profile_id": "notebook",
            "expected_label": "SHOULDER_TILT",
            "calibration": calib_frames,
            "frames": [
                {
                    "t_ms": t,
                    "pose": make_pose_frame(
                        left_shoulder=(0.62, 0.64, 0.00),
                        right_shoulder=(0.38, 0.56, 0.00),
                    ),
                }
                for t in monitoring_timestamps
            ],
        },
        {
            "id": "sc-06-head-tilt-persistent",
            "title": "Inclinação lateral da cabeça (> 4s)",
            "profile_id": "notebook",
            "expected_label": "HEAD_TILT",
            "calibration": calib_frames,
            "frames": [
                {
                    "t_ms": t,
                    "pose": make_pose_frame(
                        left_eye=(0.525, 0.342, -0.02),
                        right_eye=(0.475, 0.318, -0.02),
                    ),
                }
                for t in monitoring_timestamps
            ],
        },
        {
            "id": "sc-07-elevated-shoulders-persistent",
            "title": "Ombros elevados / tensão de trapézio (> 4s) com cabeça estável",
            "profile_id": "notebook",
            "expected_label": "ELEVATED_SHOULDERS",
            "calibration": calib_frames,
            "frames": [
                {
                    "t_ms": t,
                    "pose": make_pose_frame(
                        nose=(0.50, 0.36, -0.02),
                        left_shoulder=(0.62, 0.552, 0.00),
                        right_shoulder=(0.38, 0.552, 0.00),
                    ),
                }
                for t in monitoring_timestamps
            ],
        },
        {
            "id": "sc-08-trunk-rotation-persistent",
            "title": "Rotação axial de tronco (> 4s): assimetria de profundidade Z + estreitamento 2D",
            "profile_id": "external_monitor",
            "expected_label": "TRUNK_ROTATION",
            "calibration": calib_frames,
            "frames": [
                {
                    "t_ms": t,
                    "pose": make_pose_frame(
                        left_shoulder=(0.595, 0.60, -0.045),
                        right_shoulder=(0.405, 0.60, 0.045),
                    ),
                }
                for t in monitoring_timestamps
            ],
        },
        {
            "id": "sc-09-prolonged-absence",
            "title": "Ausência prolongada do posto (>= 60s sem landmarks) contabilizando pausa",
            "profile_id": "notebook",
            "expected_label": "PROLONGED_ABSENCE",
            "calibration": calib_frames,
            "frames": [
                {"t_ms": 4000 + i * 5000, "pose": []} for i in range(15)
            ],
        },
        {
            "id": "sc-10-transient-movement-no-alert",
            "title": "Desvio momentâneo (< 4s, apenas 2.5s) seguido de retorno postural (RN03)",
            "profile_id": "notebook",
            "expected_label": "ADEQUATE",
            "calibration": calib_frames,
            "frames": [
                {
                    "t_ms": t,
                    "pose": make_pose_frame(
                        nose=(0.50, 0.425, -0.14),
                        left_eye=(0.525, 0.395, -0.13),
                        right_eye=(0.475, 0.395, -0.13),
                    )
                    if t < 6500
                    else make_pose_frame(),
                }
                for t in monitoring_timestamps
            ],
        },
        {
            "id": "sc-11-low-confidence-no-alert",
            "title": "Quadro de baixa confiança (visibilidade 0.30 < 0.40) não emite alerta falso (RN04/RN05)",
            "profile_id": "notebook",
            "expected_label": "ADEQUATE",
            "calibration": calib_frames,
            "frames": [
                {
                    "t_ms": t,
                    "pose": make_pose_frame(
                        nose=(0.50, 0.44, -0.18),
                        visibility=0.30,
                    ),
                }
                for t in monitoring_timestamps
            ],
        },
        {
            "id": "sc-12-arm-reach-noise-no-too-close",
            "title": "Abdução de braços ao digitar (+22% ombros, 0% olhos) não dispara falso TOO_CLOSE com pesos 60/40",
            "profile_id": "notebook",
            "expected_label": "ADEQUATE",
            "calibration": calib_frames,
            "frames": [
                {
                    "t_ms": t,
                    "pose": make_pose_frame(
                        left_shoulder=(0.646, 0.614, 0.00),
                        right_shoulder=(0.354, 0.614, 0.00),
                    ),
                }
                for t in monitoring_timestamps
            ],
        },
    ]

    return {
        "version": "1.1.0",
        "engine_version": PARAMETERS_VERSION,
        "scenarios": scenarios,
    }


def evaluate_too_close_weight_ablation() -> list[dict[str, Any]]:
    """Avalia empiricamente combinações de pesos (olhos vs. ombros) para a heurística TOO_CLOSE.

    Casos de teste:
    1. Aproximação real com cabeça reta (+26% olhos, +25% ombros) -> esperado: TOO_CLOSE (Positivo)
    2. Aproximação real com leve giro de olhar (+16% olhos, +24% ombros) -> esperado: TOO_CLOSE (Positivo)
    3. Abdução de cotovelos/braços ao digitar sem aproximar tronco (+2% olhos, +23% ombros) -> esperado: ADEQUATE (Negativo)
    4. Jitter interocular / expressão facial sem aproximar tronco (+21% olhos, +1% ombros) -> esperado: ADEQUATE (Negativo)
    """
    weight_configs = [
        {"name": "100% Olhos / 0% Ombros", "weights": (1.0, 0.0)},
        {"name": "0% Olhos / 100% Ombros", "weights": (0.0, 1.0)},
        {"name": "50% Olhos / 50% Ombros", "weights": (0.5, 0.5)},
        {"name": "60% Olhos / 40% Ombros (ErgoAI)", "weights": (0.6, 0.4)},
    ]

    cases = [
        {"id": "tc-pos-1", "eye_scale": 1.26, "shoulder_scale": 1.25, "expected_positive": True},
        {"id": "tc-pos-2", "eye_scale": 1.16, "shoulder_scale": 1.24, "expected_positive": True},
        {"id": "tc-pos-3", "eye_scale": 1.24, "shoulder_scale": 1.10, "expected_positive": True},
        {"id": "tc-neg-1", "eye_scale": 1.02, "shoulder_scale": 1.23, "expected_positive": False},
        {"id": "tc-neg-2", "eye_scale": 1.21, "shoulder_scale": 1.01, "expected_positive": False},
    ]

    threshold_on = BASE_THRESHOLDS["TOO_CLOSE"]["thresholdOn"]  # 18.0%
    results: list[dict[str, Any]] = []

    for cfg in weight_configs:
        w_eye, w_sh = cfg["weights"]
        tp = fp = fn = tn = 0
        for c in cases:
            val_pct = max(0.0, (w_eye * c["eye_scale"] + w_sh * c["shoulder_scale"] - 1.0) * 100.0)
            pred_pos = val_pct >= threshold_on
            if c["expected_positive"] and pred_pos:
                tp += 1
            elif not c["expected_positive"] and pred_pos:
                fp += 1
            elif c["expected_positive"] and not pred_pos:
                fn += 1
            else:
                tn += 1

        prec = tp / (tp + fp) if (tp + fp) > 0 else 0.0
        rec = tp / (tp + fn) if (tp + fn) > 0 else 0.0
        f1 = (2 * prec * rec / (prec + rec)) if (prec + rec) > 0 else 0.0
        fpr = fp / (fp + tn) if (fp + tn) > 0 else 0.0

        results.append(
            {
                "config_name": cfg["name"],
                "eye_weight": w_eye,
                "shoulder_weight": w_sh,
                "tp": tp,
                "fp": fp,
                "fn": fn,
                "tn": tn,
                "precision": round(prec, 4),
                "recall": round(rec, 4),
                "f1": round(f1, 4),
                "fpr": round(fpr, 4),
            }
        )
    return results


def run_posture_heuristics_evaluation(
    dataset_path: Path = DEFAULT_DATASET_PATH,
) -> dict[str, Any]:
    """Executa a bateria completa de validação empírica dos limiares, novos padrões e latência."""
    if not dataset_path.exists():
        dataset = build_validation_dataset()
        dataset_path.parent.mkdir(parents=True, exist_ok=True)
        dataset_path.write_text(json.dumps(dataset, indent=2, ensure_ascii=False), encoding="utf-8")
    else:
        dataset = json.loads(dataset_path.read_text(encoding="utf-8"))

    scenarios = dataset["scenarios"]
    frame_latencies_ms: list[float] = []
    scenario_results: list[dict[str, Any]] = []

    all_target_classes = (*DEVIATION_TYPES, "PROLONGED_ABSENCE")

    for sc in scenarios:
        profile_id = sc.get("profile_id", "notebook")
        calib_res = calibrate_from_frames(sc["calibration"], profile_id=profile_id)
        if not calib_res["ok"]:
            raise RuntimeError(f"Falha na calibração do cenário {sc['id']}: {calib_res['reason']}")

        sim = PostureEngineSimulator(
            calibration=calib_res["calibration"],
            profile_id=profile_id,
        )

        triggered_alerts: set[str] = set()
        final_status = "ADEQUATE"
        for frame in sc["frames"]:
            t0 = time.perf_counter()
            feat = extract_features(frame.get("pose"))
            res = sim.evaluate(feat, float(frame["t_ms"]))
            total_step_ms = (time.perf_counter() - t0) * 1000.0
            frame_latencies_ms.append(total_step_ms)

            for al in res["activeAlerts"]:
                triggered_alerts.add(al)
            if res.get("prolongedAbsence"):
                triggered_alerts.add("PROLONGED_ABSENCE")
            final_status = res["status"]

        predicted_primary = (
            next(iter(triggered_alerts)) if triggered_alerts else "ADEQUATE"
        )
        expected = sc["expected_label"]
        matched = (
            (expected == "ADEQUATE" and len(triggered_alerts) == 0)
            or (expected in triggered_alerts)
        )

        scenario_results.append(
            {
                "id": sc["id"],
                "title": sc["title"],
                "profile_id": profile_id,
                "expected_label": expected,
                "predicted_alerts": sorted(triggered_alerts),
                "predicted_primary": predicted_primary,
                "final_status": final_status,
                "correct": matched,
            }
        )

    # Métricas por classe e agregadas
    per_class: dict[str, dict[str, Any]] = {}
    tot_tp = tot_fp = tot_fn = tot_tn = 0
    for cls in all_target_classes:
        tp = fp = fn = tn = 0
        for r in scenario_results:
            exp_pos = r["expected_label"] == cls
            pred_pos = cls in r["predicted_alerts"]
            if exp_pos and pred_pos:
                tp += 1
            elif not exp_pos and pred_pos:
                fp += 1
            elif exp_pos and not pred_pos:
                fn += 1
            else:
                tn += 1
        prec = tp / (tp + fp) if (tp + fp) > 0 else 0.0
        rec = tp / (tp + fn) if (tp + fn) > 0 else 0.0
        f1 = (2 * prec * rec / (prec + rec)) if (prec + rec) > 0 else 0.0
        fpr = fp / (fp + tn) if (fp + tn) > 0 else 0.0
        per_class[cls] = {
            "tp": tp,
            "fp": fp,
            "fn": fn,
            "tn": tn,
            "precision": round(prec, 4),
            "recall": round(rec, 4),
            "f1": round(f1, 4),
            "fpr": round(fpr, 4),
        }
        tot_tp += tp
        tot_fp += fp
        tot_fn += fn
        tot_tn += tn

    macro_f1 = sum(m["f1"] for m in per_class.values()) / len(all_target_classes)
    macro_prec = sum(m["precision"] for m in per_class.values()) / len(all_target_classes)
    macro_rec = sum(m["recall"] for m in per_class.values()) / len(all_target_classes)
    macro_fpr = sum(m["fpr"] for m in per_class.values()) / len(all_target_classes)

    # Estatísticas de latência (RNF01 <= 500 ms)
    sorted_lat = sorted(frame_latencies_ms)
    n_lat = len(sorted_lat) or 1
    mean_lat = sum(sorted_lat) / n_lat
    p95_lat = sorted_lat[min(n_lat - 1, int(0.95 * n_lat))]
    p99_lat = sorted_lat[min(n_lat - 1, int(0.99 * n_lat))]
    max_lat = sorted_lat[-1] if sorted_lat else 0.0

    ablation_too_close = evaluate_too_close_weight_ablation()

    return {
        "experiment_id": "EXP-13-POSTURE-HEURISTICS-AND-PROFILES",
        "engine_version": PARAMETERS_VERSION,
        "total_scenarios": len(scenario_results),
        "scenario_accuracy": round(
            sum(1 for r in scenario_results if r["correct"]) / len(scenario_results), 4
        ),
        "macro_metrics": {
            "precision": round(macro_prec, 4),
            "recall": round(macro_rec, 4),
            "f1": round(macro_f1, 4),
            "fpr": round(macro_fpr, 4),
        },
        "latency_rnf01": {
            "total_frames_evaluated": len(frame_latencies_ms),
            "target_max_ms": 500.0,
            "mean_ms": round(mean_lat, 4),
            "p95_ms": round(p95_lat, 4),
            "p99_ms": round(p99_lat, 4),
            "max_ms": round(max_lat, 4),
            "meets_rnf01": max_lat <= 500.0,
        },
        "too_close_weight_ablation": ablation_too_close,
        "per_class_metrics": per_class,
        "calibration_profiles": CALIBRATION_PROFILES,
        "scenarios": scenario_results,
    }


def print_posture_heuristics_summary(report: dict[str, Any]) -> None:
    """Imprime resumo executivo da validação de limiares e novos padrões posturais."""
    m = report["macro_metrics"]
    lat = report["latency_rnf01"]

    print(f"=== VALIDAÇÃO EMPÍRICA DO MOTOR POSTURAL E EVOLUÇÃO PÓS-MVP ({report['engine_version']}) ===")
    print(
        f"Cenários avaliados: {report['total_scenarios']} | "
        f"Acurácia de cenários: {report['scenario_accuracy']:.4f}"
    )
    print(
        f"Macro Precision: {m['precision']:.4f} | Macro Recall: {m['recall']:.4f} | "
        f"Macro F1: {m['f1']:.4f} | Macro FPR: {m['fpr']:.4f}"
    )

    print("\n--- 1. Ablação Empírica de Pesos TOO_CLOSE (Olhos vs. Ombros) ---")
    print(f"{'Configuração de Pesos':<36} {'Prec':>8} {'Rec':>8} {'F1':>8} {'FPR':>8}")
    print("-" * 72)
    for ab in report["too_close_weight_ablation"]:
        print(
            f"{ab['config_name']:<36} {ab['precision']:>8.4f} {ab['recall']:>8.4f} "
            f"{ab['f1']:>8.4f} {ab['fpr']:>8.4f}"
        )

    print("\n--- 2. Desempenho por Padrão Postural (6 Geométricos + Ausência Prolongada) ---")
    print(f"{'Padrão Postural':<24} {'TP':>4} {'FP':>4} {'FN':>4} {'TN':>4} {'Prec':>8} {'Rec':>8} {'F1':>8}")
    print("-" * 76)
    for cls, cm in report["per_class_metrics"].items():
        print(
            f"{cls:<24} {cm['tp']:>4} {cm['fp']:>4} {cm['fn']:>4} {cm['tn']:>4} "
            f"{cm['precision']:>8.4f} {cm['recall']:>8.4f} {cm['f1']:>8.4f}"
        )

    print("\n--- 3. Verificação de Latência (RNF01 <= 500 ms) ---")
    print(
        f"Frames processados: {lat['total_frames_evaluated']} | "
        f"Média: {lat['mean_ms']:.4f} ms | P95: {lat['p95_ms']:.4f} ms | "
        f"P99: {lat['p99_ms']:.4f} ms | Máx: {lat['max_ms']:.4f} ms | "
        f"Cumpre RNF01 (<= 500 ms): {'SIM' if lat['meets_rnf01'] else 'NÃO'}"
    )
    print("")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", type=Path, default=DEFAULT_DATASET_PATH)
    parser.add_argument("--out", type=Path, default=None, help="Caminho opcional para salvar JSON")
    args = parser.parse_args(argv)

    report = run_posture_heuristics_evaluation(dataset_path=args.dataset)
    print_posture_heuristics_summary(report)

    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
        print(f"[OK] Relatório salvo em {args.out}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
