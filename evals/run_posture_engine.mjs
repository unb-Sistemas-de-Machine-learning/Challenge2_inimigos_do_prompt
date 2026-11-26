/**
 * Adaptador fino em Node.js (ESM + type-stripping nativo no Node v24+) para executar
 * o motor postural real (frontend/src/posture-engine/postureEngine.ts) sobre datasets
 * numéricos de landmarks sem duplicar regras em Python.
 *
 * Uso: node evals/run_posture_engine.mjs <caminho_dataset.json>
 */
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

import {
  BASE_THRESHOLDS,
  CalibrationCollector,
  PARAMETERS_VERSION,
  PostureComparator,
  extractFeatures,
} from '../frontend/src/posture-engine/postureEngine.ts';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const REPO_ROOT = path.resolve(__dirname, '..');

function normalizarPose(pose) {
  if (!Array.isArray(pose)) return [];
  return pose.map((pt) => {
    if (!pt || typeof pt !== 'object') return pt;
    // Compatibilidade entre frontend/src/types/coleta.ts ("visibilidade") e MediaPipe/postureEngine.ts ("visibility")
    const visibility =
      typeof pt.visibility === 'number'
        ? pt.visibility
        : typeof pt.visibilidade === 'number'
          ? pt.visibilidade
          : undefined;
    return {
      x: pt.x,
      y: pt.y,
      z: pt.z ?? 0,
      ...(visibility !== undefined ? { visibility } : {}),
    };
  });
}

function executarCenario(cenario, parametrosPadrao = {}) {
  const params = { ...parametrosPadrao, ...(cenario.parametros || {}) };
  const calibDurationMs = params.calibrationDurationMs ?? 3000;
  const calibMinSamples = params.calibrationMinSamples ?? 10;

  const collector = new CalibrationCollector(calibDurationMs, calibMinSamples);
  const quadrosCalib = cenario.calibracao || [];
  const t0Calib = quadrosCalib.length > 0 ? quadrosCalib[0].t_ms : 0;
  collector.start(t0Calib);
  for (const amostra of quadrosCalib) {
    const features = extractFeatures(normalizarPose(amostra.pose));
    collector.addSample(features, amostra.t_ms);
  }
  const calibRes = collector.finalize();

  const comparator = new PostureComparator({
    emaAlpha: params.emaAlpha ?? 0.28,
    persistenceMs: params.persistenceMs ?? 4000,
    recoveryMs: params.recoveryMs ?? 1200,
    toleranceFactor: params.toleranceFactor ?? 1.0,
  });

  if (calibRes.ok) {
    comparator.setCalibration(calibRes.calibration);
  }

  const triggeredSet = new Set();
  const triggeredOrder = [];
  let lowConfidenceFrames = 0;
  let totalFrames = 0;
  const maxValues = Object.fromEntries(Object.keys(BASE_THRESHOLDS).map((k) => [k, 0]));

  const tStart = performance.now();
  for (const amostra of cenario.quadros || []) {
    totalFrames += 1;
    const features = extractFeatures(normalizarPose(amostra.pose));
    const res = comparator.evaluate(features, amostra.t_ms);
    if (res.status === 'LOW_CONFIDENCE') {
      lowConfidenceFrames += 1;
      continue;
    }
    if (res.measuredValues) {
      for (const [tipo, value] of Object.entries(res.measuredValues)) {
        if (value > maxValues[tipo]) {
          maxValues[tipo] = Number(value.toFixed(3));
        }
      }
    }
    for (const tipo of res.activeAlerts || []) {
      if (!triggeredSet.has(tipo)) {
        triggeredSet.add(tipo);
        triggeredOrder.push(tipo);
      }
    }
  }
  const elapsedMs = Number((performance.now() - tStart).toFixed(3));

  return {
    id: cenario.id,
    categoria: cenario.categoria || '',
    rotulo_esperado: cenario.rotulo_esperado,
    calibration_ok: Boolean(calibRes.ok),
    alerts_triggered: triggeredOrder,
    primary_predicted: triggeredOrder.length > 0 ? triggeredOrder[0] : null,
    low_confidence_frames: lowConfidenceFrames,
    total_frames: totalFrames,
    max_values: maxValues,
    elapsed_ms: elapsedMs,
  };
}

function main() {
  const datasetArg = process.argv[2];
  if (!datasetArg) {
    console.error('Uso: node evals/run_posture_engine.mjs <caminho_dataset.json>');
    process.exit(2);
  }

  const datasetPath = path.resolve(datasetArg);
  const dados = JSON.parse(fs.readFileSync(datasetPath, 'utf-8'));
  const resultados = (dados.cenarios || []).map((c) =>
    executarCenario(c, dados.parametros_padrao || {})
  );

  const engineAbsPath = path.resolve(REPO_ROOT, 'frontend/src/posture-engine/postureEngine.ts');
  const saida = {
    engine_version: PARAMETERS_VERSION,
    engine_path: path.relative(REPO_ROOT, engineAbsPath),
    dataset_tipo: dados.tipo_dataset || 'desconhecido',
    dataset_versao: dados.versao || '1',
    classes_avaliadas: Object.keys(BASE_THRESHOLDS),
    resultados,
  };
  process.stdout.write(JSON.stringify(saida, null, 2) + '\n');
}

main();
