/**
 * Motor Postural Determinístico (ErgoAI — MVP)
 *
 * Responsável por:
 * - Validar confiança dos landmarks (RN04, RN05)
 * - Extrair variáveis geométricas normalizadas (RF05, RF06)
 * - Calibrar referência individual por mediana estatística (RF04, RN02)
 * - Comparar postura atual vs. ideal com EMA + histerese + persistência temporal (RF07, RNF06, RN03)
 * - Ajustar tolerância local por feedback sem depender de LLM (RF11, RN09, RN10)
 */

export const PARAMETERS_VERSION = '1.0.0-mvp';

export const POSE_INDEX = {
  NOSE: 0,
  LEFT_EYE: 2,
  RIGHT_EYE: 5,
  LEFT_EAR: 7,
  RIGHT_EAR: 8,
  LEFT_SHOULDER: 11,
  RIGHT_SHOULDER: 12,
};

export const REFERENCE_LANDMARK_IDS = [
  POSE_INDEX.NOSE,
  POSE_INDEX.LEFT_EYE,
  POSE_INDEX.RIGHT_EYE,
  POSE_INDEX.LEFT_EAR,
  POSE_INDEX.RIGHT_EAR,
  POSE_INDEX.LEFT_SHOULDER,
  POSE_INDEX.RIGHT_SHOULDER,
];

export const BASE_THRESHOLDS = {
  FORWARD_HEAD: {
    label: 'Anteriorização / Camarão',
    unit: '%',
    thresholdOn: 16.0,
    hysteresisRatio: 0.78,
  },
  TOO_CLOSE: {
    label: 'Aproximação da Tela',
    unit: '%',
    thresholdOn: 20.0,
    hysteresisRatio: 0.78,
  },
  SHOULDER_TILT: {
    label: 'Inclinação dos Ombros',
    unit: '°',
    thresholdOn: 7.5,
    hysteresisRatio: 0.78,
  },
  HEAD_TILT: {
    label: 'Inclinação da Cabeça',
    unit: '°',
    thresholdOn: 10.0,
    hysteresisRatio: 0.78,
  },
};

export const CONFIDENCE_LIMITS = {
  minAvgConfidence: 0.55,
  minLandmarkConfidence: 0.4,
  minShoulderWidth: 0.06,
  minEyeDist: 0.015,
};

function distance2D(a, b) {
  return Math.hypot(a.x - b.x, a.y - b.y);
}

function getVisibility(lm) {
  if (!lm) return 0;
  if (typeof lm.visibility === 'number') return lm.visibility;
  if (typeof lm.presence === 'number') return lm.presence;
  return 1;
}

export function median(values) {
  if (!values || values.length === 0) return 0;
  const sorted = [...values].sort((a, b) => a - b);
  const mid = Math.floor(sorted.length / 2);
  if (sorted.length % 2 === 0) {
    return (sorted[mid - 1] + sorted[mid]) / 2;
  }
  return sorted[mid];
}

/**
 * Extrai métricas geométricas normalizadas de um frame de pose MediaPipe.
 */
export function extractFeatures(landmarks) {
  if (!landmarks || landmarks.length < 13) {
    return {
      valid: false,
      reason: 'Landmarks insuficientes detectados.',
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
      reason: 'Pessoa muito distante ou enquadramento incompleto.',
      avgConfidence,
      minConfidence,
    };
  }

  const midShoulderY = (leftShoulder.y + rightShoulder.y) / 2;
  const midShoulderZ = ((leftShoulder.z ?? 0) + (rightShoulder.z ?? 0)) / 2;

  // Altura relativa cabeça-ombros normalizada pela largura dos ombros
  const neckHeightRatio = (midShoulderY - nose.y) / shoulderWidth;

  // Profundidade relativa nariz-ombros (em MediaPipe, Z negativo fica mais próximo da câmera)
  const noseDepthDelta = midShoulderZ - (nose.z ?? 0);

  // Ângulos laterais em graus (0° = horizontal perfeito)
  const shoulderAngleDeg =
    Math.atan2(leftShoulder.y - rightShoulder.y, Math.abs(leftShoulder.x - rightShoulder.x)) *
    (180 / Math.PI);

  const headAngleDeg =
    Math.atan2(leftEye.y - rightEye.y, Math.abs(leftEye.x - rightEye.x)) * (180 / Math.PI);

  const snapshotLandmarks = {};
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
    avgConfidence,
    minConfidence,
    metrics: {
      neckHeightRatio,
      eyeDist,
      shoulderWidth,
      noseDepthDelta,
      shoulderAngleDeg,
      headAngleDeg,
    },
    snapshotLandmarks,
  };
}

