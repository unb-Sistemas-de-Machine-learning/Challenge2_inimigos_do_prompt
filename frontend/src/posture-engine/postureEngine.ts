/**
 * Motor Postural Determinístico (ErgoAI — TypeScript v1.1.0-post-mvp)
 *
 * Implementa:
 * - Validação empírica de limiares geométricos e latência <= 500 ms (RNF01, RNF07, Issue #13)
 * - Ponderação validada de proximidade TOO_CLOSE: 60% distância interocular + 40% largura dos ombros
 * - Evolução pós-MVP com 6 padrões geométricos + detecção de ausência prolongada:
 *   1. FORWARD_HEAD (Anteriorização da Cabeça)
 *   2. TOO_CLOSE (Aproximação Excessiva da Tela)
 *   3. SHOULDER_TILT (Inclinação Lateral dos Ombros)
 *   4. HEAD_TILT (Inclinação Lateral da Cabeça)
 *   5. ELEVATED_SHOULDERS (Ombros Elevados / Tensão de Trapézio)
 *   6. TRUNK_ROTATION (Rotação Axial de Tronco)
 *   + PROLONGED_ABSENCE (Ausência Prolongada do Posto / Pausa Automática)
 * - Múltiplos perfis de calibração independentes: 'notebook' vs. 'external_monitor'
 */

import type { DeviationType } from '../data/knowledgeCards';

export const PARAMETERS_VERSION = '1.1.0-post-mvp';

export type CalibrationProfileId = 'notebook' | 'external_monitor';

export interface CalibrationProfileConfig {
  id: CalibrationProfileId;
  label: string;
  description: string;
  thresholdMultipliers: Record<DeviationType, number>;
}

/**
 * Perfis ergonômicos pré-ajustados para a geometria da câmera:
 * - Notebook: câmera integrada próxima e abaixo da linha horizontal dos olhos (inclinação natural maior).
 * - Monitor Externo: webcam no topo do monitor ao nível dos olhos e distância visual maior (~60-75 cm).
 */
export const CALIBRATION_PROFILES: Record<CalibrationProfileId, CalibrationProfileConfig> = {
  notebook: {
    id: 'notebook',
    label: 'Notebook (Webcam Integrada)',
    description:
      'Ajustado para câmera integrada próxima (~45-55 cm) e ângulo de visão ligeiramente descendente.',
    thresholdMultipliers: {
      FORWARD_HEAD: 1.05,
      TOO_CLOSE: 1.0,
      SHOULDER_TILT: 1.0,
      HEAD_TILT: 1.0,
      ELEVATED_SHOULDERS: 1.0,
      TRUNK_ROTATION: 1.05,
    },
  },
  external_monitor: {
    id: 'external_monitor',
    label: 'Monitor Externo (Webcam de Topo)',
    description:
      'Ajustado para monitor externo na altura dos olhos (~60-75 cm) com maior rigor em alinhamento cervical e rotação.',
    thresholdMultipliers: {
      FORWARD_HEAD: 0.95,
      TOO_CLOSE: 0.95,
      SHOULDER_TILT: 0.95,
      HEAD_TILT: 0.95,
      ELEVATED_SHOULDERS: 0.95,
      TRUNK_ROTATION: 0.92,
    },
  },
};

export const POSE_INDEX = {
  NOSE: 0,
  LEFT_EYE: 2,
  RIGHT_EYE: 5,
  LEFT_EAR: 7,
  RIGHT_EAR: 8,
  LEFT_SHOULDER: 11,
  RIGHT_SHOULDER: 12,
} as const;

export const REFERENCE_LANDMARK_IDS = [
  POSE_INDEX.NOSE,
  POSE_INDEX.LEFT_EYE,
  POSE_INDEX.RIGHT_EYE,
  POSE_INDEX.LEFT_EAR,
  POSE_INDEX.RIGHT_EAR,
  POSE_INDEX.LEFT_SHOULDER,
  POSE_INDEX.RIGHT_SHOULDER,
] as const;

