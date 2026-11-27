import { describe, expect, it } from 'vitest';
import {
  BASE_THRESHOLDS,
  CALIBRATION_PROFILES,
  CalibrationCollector,
  PARAMETERS_VERSION,
  POSE_INDEX,
  PostureComparator,
  TOO_CLOSE_WEIGHTS,
  extractFeatures,
  type LandmarkPoint,
} from './postureEngine';

function makeLandmarks(overrides?: {
  nose?: [number, number, number];
  leftEye?: [number, number, number];
  rightEye?: [number, number, number];
  leftShoulder?: [number, number, number];
  rightShoulder?: [number, number, number];
  visibility?: number;
}): LandmarkPoint[] {
  const vis = overrides?.visibility ?? 0.95;
  const nose = overrides?.nose ?? [0.5, 0.36, -0.02];
  const leftEye = overrides?.leftEye ?? [0.525, 0.33, -0.02];
  const rightEye = overrides?.rightEye ?? [0.475, 0.33, -0.02];
  const leftShoulder = overrides?.leftShoulder ?? [0.62, 0.6, 0.0];
  const rightShoulder = overrides?.rightShoulder ?? [0.38, 0.6, 0.0];

  const pts: LandmarkPoint[] = Array.from({ length: 13 }, () => ({
    x: 0.5,
    y: 0.4,
    z: 0,
    visibility: vis,
  }));

  pts[POSE_INDEX.NOSE] = { x: nose[0], y: nose[1], z: nose[2], visibility: vis };
  pts[POSE_INDEX.LEFT_EYE] = { x: leftEye[0], y: leftEye[1], z: leftEye[2], visibility: vis };
  pts[POSE_INDEX.RIGHT_EYE] = { x: rightEye[0], y: rightEye[1], z: rightEye[2], visibility: vis };
  pts[POSE_INDEX.LEFT_EAR] = { x: leftEye[0] + 0.025, y: leftEye[1] + 0.01, z: 0, visibility: vis };
  pts[POSE_INDEX.RIGHT_EAR] = { x: rightEye[0] - 0.025, y: rightEye[1] + 0.01, z: 0, visibility: vis };
  pts[POSE_INDEX.LEFT_SHOULDER] = {
    x: leftShoulder[0],
    y: leftShoulder[1],
    z: leftShoulder[2],
    visibility: vis,
  };
  pts[POSE_INDEX.RIGHT_SHOULDER] = {
    x: rightShoulder[0],
    y: rightShoulder[1],
    z: rightShoulder[2],
    visibility: vis,
  };

  return pts;
}

function calibrateBaseline(profileId: 'notebook' | 'external_monitor' = 'notebook') {
  const collector = new CalibrationCollector(3000, 10, profileId);
  collector.start(0, profileId);
  for (let i = 0; i <= 12; i++) {
    const feat = extractFeatures(makeLandmarks());
    collector.addSample(feat, i * 250);
  }
  const finalized = collector.finalize();
  if (!finalized.ok) {
    throw new Error(`Calibration failed: ${finalized.reason}`);
  }
  return finalized.calibration;
}