/**
 * Coletor de amostras para calibração inicial da postura ideal (RF04, RN02).
 */
export class CalibrationCollector {
  constructor(durationMs = 3000, minSamples = 10) {
    this.durationMs = durationMs;
    this.minSamples = minSamples;
    this.active = false;
    this.startedAt = 0;
    this.samples = [];
  }

  start(nowMs = performance.now()) {
    this.active = true;
    this.startedAt = nowMs;
    this.samples = [];
  }

  cancel() {
    this.active = false;
    this.samples = [];
  }

  addSample(features, nowMs = performance.now()) {
    if (!this.active) {
      return { active: false, progress: 0, remainingMs: 0, done: false, sampleCount: 0 };
    }

    if (features && features.valid) {
      this.samples.push(features);
    }

    const elapsed = Math.max(0, nowMs - this.startedAt);
    const progress = Math.min(1, elapsed / this.durationMs);
    const remainingMs = Math.max(0, this.durationMs - elapsed);
    const done = elapsed >= this.durationMs;

    return {
      active: true,
      progress,
      remainingMs,
      done,
      sampleCount: this.samples.length,
    };
  }

  finalize() {
    this.active = false;
    if (this.samples.length < this.minSamples) {
      return {
        ok: false,
        reason: `Poucos quadros válidos capturados (${this.samples.length}/${this.minSamples}). Mantenha rosto e ombros visíveis.`,
      };
    }

    const metricKeys = [
      'neckHeightRatio',
      'eyeDist',
      'shoulderWidth',
      'noseDepthDelta',
      'shoulderAngleDeg',
      'headAngleDeg',
    ];

    const referenceMetrics = {};
    for (const key of metricKeys) {
      referenceMetrics[key] = median(this.samples.map((s) => s.metrics[key]));
    }

    const referenceLandmarks = {};
    for (const id of REFERENCE_LANDMARK_IDS) {
      const xs = [];
      const ys = [];
      const zs = [];
      for (const sample of this.samples) {
        const lm = sample.snapshotLandmarks[id];
        if (lm) {
          xs.push(lm.x);
          ys.push(lm.y);
          zs.push(lm.z);
        }
      }
      if (xs.length > 0) {
        referenceLandmarks[id] = {
          x: median(xs),
          y: median(ys),
          z: median(zs),
        };
      }
    }

    return {
      ok: true,
      calibration: {
        createdAt: new Date().toISOString(),
        version: PARAMETERS_VERSION,
        sampleCount: this.samples.length,
        metrics: referenceMetrics,
        referenceLandmarks,
      },
    };
  }
}

/**
 * Comparador em tempo real da postura atual vs. ideal calibrada.
 */
export class PostureComparator {
  constructor(options = {}) {
    this.emaAlpha = options.emaAlpha ?? 0.28;
    this.persistenceMs = options.persistenceMs ?? 4000;
    this.recoveryMs = options.recoveryMs ?? 1200;
    this.toleranceFactor = options.toleranceFactor ?? 1.0;
    this.calibration = null;
    this.smoothedMetrics = null;
    this.deviationStates = this.#createInitialStates();
  }