export interface ThresholdConfig {
  label: string;
  unit: string;
  thresholdOn: number;
  hysteresisRatio: number;
}

export const TOO_CLOSE_WEIGHTS = {
  eyeWeight: 0.6,
  shoulderWeight: 0.4,
} as const;

export const BASE_THRESHOLDS: Record<DeviationType, ThresholdConfig> = {
  FORWARD_HEAD: {
    label: 'Anteriorização / Camarão',
    unit: '%',
    thresholdOn: 18.0,
    hysteresisRatio: 0.78,
  },
  TOO_CLOSE: {
    label: 'Aproximação da Tela',
    unit: '%',
    thresholdOn: 18.0,
    hysteresisRatio: 0.78,
  },
  SHOULDER_TILT: {
    label: 'Inclinação dos Ombros',
    unit: '%',
    thresholdOn: 25.0,
    hysteresisRatio: 0.78,
  },
  HEAD_TILT: {
    label: 'Inclinação da Cabeça',
    unit: '°',
    thresholdOn: 14.0,
    hysteresisRatio: 0.78,
  },
  ELEVATED_SHOULDERS: {
    label: 'Ombros Elevados (Trapézio)',
    unit: '%',
    thresholdOn: 14.0,
    hysteresisRatio: 0.78,
  },
  TRUNK_ROTATION: {
    label: 'Rotação de Tronco',
    unit: '%',
    thresholdOn: 22.0,
    hysteresisRatio: 0.78,
  },
};

export const CONFIDENCE_LIMITS = {
  minAvgConfidence: 0.55,
  minLandmarkConfidence: 0.4,
  minShoulderWidth: 0.06,
  minEyeDist: 0.015,
};

export const DEFAULT_PROLONGED_ABSENCE_MS = 60_000;

export interface LandmarkPoint {
  x: number;
  y: number;
  z?: number;
  visibility?: number;
  presence?: number;
}

export interface PostureMetrics {
  neckHeightRatio: number;
  eyeDist: number;
  shoulderWidth: number;
  noseDepthDelta: number;
  shoulderAngleDeg: number;
  headAngleDeg: number;
  midShoulderY: number;
  noseY: number;
  shoulderDepthDiff: number;
}

export interface ExtractedFeatures {
  valid: boolean;
  userAbsent?: boolean;
  reason?: string;
  avgConfidence: number;
  minConfidence: number;
  metrics?: PostureMetrics;
  snapshotLandmarks?: Record<number, { x: number; y: number; z: number; visibility: number }>;
}

export interface CalibrationData {
  profileId?: CalibrationProfileId;
  createdAt: string;
  version: string;
  sampleCount: number;
  metrics: PostureMetrics;
  referenceLandmarks: Record<number, { x: number; y: number; z: number }>;
}

export type CalibrationProfilesMap = Partial<Record<CalibrationProfileId, CalibrationData>>;

interface DeviationState {
  activeAlert: boolean;
  aboveSinceMs: number | null;
  belowSinceMs: number | null;
  elapsedAboveMs: number;
  lastValue: number;
}

function distance2D(a: LandmarkPoint, b: LandmarkPoint): number {
  return Math.hypot(a.x - b.x, a.y - b.y);
}

function getVisibility(lm?: LandmarkPoint): number {
  if (!lm) return 0;
  if (typeof lm.visibility === 'number') return lm.visibility;
  if (typeof lm.presence === 'number') return lm.presence;
  return 1;
}

export function median(values: number[]): number {
  if (!values.length) return 0;
  const sorted = [...values].sort((a, b) => a - b);
  const mid = Math.floor(sorted.length / 2);
  return sorted.length % 2 === 0
    ? (sorted[mid - 1] + sorted[mid]) / 2
    : sorted[mid];
}