describe('postureEngine (TypeScript real)', () => {
  it('expõe versão 1.1.0-post-mvp, pesos 60/40 de TOO_CLOSE e 6 padrões geométricos', () => {
    expect(PARAMETERS_VERSION).toBe('1.1.0-post-mvp');
    expect(TOO_CLOSE_WEIGHTS).toEqual({ eyeWeight: 0.6, shoulderWeight: 0.4 });
    expect(Object.keys(BASE_THRESHOLDS)).toEqual([
      'FORWARD_HEAD',
      'TOO_CLOSE',
      'SHOULDER_TILT',
      'HEAD_TILT',
      'ELEVATED_SHOULDERS',
      'TRUNK_ROTATION',
    ]);
    expect(Object.keys(CALIBRATION_PROFILES)).toEqual(['notebook', 'external_monitor']);
  });

  it('mantém ADEQUATE na postura neutra e respeita persistência temporal de 4000 ms (RN03)', () => {
    const calib = calibrateBaseline('notebook');
    const comparator = new PostureComparator({ profileId: 'notebook' });
    comparator.setCalibration(calib);

    // Movimento momentâneo de anteriorização (< 4000 ms: apenas 2500 ms)
    for (let t = 4000; t < 6500; t += 250) {
      const feat = extractFeatures(
        makeLandmarks({
          nose: [0.5, 0.425, -0.14],
          leftEye: [0.525, 0.395, -0.13],
          rightEye: [0.475, 0.395, -0.13],
        }),
      );
      const res = comparator.evaluate(feat, t);
      expect(res.activeAlerts).toEqual([]);
    }

    // Retorno para postura neutra
    const resNeutral = comparator.evaluate(extractFeatures(makeLandmarks()), 7000);
    expect(resNeutral.status).toBe('ADEQUATE');
    expect(resNeutral.activeAlerts).toEqual([]);
  });

  it('detecta FORWARD_HEAD, TOO_CLOSE (60/40), SHOULDER_TILT e HEAD_TILT persistentes (> 4s)', () => {
    const calib = calibrateBaseline('notebook');

    // 1. FORWARD_HEAD
    const compFw = new PostureComparator({ profileId: 'notebook' });
    compFw.setCalibration(calib);
    let lastFw = compFw.evaluate(extractFeatures(makeLandmarks()), 4000);
    for (let t = 4000; t <= 10000; t += 250) {
      lastFw = compFw.evaluate(
        extractFeatures(
          makeLandmarks({
            nose: [0.5, 0.425, -0.14],
            leftEye: [0.525, 0.395, -0.13],
            rightEye: [0.475, 0.395, -0.13],
          }),
        ),
        t,
      );
    }
    expect(lastFw.activeAlerts).toContain('FORWARD_HEAD');

    // 2. TOO_CLOSE (60% olhos / 40% ombros)
    const compTc = new PostureComparator({ profileId: 'notebook' });
    compTc.setCalibration(calib);
    let lastTc = compTc.evaluate(extractFeatures(makeLandmarks()), 4000);
    for (let t = 4000; t <= 10000; t += 250) {
      lastTc = compTc.evaluate(
        extractFeatures(
          makeLandmarks({
            nose: [0.5, 0.36, -0.04],
            leftEye: [0.532, 0.33, -0.04],
            rightEye: [0.468, 0.33, -0.04],
            leftShoulder: [0.652, 0.635, 0.0],
            rightShoulder: [0.348, 0.635, 0.0],
          }),
        ),
        t,
      );
    }
    expect(lastTc.activeAlerts).toContain('TOO_CLOSE');

    // 3. Abdução isolada de ombros (+22% ombros, 0% olhos) NÃO dispara falso TOO_CLOSE com pesos 60/40
    const compArm = new PostureComparator({ profileId: 'notebook' });
    compArm.setCalibration(calib);
    let lastArm = compArm.evaluate(extractFeatures(makeLandmarks()), 4000);
    for (let t = 4000; t <= 10000; t += 250) {
      lastArm = compArm.evaluate(
        extractFeatures(
          makeLandmarks({
            leftShoulder: [0.646, 0.614, 0.0],
            rightShoulder: [0.354, 0.614, 0.0],
          }),
        ),
        t,
      );
    }
    expect(lastArm.activeAlerts).not.toContain('TOO_CLOSE');
  });

  it('detecta ELEVATED_SHOULDERS sem falso positivo cruzado em FORWARD_HEAD', () => {
    const calib = calibrateBaseline('notebook');
    const comparator = new PostureComparator({ profileId: 'notebook' });
    comparator.setCalibration(calib);

    let lastRes = comparator.evaluate(extractFeatures(makeLandmarks()), 4000);
    for (let t = 4000; t <= 10000; t += 250) {
      lastRes = comparator.evaluate(
        extractFeatures(
          makeLandmarks({
            nose: [0.5, 0.36, -0.02],
            leftShoulder: [0.62, 0.552, 0.0],
            rightShoulder: [0.38, 0.552, 0.0],
          }),
        ),
        t,
      );
    }
    expect(lastRes.activeAlerts).toContain('ELEVATED_SHOULDERS');
    expect(lastRes.activeAlerts).not.toContain('FORWARD_HEAD');
  });

  it('detecta TRUNK_ROTATION real e não confunde afastamento linear da câmera com rotação', () => {
    const calib = calibrateBaseline('external_monitor');
    const comparator = new PostureComparator({ profileId: 'external_monitor' });
    comparator.setCalibration(calib);

    // Caso 1: Usuário apenas se afasta em linha reta (olhos e ombros encolhem 18% na mesma proporção, sem delta Z)
    let farRes = comparator.evaluate(extractFeatures(makeLandmarks()), 4000);
    for (let t = 4000; t <= 10000; t += 250) {
      farRes = comparator.evaluate(
        extractFeatures(
          makeLandmarks({
            leftEye: [0.5205, 0.33, -0.02],
            rightEye: [0.4795, 0.33, -0.02],
            leftShoulder: [0.5984, 0.6, 0.0],
            rightShoulder: [0.4016, 0.6, 0.0],
          }),
        ),
        t,
      );
    }
    expect(farRes.activeAlerts).not.toContain('TRUNK_ROTATION');

    // Caso 2: Rotação axial real do tronco (assimetria Z entre ombros + estreitamento projetivo)
    const compRot = new PostureComparator({ profileId: 'external_monitor' });
    compRot.setCalibration(calib);
    let rotRes = compRot.evaluate(extractFeatures(makeLandmarks()), 4000);
    for (let t = 4000; t <= 10000; t += 250) {
      rotRes = compRot.evaluate(
        extractFeatures(
          makeLandmarks({
            leftShoulder: [0.595, 0.6, -0.045],
            rightShoulder: [0.405, 0.6, 0.045],
          }),
        ),
        t,
      );
    }
    expect(rotRes.activeAlerts).toContain('TRUNK_ROTATION');
  });

  it('detecta PROLONGED_ABSENCE após 60s sem landmarks e cumpre latência RNF01 <= 500 ms', () => {
    const calib = calibrateBaseline('notebook');
    const comparator = new PostureComparator({ profileId: 'notebook', prolongedAbsenceMs: 60000 });
    comparator.setCalibration(calib);

    let res = comparator.evaluate(extractFeatures([]), 4000);
    for (let t = 4000; t <= 70000; t += 5000) {
      res = comparator.evaluate(extractFeatures([]), t);
      expect(res.evaluationLatencyMs).toBeLessThanOrEqual(500);
    }
    expect(res.status).toBe('PROLONGED_ABSENCE');
    expect(res.prolongedAbsence).toBe(true);
  });
});