  #createInitialStates() {
    const states = {};
    for (const key of Object.keys(BASE_THRESHOLDS)) {
      states[key] = {
        activeAlert: false,
        aboveSinceMs: null,
        belowSinceMs: null,
        elapsedAboveMs: 0,
        lastValue: 0,
      };
    }
    return states;
  }

  setCalibration(calibration) {
    this.calibration = calibration;
    this.smoothedMetrics = null;
    this.deviationStates = this.#createInitialStates();
  }

  setPersistenceMs(ms) {
    this.persistenceMs = Math.max(1500, Math.min(15000, ms));
  }

  setToleranceFactor(factor) {
    // Limite seguro (RN09): permite tolerância entre 0.75x e 1.60x
    this.toleranceFactor = Math.max(0.75, Math.min(1.6, Number(factor.toFixed(2))));
  }

  applyFeedback(classification) {
    if (classification === 'falso_alerta') {
      this.setToleranceFactor(this.toleranceFactor + 0.1);
    } else if (classification === 'util') {
      this.setToleranceFactor(this.toleranceFactor - 0.03);
    }
    return this.toleranceFactor;
  }

  resetStates() {
    this.smoothedMetrics = null;
    this.deviationStates = this.#createInitialStates();
  }

  evaluate(features, nowMs = performance.now()) {
    if (!this.calibration) {
      return {
        status: 'UNCALIBRATED',
        valid: false,
        reason: 'Calibração inicial pendente.',
        deviations: {},
        activeAlerts: [],
        newlyTriggered: [],
        newlyResolved: [],
        persistenceProgress: 0,
        toleranceFactor: this.toleranceFactor,
      };
    }

    if (!features || !features.valid) {
      return {
        status: 'LOW_CONFIDENCE',
        valid: false,
        reason: features?.reason || 'Confiança insuficiente.',
        avgConfidence: features?.avgConfidence ?? 0,
        minConfidence: features?.minConfidence ?? 0,
        deviations: {},
        activeAlerts: Object.keys(this.deviationStates).filter(
          (k) => this.deviationStates[k].activeAlert
        ),
        newlyTriggered: [],
        newlyResolved: [],
        persistenceProgress: 0,
        toleranceFactor: this.toleranceFactor,
      };
    }

    // 1. Suavização EMA nos sinais geométricos
    const raw = features.metrics;
    if (!this.smoothedMetrics) {
      this.smoothedMetrics = { ...raw };
    } else {
      for (const key of Object.keys(raw)) {
        this.smoothedMetrics[key] =
          this.emaAlpha * raw[key] + (1 - this.emaAlpha) * this.smoothedMetrics[key];
      }
    }

    const ref = this.calibration.metrics;
    const cur = this.smoothedMetrics;

    // 2. Cálculo dos desvios relativos à referência calibrada
    const neckBase = Math.max(ref.neckHeightRatio, 0.15);
    const neckDropPct = ((ref.neckHeightRatio - cur.neckHeightRatio) / neckBase) * 100;
    const depthCuePct = Math.max(0, (cur.noseDepthDelta - ref.noseDepthDelta) * 25);
    const forwardHeadValue = Math.max(0, neckDropPct + depthCuePct);

    const eyeScale = cur.eyeDist / Math.max(ref.eyeDist, 0.015);
    const shoulderScale = cur.shoulderWidth / Math.max(ref.shoulderWidth, 0.06);
    const combinedProximityScale = 0.6 * eyeScale + 0.4 * shoulderScale;
    const tooCloseValue = Math.max(0, (combinedProximityScale - 1) * 100);

    const shoulderTiltValue = Math.abs(cur.shoulderAngleDeg - ref.shoulderAngleDeg);
    const headTiltValue = Math.abs(cur.headAngleDeg - ref.headAngleDeg);

    const measuredValues = {
      FORWARD_HEAD: forwardHeadValue,
      TOO_CLOSE: tooCloseValue,
      SHOULDER_TILT: shoulderTiltValue,
      HEAD_TILT: headTiltValue,
    };

    // 3. Máquina de estados com histerese e persistência temporal (RF07, RN03)
    const deviations = {};
    const activeAlerts = [];
    const newlyTriggered = [];
    const newlyResolved = [];
    let maxPersistenceProgress = 0;
    let primaryWarning = null;

    for (const [type, cfg] of Object.entries(BASE_THRESHOLDS)) {
      const value = measuredValues[type];
      const thresholdOn = cfg.thresholdOn * this.toleranceFactor;
      const thresholdOff = thresholdOn * cfg.hysteresisRatio;
      const state = this.deviationStates[type];
      state.lastValue = value;

      if (!state.activeAlert) {
        if (value >= thresholdOn) {
          if (state.aboveSinceMs === null) {
            state.aboveSinceMs = nowMs;
          }
          state.elapsedAboveMs = nowMs - state.aboveSinceMs;
          const progress = Math.min(1, state.elapsedAboveMs / this.persistenceMs);
          if (progress > maxPersistenceProgress) {
            maxPersistenceProgress = progress;
            primaryWarning = type;
          }

          if (state.elapsedAboveMs >= this.persistenceMs) {
            state.activeAlert = true;
            state.belowSinceMs = null;
            newlyTriggered.push({
              type,
              value,
              thresholdOn,
              confidence: features.avgConfidence,
            });
          }
        } else if (value < thresholdOff) {
          // Abaixo da banda de histerese -> zera o acumulador
          state.aboveSinceMs = null;
          state.elapsedAboveMs = 0;
        } else if (state.aboveSinceMs !== null) {
          // Dentro da banda de histerese (entre thresholdOff e thresholdOn): mantém progresso
          state.elapsedAboveMs = nowMs - state.aboveSinceMs;
          const progress = Math.min(1, state.elapsedAboveMs / this.persistenceMs);
          if (progress > maxPersistenceProgress) {
            maxPersistenceProgress = progress;
            primaryWarning = type;
          }
        }
      } else {
        // Alerta já ativo: exige retorno abaixo de thresholdOff por recoveryMs para encerrar
        if (value <= thresholdOff) {
          if (state.belowSinceMs === null) {
            state.belowSinceMs = nowMs;
          }
          if (nowMs - state.belowSinceMs >= this.recoveryMs) {
            state.activeAlert = false;
            state.aboveSinceMs = null;
            state.belowSinceMs = null;
            state.elapsedAboveMs = 0;
            newlyResolved.push({ type });
          }
        } else {
          state.belowSinceMs = null;
        }
      }

      if (state.activeAlert) {
        activeAlerts.push(type);
      }

      deviations[type] = {
        type,
        label: cfg.label,
        unit: cfg.unit,
        value,
        thresholdOn,
        thresholdOff,
        ratioToThreshold: value / thresholdOn,
        activeAlert: state.activeAlert,
        elapsedAboveMs: state.elapsedAboveMs,
        inWarningBand: !state.activeAlert && state.aboveSinceMs !== null,
      };
    }

    // Ordena alertas ativos pelo maior desvio relativo
    activeAlerts.sort(
      (a, b) => deviations[b].ratioToThreshold - deviations[a].ratioToThreshold
    );

    let status = 'ADEQUATE';
    if (activeAlerts.length > 0) {
      status = 'ALERT_PERSISTENT';
      maxPersistenceProgress = 1;
    } else if (maxPersistenceProgress > 0) {
      status = 'WARNING_TRANSIENT';
    }

    return {
      status,
      valid: true,
      avgConfidence: features.avgConfidence,
      minConfidence: features.minConfidence,
      smoothedMetrics: { ...cur },
      referenceMetrics: { ...ref },
      deviations,
      activeAlerts,
      primaryDeviation: activeAlerts[0] || primaryWarning || null,
      newlyTriggered,
      newlyResolved,
      persistenceProgress: maxPersistenceProgress,
      persistenceMs: this.persistenceMs,
      toleranceFactor: this.toleranceFactor,
    };
  }
}