export function extractFeatures(landmarks?: LandmarkPoint[]): ExtractedFeatures {
  if (!landmarks || landmarks.length < 13) {
    return {
      valid: false,
      userAbsent: true,
      reason: 'Landmarks insuficientes detectados (usuário ausente do quadro).',
      avgConfidence: 0,
      minConfidence: 0,
    };
  }

  const requiredIds = [
    POSE_INDEX.NOSE,
    POSE_INDEX.LEFT_EYE,
    POSE_INDEX.RIGHT_EYE,
    POSE_INDEX.LEFT_SHOULDER,
    POSE_INDEX.RIGHT_SHOULDER,
  ];

  const confidences = requiredIds.map((id) => getVisibility(landmarks[id]));
  const avgConfidence = confidences.reduce((acc, v) => acc + v, 0) / confidences.length;
  const minConfidence = Math.min(...confidences);

  if (
    avgConfidence < CONFIDENCE_LIMITS.minAvgConfidence ||
    minConfidence < CONFIDENCE_LIMITS.minLandmarkConfidence
  ) {
    return {
      valid: false,
      userAbsent: avgConfidence < 0.2,
      reason: 'Confiança dos pontos abaixo do limite mínimo (RN05).',
      avgConfidence,
      minConfidence,
    };
  }

  const nose = landmarks[POSE_INDEX.NOSE];
  const leftEye = landmarks[POSE_INDEX.LEFT_EYE];
  const rightEye = landmarks[POSE_INDEX.RIGHT_EYE];
  const leftShoulder = landmarks[POSE_INDEX.LEFT_SHOULDER];
  const rightShoulder = landmarks[POSE_INDEX.RIGHT_SHOULDER];

  const shoulderWidth = distance2D(leftShoulder, rightShoulder);
  const eyeDist = distance2D(leftEye, rightEye);

  if (
    shoulderWidth < CONFIDENCE_LIMITS.minShoulderWidth ||
    eyeDist < CONFIDENCE_LIMITS.minEyeDist
  ) {
    return {
      valid: false,
      userAbsent: false,
      reason: 'Pessoa muito distante ou enquadramento incompleto.',
      avgConfidence,
      minConfidence,
    };
  }

  const midShoulderY = (leftShoulder.y + rightShoulder.y) / 2;
  const midShoulderZ = ((leftShoulder.z ?? 0) + (rightShoulder.z ?? 0)) / 2;

  const neckHeightRatio = (midShoulderY - nose.y) / shoulderWidth;
  const noseDepthDelta = midShoulderZ - (nose.z ?? 0);
  const shoulderDepthDiff = (leftShoulder.z ?? 0) - (rightShoulder.z ?? 0);

  const shoulderAngleDeg =
    Math.atan2(leftShoulder.y - rightShoulder.y, Math.abs(leftShoulder.x - rightShoulder.x)) *
    (180 / Math.PI);

  const headAngleDeg =
    Math.atan2(leftEye.y - rightEye.y, Math.abs(leftEye.x - rightEye.x)) * (180 / Math.PI);

  const snapshotLandmarks: Record<
    number,
    { x: number; y: number; z: number; visibility: number }
  > = {};

  for (const id of REFERENCE_LANDMARK_IDS) {
    const lm = landmarks[id];
    if (lm) {
      snapshotLandmarks[id] = {
        x: lm.x,
        y: lm.y,
        z: lm.z ?? 0,
        visibility: getVisibility(lm),
      };
    }
  }

  return {
    valid: true,
    userAbsent: false,
    avgConfidence,
    minConfidence,
    metrics: {
      neckHeightRatio,
      eyeDist,
      shoulderWidth,
      noseDepthDelta,
      shoulderAngleDeg,
      headAngleDeg,
      midShoulderY,
      noseY: nose.y,
      shoulderDepthDiff,
    },
    snapshotLandmarks,
  };
}

export class CalibrationCollector {
  private durationMs: number;
  private minSamples: number;
  private active = false;
  private startedAt = 0;
  private samples: ExtractedFeatures[] = [];
  private profileId: CalibrationProfileId = 'notebook';

  constructor(durationMs = 3000, minSamples = 10, profileId: CalibrationProfileId = 'notebook') {
    this.durationMs = durationMs;
    this.minSamples = minSamples;
    this.profileId = profileId;
  }

  setProfileId(profileId: CalibrationProfileId): void {
    this.profileId = profileId;
  }

  getProfileId(): CalibrationProfileId {
    return this.profileId;
  }

  start(nowMs = performance.now(), profileId?: CalibrationProfileId): void {
    if (profileId) this.profileId = profileId;
    this.active = true;
    this.startedAt = nowMs;
    this.samples = [];
  }

  cancel(): void {
    this.active = false;
    this.samples = [];
  }

  addSample(features: ExtractedFeatures, nowMs = performance.now()) {
    if (!this.active) {
      return { active: false, progress: 0, remainingMs: 0, done: false, sampleCount: 0 };
    }
    if (features.valid) {
      this.samples.push(features);
    }
    const elapsed = Math.max(0, nowMs - this.startedAt);
    return {
      active: true,
      progress: Math.min(1, elapsed / this.durationMs),
      remainingMs: Math.max(0, this.durationMs - elapsed),
      done: elapsed >= this.durationMs,
      sampleCount: this.samples.length,
    };
  }

  finalize(): { ok: true; calibration: CalibrationData } | { ok: false; reason: string } {
    this.active = false;
    if (this.samples.length < this.minSamples) {
      return {
        ok: false,
        reason: `Poucos quadros válidos capturados (${this.samples.length}/${this.minSamples}).`,
      };
    }

    const metricKeys: (keyof PostureMetrics)[] = [
      'neckHeightRatio',
      'eyeDist',
      'shoulderWidth',
      'noseDepthDelta',
      'shoulderAngleDeg',
      'headAngleDeg',
      'midShoulderY',
      'noseY',
      'shoulderDepthDiff',
    ];

    const referenceMetrics = {} as PostureMetrics;
    for (const key of metricKeys) {
      referenceMetrics[key] = median(this.samples.map((s) => s.metrics![key] ?? 0));
    }

    const referenceLandmarks: CalibrationData['referenceLandmarks'] = {};
    for (const id of REFERENCE_LANDMARK_IDS) {
      const xs: number[] = [];
      const ys: number[] = [];
      const zs: number[] = [];
      for (const sample of this.samples) {
        const lm = sample.snapshotLandmarks?.[id];
        if (lm) {
          xs.push(lm.x);
          ys.push(lm.y);
          zs.push(lm.z);
        }
      }
      if (xs.length > 0) {
        referenceLandmarks[id] = { x: median(xs), y: median(ys), z: median(zs) };
      }
    }

    return {
      ok: true,
      calibration: {
        profileId: this.profileId,
        createdAt: new Date().toISOString(),
        version: PARAMETERS_VERSION,
        sampleCount: this.samples.length,
        metrics: referenceMetrics,
        referenceLandmarks,
      },
    };
  }
}

export class PostureComparator {
  private emaAlpha: number;
  private persistenceMs: number;
  private recoveryMs: number;
  private toleranceFactor: number;
  private prolongedAbsenceMs: number;
  private profileId: CalibrationProfileId;
  private calibration: CalibrationData | null = null;
  private smoothedMetrics: PostureMetrics | null = null;
  private deviationStates: Record<DeviationType, DeviationState>;
  private absentSinceMs: number | null = null;
  private prolongedAbsenceDetected = false;

  constructor(options?: {
    emaAlpha?: number;
    persistenceMs?: number;
    recoveryMs?: number;
    toleranceFactor?: number;
    prolongedAbsenceMs?: number;
    profileId?: CalibrationProfileId;
  }) {
    this.emaAlpha = options?.emaAlpha ?? 0.28;
    this.persistenceMs = options?.persistenceMs ?? 4000;
    this.recoveryMs = options?.recoveryMs ?? 1200;
    this.toleranceFactor = options?.toleranceFactor ?? 1.0;
    this.prolongedAbsenceMs = options?.prolongedAbsenceMs ?? DEFAULT_PROLONGED_ABSENCE_MS;
    this.profileId = options?.profileId ?? 'notebook';
    this.deviationStates = this.createInitialStates();
  }

  private createInitialStates(): Record<DeviationType, DeviationState> {
    return {
      FORWARD_HEAD: { activeAlert: false, aboveSinceMs: null, belowSinceMs: null, elapsedAboveMs: 0, lastValue: 0 },
      TOO_CLOSE: { activeAlert: false, aboveSinceMs: null, belowSinceMs: null, elapsedAboveMs: 0, lastValue: 0 },
      SHOULDER_TILT: { activeAlert: false, aboveSinceMs: null, belowSinceMs: null, elapsedAboveMs: 0, lastValue: 0 },
      HEAD_TILT: { activeAlert: false, aboveSinceMs: null, belowSinceMs: null, elapsedAboveMs: 0, lastValue: 0 },
      ELEVATED_SHOULDERS: { activeAlert: false, aboveSinceMs: null, belowSinceMs: null, elapsedAboveMs: 0, lastValue: 0 },
      TRUNK_ROTATION: { activeAlert: false, aboveSinceMs: null, belowSinceMs: null, elapsedAboveMs: 0, lastValue: 0 },
    };
  }

  setProfileId(profileId: CalibrationProfileId): void {
    this.profileId = profileId;
  }

  getProfileId(): CalibrationProfileId {
    return this.profileId;
  }

  setCalibration(calibration: CalibrationData | null): void {
    this.calibration = calibration;
    if (calibration?.profileId) {
      this.profileId = calibration.profileId;
    }
    this.smoothedMetrics = null;
    this.absentSinceMs = null;
    this.prolongedAbsenceDetected = false;
    this.deviationStates = this.createInitialStates();
  }

  setToleranceFactor(factor: number): void {
    this.toleranceFactor = Math.max(0.75, Math.min(1.6, Number(factor.toFixed(2))));
  }

  applyFeedback(classification: 'falso_alerta' | 'util'): number {
    if (classification === 'falso_alerta') {
      this.setToleranceFactor(this.toleranceFactor + 0.1);
    } else {
      this.setToleranceFactor(this.toleranceFactor - 0.03);
    }
    return this.toleranceFactor;
  }

  evaluate(features: ExtractedFeatures, nowMs = performance.now()) {
    const evalStartMs = performance.now();

    if (!this.calibration) {
      return {
        status: 'UNCALIBRATED' as const,
        valid: false,
        activeAlerts: [] as DeviationType[],
        prolongedAbsence: false,
        absenceDurationMs: 0,
        profileId: this.profileId,
        evaluationLatencyMs: Number((performance.now() - evalStartMs).toFixed(4)),
      };
    }

    if (!features.valid || !features.metrics) {
      if (features.userAbsent) {
        if (this.absentSinceMs === null) {
          this.absentSinceMs = nowMs;
        }
        const absenceDurationMs = Math.max(0, nowMs - this.absentSinceMs);
        if (absenceDurationMs >= this.prolongedAbsenceMs) {
          this.prolongedAbsenceDetected = true;
          // Ao detectar ausência prolongada (pausa física fora da cadeira), limpa alertas ativos
          this.deviationStates = this.createInitialStates();
        }
        return {
          status: this.prolongedAbsenceDetected
            ? ('PROLONGED_ABSENCE' as const)
            : ('LOW_CONFIDENCE' as const),
          valid: false,
          activeAlerts: [] as DeviationType[],
          prolongedAbsence: this.prolongedAbsenceDetected,
          absenceDurationMs,
          profileId: this.profileId,
          evaluationLatencyMs: Number((performance.now() - evalStartMs).toFixed(4)),
        };
      }

      return {
        status: 'LOW_CONFIDENCE' as const,
        valid: false,
        activeAlerts: (Object.keys(this.deviationStates) as DeviationType[]).filter(
          (k) => this.deviationStates[k].activeAlert
        ),
        prolongedAbsence: false,
        absenceDurationMs: 0,
        profileId: this.profileId,
        evaluationLatencyMs: Number((performance.now() - evalStartMs).toFixed(4)),
      };
    }

    // Usuário presente com confiança válida -> zera cronômetro de ausência
    this.absentSinceMs = null;
    this.prolongedAbsenceDetected = false;

    const raw = features.metrics;
    if (!this.smoothedMetrics) {
      this.smoothedMetrics = { ...raw };
    } else {
      for (const key of Object.keys(raw) as (keyof PostureMetrics)[]) {
        const curVal = raw[key] ?? 0;
        const prevVal = this.smoothedMetrics[key] ?? curVal;
        this.smoothedMetrics[key] =
          this.emaAlpha * curVal + (1 - this.emaAlpha) * prevVal;
      }
    }

    const ref = this.calibration.metrics;
    const cur = this.smoothedMetrics;
    const refShoulderWidth = Math.max(ref.shoulderWidth, 0.06);

    // 1. Anteriorização da cabeça (queda da altura cervical + avanço Z do nariz)
    const neckBase = Math.max(ref.neckHeightRatio, 0.15);
    const neckDropPct = ((ref.neckHeightRatio - cur.neckHeightRatio) / neckBase) * 100;
    const depthCuePct = Math.max(0, (cur.noseDepthDelta - ref.noseDepthDelta) * 25);

    // 2. Ombros elevados (trapézio contraído): linha média dos ombros sobe (Y diminui)
    // enquanto a cabeça permanece estável (sem queda significativa do nariz)
    const refMidShoulderY = ref.midShoulderY ?? 0.6;
    const curMidShoulderY = cur.midShoulderY ?? refMidShoulderY;
    const refNoseY = ref.noseY ?? 0.4;
    const curNoseY = cur.noseY ?? refNoseY;

    const shoulderRiseNorm = ((refMidShoulderY - curMidShoulderY) / refShoulderWidth) * 100;
    const noseDropNorm = Math.max(0, ((curNoseY - refNoseY) / refShoulderWidth) * 100);
    const elevatedShouldersValue = Math.max(0, shoulderRiseNorm - 0.85 * noseDropNorm);

    // Quando o encurtamento cervical decorre da elevação isolada dos ombros (sem avanço Z nem queda da cabeça),
    // desconta a subida dos ombros para evitar falso positivo cruzado em FORWARD_HEAD
    const forwardHeadAdjustedDrop =
      elevatedShouldersValue > 8 && depthCuePct < 2.5 && noseDropNorm < 3.0
        ? Math.max(0, neckDropPct - shoulderRiseNorm * 0.9)
        : neckDropPct;
    const forwardHeadValue = Math.max(0, forwardHeadAdjustedDrop + depthCuePct);

    // 3. Aproximação excessiva da tela (60% distância interocular + 40% largura dos ombros)
    const eyeScale = cur.eyeDist / Math.max(ref.eyeDist, 0.015);
    const shoulderScale = cur.shoulderWidth / refShoulderWidth;
    const combinedProximityScale =
      TOO_CLOSE_WEIGHTS.eyeWeight * eyeScale +
      TOO_CLOSE_WEIGHTS.shoulderWeight * shoulderScale;
    const tooCloseValue = Math.max(0, (combinedProximityScale - 1) * 100);

    // 4. Inclinação lateral dos ombros e da cabeça
    const shoulderAngleDeltaRad =
      (Math.abs(cur.shoulderAngleDeg - ref.shoulderAngleDeg) * Math.PI) / 180;
    const shoulderTiltPct = Math.abs(Math.tan(shoulderAngleDeltaRad)) * 100;
    const headTiltValue = Math.abs(cur.headAngleDeg - ref.headAngleDeg);

    // 5. Rotação axial de tronco: assimetria de profundidade Z entre ombros + estreitamento projetivo 2D
    const refDepthDiff = ref.shoulderDepthDiff ?? 0;
    const curDepthDiff = cur.shoulderDepthDiff ?? 0;
    const depthRotationPct =
      (Math.abs(curDepthDiff - refDepthDiff) / refShoulderWidth) * 100;
    const widthForeshorteningPct = Math.max(0, (1 - shoulderScale) * 100);
    const trunkRotationValue = Math.max(
      0,
      0.7 * depthRotationPct + 0.3 * widthForeshorteningPct
    );

    const measuredValues: Record<DeviationType, number> = {
      FORWARD_HEAD: forwardHeadValue,
      TOO_CLOSE: tooCloseValue,
      SHOULDER_TILT: shoulderTiltPct,
      HEAD_TILT: headTiltValue,
      ELEVATED_SHOULDERS: elevatedShouldersValue,
      TRUNK_ROTATION: trunkRotationValue,
    };

    const ratios: Record<DeviationType, number> = {
      FORWARD_HEAD: 0,
      TOO_CLOSE: 0,
      SHOULDER_TILT: 0,
      HEAD_TILT: 0,
      ELEVATED_SHOULDERS: 0,
      TRUNK_ROTATION: 0,
    };

    const profileMultipliers =
      CALIBRATION_PROFILES[this.profileId]?.thresholdMultipliers ??
      CALIBRATION_PROFILES.notebook.thresholdMultipliers;

    const activeAlerts: DeviationType[] = [];
    for (const type of Object.keys(BASE_THRESHOLDS) as DeviationType[]) {
      const cfg = BASE_THRESHOLDS[type];
      const value = measuredValues[type];
      const profileMult = profileMultipliers[type] ?? 1.0;
      const thresholdOn = cfg.thresholdOn * this.toleranceFactor * profileMult;
      const thresholdOff = thresholdOn * cfg.hysteresisRatio;
      ratios[type] = value / thresholdOn;
      const state = this.deviationStates[type];
      state.lastValue = value;

      if (!state.activeAlert) {
        if (value >= thresholdOn) {
          if (state.aboveSinceMs === null) state.aboveSinceMs = nowMs;
          state.elapsedAboveMs = nowMs - state.aboveSinceMs;
          if (state.elapsedAboveMs >= this.persistenceMs) {
            state.activeAlert = true;
            state.belowSinceMs = null;
          }
        } else if (value < thresholdOff) {
          state.aboveSinceMs = null;
          state.elapsedAboveMs = 0;
        }
      } else {
        if (value <= thresholdOff) {
          if (state.belowSinceMs === null) state.belowSinceMs = nowMs;
          if (nowMs - state.belowSinceMs >= this.recoveryMs) {
            state.activeAlert = false;
            state.aboveSinceMs = null;
            state.belowSinceMs = null;
            state.elapsedAboveMs = 0;
          }
        } else {
          state.belowSinceMs = null;
        }
      }

      if (state.activeAlert) activeAlerts.push(type);
    }

    // Prioriza o desvio com maior proporção acima do limite
    activeAlerts.sort((a, b) => ratios[b] - ratios[a]);

    return {
      status: activeAlerts.length > 0 ? ('ALERT_PERSISTENT' as const) : ('ADEQUATE' as const),
      valid: true,
      avgConfidence: features.avgConfidence,
      activeAlerts,
      measuredValues,
      ratios,
      toleranceFactor: this.toleranceFactor,
      profileId: this.profileId,
      prolongedAbsence: false,
      absenceDurationMs: 0,
      evaluationLatencyMs: Number((performance.now() - evalStartMs).toFixed(4)),
    };
  }
}
