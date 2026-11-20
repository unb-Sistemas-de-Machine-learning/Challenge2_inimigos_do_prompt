import {
  FilesetResolver,
  PoseLandmarker,
} from 'https://cdn.jsdelivr.net/npm/@mediapipe/tasks-vision@0.10.14/vision_bundle.mjs';

import { CLINICAL_DISCLAIMER, KNOWLEDGE_CARDS } from './knowledge-cards.js';
import {
  BASE_THRESHOLDS,
  CalibrationCollector,
  PARAMETERS_VERSION,
  POSE_INDEX,
  PostureComparator,
  extractFeatures,
} from './posture-engine.js';

const STORAGE_KEYS = {
  CALIBRATION: 'ergoai_calibration_v1',
  SESSIONS: 'ergoai_sessions_v1',
  SETTINGS: 'ergoai_settings_v1',
};

const MEDIAPIPE_WASM_URL =
  'https://cdn.jsdelivr.net/npm/@mediapipe/tasks-vision@0.10.14/wasm';
const POSE_MODEL_URL =
  'https://storage.googleapis.com/mediapipe-models/pose_landmarker/pose_landmarker_lite/float16/1/pose_landmarker_lite.task';

const INFERENCE_INTERVAL_MS = 100; // ~10 FPS para eficiência energética e CPU livre

const dom = {
  statusBadge: document.getElementById('statusBadge'),
  latencyBadge: document.getElementById('latencyBadge'),
  toggleAuditBtn: document.getElementById('toggleAuditBtn'),
  stageTitle: document.getElementById('stageTitle'),
  stageDescription: document.getElementById('stageDescription'),
  showGhostCheckbox: document.getElementById('showGhostCheckbox'),
  webcamVideo: document.getElementById('webcamVideo'),
  overlayCanvas: document.getElementById('overlayCanvas'),
  startOverlay: document.getElementById('startOverlay'),
  startCameraBtn: document.getElementById('startCameraBtn'),
  cameraErrorMsg: document.getElementById('cameraErrorMsg'),
  calibrationOverlay: document.getElementById('calibrationOverlay'),
  calibCountdown: document.getElementById('calibCountdown'),
  calibProgressBar: document.getElementById('calibProgressBar'),
  calibSampleInfo: document.getElementById('calibSampleInfo'),
  canvasLegend: document.getElementById('canvasLegend'),
  confidenceLegend: document.getElementById('confidenceLegend'),
  calibrateBtn: document.getElementById('calibrateBtn'),
  useSavedCalibBtn: document.getElementById('useSavedCalibBtn'),
  stopSessionBtn: document.getElementById('stopSessionBtn'),
  tolerancePill: document.getElementById('tolerancePill'),
  uncalibratedNotice: document.getElementById('uncalibratedNotice'),
  metricsList: document.getElementById('metricsList'),
  persistenceLabel: document.getElementById('persistenceLabel'),
  persistenceBar: document.getElementById('persistenceBar'),
  alertSeverityPill: document.getElementById('alertSeverityPill'),
  adequateCard: document.getElementById('adequateCard'),
  activeKnowledgeCard: document.getElementById('activeKnowledgeCard'),
  cardTitle: document.getElementById('cardTitle'),
  cardCategory: document.getElementById('cardCategory'),
  cardShort: document.getElementById('cardShort'),
  cardAction: document.getElementById('cardAction'),
  cardSource: document.getElementById('cardSource'),
  cardEvidence: document.getElementById('cardEvidence'),
  feedbackRow: document.getElementById('feedbackRow'),
  feedbackUsefulBtn: document.getElementById('feedbackUsefulBtn'),
  feedbackFalseBtn: document.getElementById('feedbackFalseBtn'),
  feedbackConfirmation: document.getElementById('feedbackConfirmation'),
  clinicalDisclaimer: document.getElementById('clinicalDisclaimer'),
  kpiAdequatePct: document.getElementById('kpiAdequatePct'),
  kpiDuration: document.getElementById('kpiDuration'),
  kpiAlerts: document.getElementById('kpiAlerts'),
  kpiNextBreak: document.getElementById('kpiNextBreak'),
  clearHistoryBtn: document.getElementById('clearHistoryBtn'),
  historyEmpty: document.getElementById('historyEmpty'),
  historyTable: document.getElementById('historyTable'),
  historyTableBody: document.getElementById('historyTableBody'),
  persistenceSlider: document.getElementById('persistenceSlider'),
  settingPersistenceVal: document.getElementById('settingPersistenceVal'),
  toleranceSlider: document.getElementById('toleranceSlider'),
  settingToleranceVal: document.getElementById('settingToleranceVal'),
  breakIntervalSelect: document.getElementById('breakIntervalSelect'),
  soundAlertCheckbox: document.getElementById('soundAlertCheckbox'),
  browserNotifCheckbox: document.getElementById('browserNotifCheckbox'),
  auditPanel: document.getElementById('auditPanel'),
  auditVersionPill: document.getElementById('auditVersionPill'),
  auditSnapshot: document.getElementById('auditSnapshot'),
  auditLog: document.getElementById('auditLog'),
};

const appState = {
  poseLandmarker: null,
  stream: null,
  running: false,
  loopTimerId: null,
  lastDetectTimestamp: -1,
  lastVideoTime: -1,
  lastFrameAtMs: 0,
  collector: new CalibrationCollector(3000, 10),
  comparator: new PostureComparator({ persistenceMs: 4000, toleranceFactor: 1.0 }),
  session: null,
  currentCardType: null,
  lastDisplayedAlertId: null,
  breakDue: false,
  lastBreakResetAtMs: 0,
  audioCtx: null,
  auditEntries: [],
};

// -------------------------
// Persistência Local (RNF09)
// -------------------------

function loadJson(key, fallback) {
  try {
    const raw = localStorage.getItem(key);
    return raw ? JSON.parse(raw) : fallback;
  } catch {
    return fallback;
  }
}

function saveJson(key, value) {
  try {
    localStorage.setItem(key, JSON.stringify(value));
  } catch {
    // Ignora caso localStorage esteja bloqueado
  }
}

function loadSettings() {
  const saved = loadJson(STORAGE_KEYS.SETTINGS, {});
  const persistenceSec = Number(saved.persistenceSec ?? 4);
  const toleranceFactor = Number(saved.toleranceFactor ?? 1.0);
  const breakIntervalSec = Number(saved.breakIntervalSec ?? 2700);
  const soundEnabled = saved.soundEnabled ?? true;
  const notifEnabled = saved.notifEnabled ?? false;

  dom.persistenceSlider.value = String(persistenceSec);
  dom.settingPersistenceVal.textContent = `${persistenceSec.toFixed(1)}s`;
  appState.comparator.setPersistenceMs(persistenceSec * 1000);

  dom.toleranceSlider.value = String(toleranceFactor);
  dom.settingToleranceVal.textContent = `${toleranceFactor.toFixed(2)}x`;
  dom.tolerancePill.textContent = `Tolerância: ${toleranceFactor.toFixed(2)}x`;
  appState.comparator.setToleranceFactor(toleranceFactor);

  dom.breakIntervalSelect.value = String(breakIntervalSec);
  dom.soundAlertCheckbox.checked = Boolean(soundEnabled);
  dom.browserNotifCheckbox.checked = Boolean(notifEnabled);
}

function persistSettings() {
  saveJson(STORAGE_KEYS.SETTINGS, {
    persistenceSec: Number(dom.persistenceSlider.value),
    toleranceFactor: Number(dom.toleranceSlider.value),
    breakIntervalSec: Number(dom.breakIntervalSelect.value),
    soundEnabled: dom.soundAlertCheckbox.checked,
    notifEnabled: dom.browserNotifCheckbox.checked,
  });
}

function addAuditLog(event, detail = '') {
  const time = new Date().toLocaleTimeString('pt-BR');
  appState.auditEntries.unshift({ time, event, detail });
  if (appState.auditEntries.length > 60) {
    appState.auditEntries.pop();
  }
  dom.auditLog.innerHTML = appState.auditEntries
    .map(
      (item) =>
        `<div class="audit-entry"><strong>[${item.time}]</strong> ${escapeHtml(item.event)}${
          item.detail ? ` — <span class="muted">${escapeHtml(item.detail)}</span>` : ''
        }</div>`
    )
    .join('');
}

function escapeHtml(text) {
  return String(text)
    .replaceAll('&', '&amp;')
    .replaceAll('<', '&lt;')
    .replaceAll('>', '&gt;');
}

function formatDuration(ms) {
  const totalSec = Math.max(0, Math.floor(ms / 1000));
  const min = Math.floor(totalSec / 60);
  const sec = totalSec % 60;
  return `${String(min).padStart(2, '0')}:${String(sec).padStart(2, '0')}`;
}

// -------------------------
// Sessão & Histórico (RF17 / RF18)
// -------------------------

function createSession() {
  const now = Date.now();
  appState.session = {
    id: `sess_${now}`,
    startedAtMs: now,
    startedAtIso: new Date(now).toISOString(),
    version: PARAMETERS_VERSION,
    adequateMs: 0,
    monitoredMs: 0,
    alertCount: 0,
    usefulCount: 0,
    falseAlertCount: 0,
    events: [],
  };
  appState.lastBreakResetAtMs = now;
  appState.breakDue = false;
  updateSessionKpis(now);
}

function finishAndSaveSession() {
  if (!appState.session) return;
  const now = Date.now();
  const totalDurationMs = now - appState.session.startedAtMs;
  if (appState.session.monitoredMs > 2000) {
    const adequatePct = Math.round(
      (appState.session.adequateMs / appState.session.monitoredMs) * 100
    );
    const history = loadJson(STORAGE_KEYS.SESSIONS, []);
    history.unshift({
      id: appState.session.id,
      startedAtIso: appState.session.startedAtIso,
      durationMs: totalDurationMs,
      adequatePct,
      alertCount: appState.session.alertCount,
      usefulCount: appState.session.usefulCount,
      falseAlertCount: appState.session.falseAlertCount,
    });
    saveJson(STORAGE_KEYS.SESSIONS, history.slice(0, 15));
    renderHistoryTable();
  }
  appState.session = null;
}

function renderHistoryTable() {
  const history = loadJson(STORAGE_KEYS.SESSIONS, []);
  if (!history.length) {
    dom.historyEmpty.classList.remove('hidden');
    dom.historyTable.classList.add('hidden');
    dom.historyTableBody.innerHTML = '';
    return;
  }

  dom.historyEmpty.classList.add('hidden');
  dom.historyTable.classList.remove('hidden');
  dom.historyTableBody.innerHTML = history
    .slice(0, 6)
    .map((s) => {
      const dateStr = new Date(s.startedAtIso).toLocaleString('pt-BR', {
        day: '2-digit',
        month: '2-digit',
        hour: '2-digit',
        minute: '2-digit',
      });
      return `
        <tr>
          <td>${dateStr}</td>
          <td>${formatDuration(s.durationMs)}</td>
          <td>${s.adequatePct}%</td>
          <td>${s.alertCount}</td>
          <td>👍 ${s.usefulCount} / 👎 ${s.falseAlertCount}</td>
        </tr>
      `;
    })
    .join('');
}

function updateSessionKpis(nowMs) {
  if (!appState.session) {
    dom.kpiAdequatePct.textContent = '--%';
    dom.kpiDuration.textContent = '00:00';
    dom.kpiAlerts.textContent = '0';
    dom.kpiNextBreak.textContent = '--:--';
    return;
  }

  const elapsedSessionMs = nowMs - appState.session.startedAtMs;
  dom.kpiDuration.textContent = formatDuration(elapsedSessionMs);
  dom.kpiAlerts.textContent = String(appState.session.alertCount);

  if (appState.session.monitoredMs > 0) {
    const pct = Math.min(
      100,
      Math.round((appState.session.adequateMs / appState.session.monitoredMs) * 100)
    );
    dom.kpiAdequatePct.textContent = `${pct}%`;
  } else {
    dom.kpiAdequatePct.textContent = '--%';
  }

  const breakIntervalMs = Number(dom.breakIntervalSelect.value) * 1000;
  const remainingBreakMs = Math.max(
    0,
    breakIntervalMs - (nowMs - appState.lastBreakResetAtMs)
  );
  dom.kpiNextBreak.textContent =
    remainingBreakMs === 0 ? 'Agora!' : formatDuration(remainingBreakMs);

  if (
    appState.comparator.calibration &&
    !appState.breakDue &&
    remainingBreakMs === 0
  ) {
    appState.breakDue = true;
    appState.session.alertCount += 1;
    addAuditLog('PAUSA_ATIVA_RECOMENDADA', `Intervalo de ${dom.breakIntervalSelect.value}s atingido`);
    triggerAlertFeedback(KNOWLEDGE_CARDS.BREAK_NEEDED);
    showKnowledgeCard('BREAK_NEEDED');
  }
}

// -------------------------
// Som & Notificações (RF08)
// -------------------------

function playSoftChime() {
  if (!dom.soundAlertCheckbox.checked) return;
  try {
    const AudioCtx = window.AudioContext || window.webkitAudioContext;
    if (!AudioCtx) return;
    if (!appState.audioCtx) {
      appState.audioCtx = new AudioCtx();
    }
    const ctx = appState.audioCtx;
    if (ctx.state === 'suspended') {
      ctx.resume();
    }
    const osc = ctx.createOscillator();
    const gain = ctx.createGain();
    osc.type = 'sine';
    osc.frequency.setValueAtTime(528, ctx.currentTime);
    osc.frequency.exponentialRampToValueAtTime(660, ctx.currentTime + 0.18);
    gain.gain.setValueAtTime(0.001, ctx.currentTime);
    gain.gain.exponentialRampToValueAtTime(0.08, ctx.currentTime + 0.04);
    gain.gain.exponentialRampToValueAtTime(0.001, ctx.currentTime + 0.35);
    osc.connect(gain);
    gain.connect(ctx.destination);
    osc.start();
    osc.stop(ctx.currentTime + 0.36);
  } catch {
    // Silencioso se navegador bloquear áudio
  }
}

function sendBrowserNotification(card) {
  if (!dom.browserNotifCheckbox.checked) return;
  if (!('Notification' in window) || Notification.permission !== 'granted') return;
  try {
    new Notification(`ErgoAI: ${card.titulo}`, {
      body: card.acaoRecomendada,
      tag: card.id,
    });
  } catch {
    // Ignora falhas de notificação
  }
}

function triggerAlertFeedback(card) {
  playSoftChime();
  sendBrowserNotification(card);
}

// -------------------------
// Câmera & MediaPipe Pose
// -------------------------

async function initPoseLandmarker() {
  const vision = await FilesetResolver.forVisionTasks(MEDIAPIPE_WASM_URL);
  try {
    return await PoseLandmarker.createFromOptions(vision, {
      baseOptions: {
        modelAssetPath: POSE_MODEL_URL,
        delegate: 'GPU',
      },
      runningMode: 'VIDEO',
      numPoses: 1,
      minPoseDetectionConfidence: 0.5,
      minPosePresenceConfidence: 0.5,
      minTrackingConfidence: 0.5,
    });
  } catch {
    // Fallback para CPU caso WebGL2/GPU não esteja disponível
    return await PoseLandmarker.createFromOptions(vision, {
      baseOptions: {
        modelAssetPath: POSE_MODEL_URL,
        delegate: 'CPU',
      },
      runningMode: 'VIDEO',
      numPoses: 1,
      minPoseDetectionConfidence: 0.5,
      minPosePresenceConfidence: 0.5,
      minTrackingConfidence: 0.5,
    });
  }
}

async function startCameraAndSession() {
  dom.cameraErrorMsg.classList.add('hidden');
  dom.startCameraBtn.disabled = true;
  dom.startCameraBtn.textContent = 'Carregando modelo e webcam...';
  setStatusBadge('Carregando IA...', 'pill-calib');

  try {
    if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
      throw new Error(
        'Navegador sem suporte a getUserMedia ou contexto não seguro (use localhost ou HTTPS).'
      );
    }

    const stream = await navigator.mediaDevices.getUserMedia({
      video: {
        width: { ideal: 640 },
        height: { ideal: 480 },
        facingMode: 'user',
      },
      audio: false,
    });

    appState.stream = stream;
    dom.webcamVideo.srcObject = stream;
    await dom.webcamVideo.play();

    if (!appState.poseLandmarker) {
      appState.poseLandmarker = await initPoseLandmarker();
    }

    appState.running = true;
    appState.lastDetectTimestamp = -1;
    appState.lastVideoTime = -1;
    appState.lastFrameAtMs = Date.now();
    createSession();

    dom.startOverlay.classList.add('hidden');
    dom.canvasLegend.classList.remove('hidden');
    dom.calibrateBtn.disabled = false;
    dom.stopSessionBtn.classList.remove('hidden');

    const savedCalib = loadJson(STORAGE_KEYS.CALIBRATION, null);
    if (savedCalib && savedCalib.metrics) {
      dom.useSavedCalibBtn.classList.remove('hidden');
    }

    setStatusBadge('Pronto para Calibrar (Etapa 1)', 'pill-calib');
    addAuditLog('SESSAO_INICIADA', 'Webcam autorizada e PoseLandmarker carregado localmente');
    scheduleNextFrame();
  } catch (err) {
    dom.cameraErrorMsg.textContent = `Não foi possível iniciar a webcam: ${err.message}`;
    dom.cameraErrorMsg.classList.remove('hidden');
    dom.startCameraBtn.disabled = false;
    dom.startCameraBtn.textContent = 'Tentar Novamente';
    setStatusBadge('Erro na Webcam', 'pill-alert');
    addAuditLog('ERRO_INICIALIZACAO', err.message);
  }
}

function stopSession() {
  appState.running = false;
  if (appState.loopTimerId) {
    clearTimeout(appState.loopTimerId);
    appState.loopTimerId = null;
  }
  appState.collector.cancel();
  appState.comparator.setCalibration(null);
  finishAndSaveSession();

  if (appState.stream) {
    appState.stream.getTracks().forEach((t) => t.stop());
    appState.stream = null;
  }
  dom.webcamVideo.srcObject = null;

  const ctx = dom.overlayCanvas.getContext('2d');
  ctx.clearRect(0, 0, dom.overlayCanvas.width, dom.overlayCanvas.height);

  dom.startOverlay.classList.remove('hidden');
  dom.calibrationOverlay.classList.add('hidden');
  dom.canvasLegend.classList.add('hidden');
  dom.stopSessionBtn.classList.add('hidden');
  dom.useSavedCalibBtn.classList.add('hidden');
  dom.calibrateBtn.disabled = true;
  dom.calibrateBtn.textContent = '🎯 Regular / Calibrar Postura Ideal (3s)';
  dom.startCameraBtn.disabled = false;
  dom.startCameraBtn.textContent = 'Ligar Webcam e Carregar IA';

  dom.stageTitle.textContent = 'Etapa 1 — Regulagem da Postura Ideal';
  dom.stageDescription.textContent =
    'Ligue a webcam, ajuste sua posição confortável e calibre sua referência individual.';
  dom.uncalibratedNotice.classList.remove('hidden');
  dom.metricsList.classList.add('hidden');
  clearKnowledgeCard();
  setStatusBadge('Sessão Encerrada', 'pill-idle');
  dom.latencyBadge.textContent = 'Latência: -- ms';
  addAuditLog('SESSAO_ENCERRADA', 'Monitoramento interrompido pelo usuário (RN08)');
}

// -------------------------
// Calibração (Etapa 1)
// -------------------------

function startCalibration() {
  if (!appState.running) return;
  appState.collector.start(performance.now());
  dom.calibrationOverlay.classList.remove('hidden');
  dom.calibrateBtn.disabled = true;
  dom.useSavedCalibBtn.classList.add('hidden');
  dom.calibProgressBar.style.width = '0%';
  dom.calibCountdown.textContent = '3';
  setStatusBadge('Calibrando (3s)...', 'pill-calib');
  addAuditLog('CALIBRACAO_INICIADA', 'Coletando amostras por 3 segundos');
}

function applyCalibration(calibration, sourceLabel) {
  appState.comparator.setCalibration(calibration);
  saveJson(STORAGE_KEYS.CALIBRATION, calibration);

  dom.calibrationOverlay.classList.add('hidden');
  dom.calibrateBtn.disabled = false;
  dom.calibrateBtn.textContent = '🔄 Recalibrar Postura Ideal';
  dom.useSavedCalibBtn.classList.add('hidden');

  dom.stageTitle.textContent = 'Etapa 2 — Comparando Postura Atual vs. Ideal';
  dom.stageDescription.textContent =
    'Sua referência individual está travada em ciano. O algoritmo monitora desvios persistentes.';
  dom.uncalibratedNotice.classList.add('hidden');
  dom.metricsList.classList.remove('hidden');
  setStatusBadge('Postura Adequada', 'pill-ok');

  addAuditLog(
    'CALIBRACAO_CONCLUIDA',
    `${sourceLabel} (${calibration.sampleCount} amostras, neckRatio=${calibration.metrics.neckHeightRatio.toFixed(3)})`
  );
}

// -------------------------
// Loop Principal de Visão
// -------------------------

function scheduleNextFrame() {
  if (!appState.running) return;
  appState.loopTimerId = setTimeout(processFrame, INFERENCE_INTERVAL_MS);
}

function processFrame() {
  if (!appState.running) return;

  const video = dom.webcamVideo;
  const nowEpochMs = Date.now();
  const deltaMs = Math.max(0, nowEpochMs - appState.lastFrameAtMs);
  appState.lastFrameAtMs = nowEpochMs;

  updateSessionKpis(nowEpochMs);

  if (video.readyState >= 2 && video.videoWidth > 0 && appState.poseLandmarker) {
    const perfNow = performance.now();
    if (video.currentTime !== appState.lastVideoTime && perfNow > appState.lastDetectTimestamp) {
      appState.lastVideoTime = video.currentTime;
      appState.lastDetectTimestamp = perfNow;

      const t0 = performance.now();
      const result = appState.poseLandmarker.detectForVideo(video, perfNow);
      const latencyMs = Math.round(performance.now() - t0);
      dom.latencyBadge.textContent = `Latência: ${latencyMs} ms`;

      const landmarks = result?.landmarks?.[0] || null;
      const features = extractFeatures(landmarks);

      if (features.valid) {
        dom.confidenceLegend.textContent = `Confiança: ${Math.round(features.avgConfidence * 100)}%`;
      } else {
        dom.confidenceLegend.textContent = `Confiança baixa (${Math.round(
          (features.avgConfidence || 0) * 100
        )}%)`;
      }

      // Fluxo Etapa 1: Se calibração em andamento
      if (appState.collector.active) {
        const calibStatus = appState.collector.addSample(features, perfNow);
        const secsLeft = Math.max(1, Math.ceil(calibStatus.remainingMs / 1000));
        dom.calibCountdown.textContent = String(secsLeft);
        dom.calibProgressBar.style.width = `${Math.round(calibStatus.progress * 100)}%`;
        dom.calibSampleInfo.textContent = `Coletando pontos corporais: ${calibStatus.sampleCount} amostras válidas`;

        if (calibStatus.done) {
          const finalized = appState.collector.finalize();
          if (finalized.ok) {
            applyCalibration(finalized.calibration, 'Nova calibração');
          } else {
            dom.calibrationOverlay.classList.add('hidden');
            dom.calibrateBtn.disabled = false;
            setStatusBadge('Falha na Calibração', 'pill-warn');
            addAuditLog('CALIBRACAO_FALHOU', finalized.reason);
            alert(finalized.reason);
          }
        }
        drawOverlay(landmarks, null, 'CALIBRATING');
      } else if (appState.comparator.calibration) {
        // Fluxo Etapa 2: Comparação contínua Atual vs Ideal
        const evalResult = appState.comparator.evaluate(features, perfNow);
        updateComparatorUI(evalResult, deltaMs);
        drawOverlay(
          landmarks,
          appState.comparator.calibration.referenceLandmarks,
          evalResult.status
        );
      } else {
        // Câmera ligada, aguardando usuário clicar em Calibrar
        drawOverlay(landmarks, null, 'PREVIEW');
      }
    }
  }

  scheduleNextFrame();
}

// -------------------------
// Atualização de UI e Canvas
// -------------------------

function updateComparatorUI(evalResult, deltaMs) {
  if (appState.session && evalResult.valid) {
    appState.session.monitoredMs += deltaMs;
    if (evalResult.status === 'ADEQUATE' || evalResult.status === 'WARNING_TRANSIENT') {
      appState.session.adequateMs += deltaMs;
    }
  }

  // Atualiza barras de desvio
  if (evalResult.valid) {
    for (const [type, dev] of Object.entries(evalResult.deviations)) {
      const valEl = document.getElementById(`val-${type}`);
      const barEl = document.getElementById(`bar-${type}`);
      if (!valEl || !barEl) continue;

      const precision = BASE_THRESHOLDS[type].unit === '°' ? 1 : 1;
      valEl.textContent = `${dev.value.toFixed(precision)}${dev.unit} / ${dev.thresholdOn.toFixed(
        precision
      )}${dev.unit}`;

      const fillPct = Math.min(100, Math.round((dev.value / dev.thresholdOn) * 100));
      barEl.style.width = `${fillPct}%`;
      barEl.classList.remove('progress-amber', 'progress-red');
      if (dev.activeAlert) {
        barEl.classList.add('progress-red');
      } else if (dev.inWarningBand || fillPct >= 78) {
        barEl.classList.add('progress-amber');
      }
    }

    const persistSec = (evalResult.persistenceProgress * (evalResult.persistenceMs / 1000)).toFixed(
      1
    );
    const maxSec = (evalResult.persistenceMs / 1000).toFixed(1);
    dom.persistenceLabel.textContent = `${persistSec}s / ${maxSec}s`;
    dom.persistenceBar.style.width = `${Math.round(evalResult.persistenceProgress * 100)}%`;
  }

  // Status badge no cabeçalho
  if (evalResult.status === 'LOW_CONFIDENCE') {
    setStatusBadge('Confiança Baixa (RN05)', 'pill-warn');
  } else if (evalResult.status === 'ALERT_PERSISTENT') {
    setStatusBadge('Desvio Persistente', 'pill-alert');
  } else if (evalResult.status === 'WARNING_TRANSIENT') {
    setStatusBadge('Atenção (Momentâneo)', 'pill-warn');
  } else if (evalResult.status === 'ADEQUATE') {
    setStatusBadge('Postura Adequada', 'pill-ok');
  }

  // Disparo e resolução de alertas
  for (const trig of evalResult.newlyTriggered) {
    if (appState.session) {
      appState.session.alertCount += 1;
      appState.session.events.push({
        type: trig.type,
        value: Number(trig.value.toFixed(2)),
        confidence: Number(trig.confidence.toFixed(2)),
        at: new Date().toISOString(),
      });
    }
    const card = KNOWLEDGE_CARDS[trig.type];
    addAuditLog(
      'ALERTA_DISPARADO',
      `${trig.type} valor=${trig.value.toFixed(1)} limiar=${trig.thresholdOn.toFixed(1)} conf=${(
        trig.confidence * 100
      ).toFixed(0)}%`
    );
    if (card) {
      triggerAlertFeedback(card);
    }
  }

  for (const res of evalResult.newlyResolved) {
    addAuditLog('DESVIO_CORRIGIDO', `${res.type} retornou à faixa adequada`);
  }

  // Exibição do Cartão de Conhecimento ativo
  if (evalResult.activeAlerts.length > 0) {
    showKnowledgeCard(evalResult.activeAlerts[0]);
  } else if (appState.breakDue) {
    showKnowledgeCard('BREAK_NEEDED');
  } else {
    clearKnowledgeCard(evalResult.status === 'LOW_CONFIDENCE');
  }

  // Atualiza snapshot de auditoria se visível
  if (!dom.auditPanel.classList.contains('hidden')) {
    dom.auditSnapshot.textContent = JSON.stringify(
      {
        status: evalResult.status,
        toleranceFactor: evalResult.toleranceFactor,
        avgConfidence: evalResult.avgConfidence
          ? Number(evalResult.avgConfidence.toFixed(3))
          : 0,
        referenceMetrics: evalResult.referenceMetrics
          ? roundObj(evalResult.referenceMetrics)
          : null,
        smoothedMetrics: evalResult.smoothedMetrics
          ? roundObj(evalResult.smoothedMetrics)
          : null,
        activeAlerts: evalResult.activeAlerts,
      },
      null,
      2
    );
  }
}

function roundObj(obj) {
  const out = {};
  for (const [k, v] of Object.entries(obj)) {
    out[k] = typeof v === 'number' ? Number(v.toFixed(3)) : v;
  }
  return out;
}

function showKnowledgeCard(type) {
  const card = KNOWLEDGE_CARDS[type];
  if (!card) return;

  const isSameVisibleCard =
    appState.currentCardType === type &&
    !dom.activeKnowledgeCard.classList.contains('hidden');
  if (isSameVisibleCard) {
    return;
  }

  appState.currentCardType = type;
  dom.adequateCard.classList.add('hidden');
  dom.activeKnowledgeCard.classList.remove('hidden');
  dom.feedbackConfirmation.classList.add('hidden');

  if (type === 'BREAK_NEEDED') {
    dom.activeKnowledgeCard.classList.add('knowledge-break');
    dom.alertSeverityPill.textContent = 'Pausa Ativa';
    dom.alertSeverityPill.className = 'pill pill-warn';
    dom.feedbackUsefulBtn.textContent = '✅ Pausa Concluída (Reiniciar Timer)';
    dom.feedbackFalseBtn.classList.add('hidden');
  } else {
    dom.activeKnowledgeCard.classList.remove('knowledge-break');
    dom.alertSeverityPill.textContent = 'Alerta Ativo';
    dom.alertSeverityPill.className = 'pill pill-alert';
    dom.feedbackUsefulBtn.textContent = '👍 Alerta Útil';
    dom.feedbackFalseBtn.classList.remove('hidden');
  }

  dom.cardTitle.textContent = card.titulo;
  dom.cardCategory.textContent = card.severidadeLabel;
  dom.cardShort.textContent = card.orientacaoCurta;
  dom.cardAction.textContent = card.acaoRecomendada;
  dom.cardSource.textContent = card.fonte;
  dom.cardEvidence.textContent = `"${card.trechoEvidencia}"`;
}

function clearKnowledgeCard(lowConfidence = false) {
  appState.currentCardType = null;
  dom.activeKnowledgeCard.classList.add('hidden');
  dom.adequateCard.classList.remove('hidden');

  if (lowConfidence) {
    dom.alertSeverityPill.textContent = 'Confiança Baixa';
    dom.alertSeverityPill.className = 'pill pill-warn';
    dom.adequateCard.innerHTML =
      '<strong>Posição ou iluminação insuficiente (RN05).</strong><p>Mantenha rosto e ombros bem iluminados e visíveis na câmera para evitar classificações imprecisas.</p>';
  } else if (appState.comparator.calibration) {
    dom.alertSeverityPill.textContent = 'Postura OK';
    dom.alertSeverityPill.className = 'pill pill-ok';
    dom.adequateCard.innerHTML =
      '<strong>Postura alinhada com a sua referência calibrada!</strong><p>Continue assim. Pequenos movimentos rápidos são ignorados pelo filtro de histerese.</p>';
  } else {
    dom.alertSeverityPill.textContent = 'Em espera';
    dom.alertSeverityPill.className = 'pill pill-idle';
  }
}

function setStatusBadge(text, className) {
  dom.statusBadge.textContent = text;
  dom.statusBadge.className = `pill ${className}`;
}

function drawOverlay(currentLandmarks, refLandmarks, status) {
  const video = dom.webcamVideo;
  const canvas = dom.overlayCanvas;
  if (!video.videoWidth || !video.videoHeight) return;

  if (canvas.width !== video.videoWidth || canvas.height !== video.videoHeight) {
    canvas.width = video.videoWidth;
    canvas.height = video.videoHeight;
  }

  const ctx = canvas.getContext('2d');
  ctx.clearRect(0, 0, canvas.width, canvas.height);

  // 1. Silhueta Ideal Calibrada (Tracejado em Ciano)
  if (refLandmarks && dom.showGhostCheckbox.checked) {
    drawSkeleton(ctx, canvas.width, canvas.height, refLandmarks, {
      strokeColor: 'rgba(34, 211, 238, 0.78)',
      pointColor: 'rgba(34, 211, 238, 0.95)',
      lineWidth: 2.5,
      dashed: [7, 5],
      radius: 4.5,
    });
  }

  // 2. Esqueleto Atual
  if (currentLandmarks) {
    let color = '#10b981'; // ADEQUATE
    if (status === 'ALERT_PERSISTENT') color = '#ef4444';
    else if (status === 'WARNING_TRANSIENT' || status === 'LOW_CONFIDENCE') color = '#f59e0b';
    else if (status === 'CALIBRATING' || status === 'PREVIEW') color = '#60a5fa';

    drawSkeleton(ctx, canvas.width, canvas.height, currentLandmarks, {
      strokeColor: color,
      pointColor: color,
      lineWidth: 3,
      dashed: [],
      radius: 5,
    });
  }
}

function drawSkeleton(ctx, w, h, lmMap, style) {
  const nose = lmMap[POSE_INDEX.NOSE];
  const leftEye = lmMap[POSE_INDEX.LEFT_EYE];
  const rightEye = lmMap[POSE_INDEX.RIGHT_EYE];
  const leftEar = lmMap[POSE_INDEX.LEFT_EAR];
  const rightEar = lmMap[POSE_INDEX.RIGHT_EAR];
  const leftShoulder = lmMap[POSE_INDEX.LEFT_SHOULDER];
  const rightShoulder = lmMap[POSE_INDEX.RIGHT_SHOULDER];

  if (!nose || !leftShoulder || !rightShoulder) return;

  const midShoulder = {
    x: (leftShoulder.x + rightShoulder.x) / 2,
    y: (leftShoulder.y + rightShoulder.y) / 2,
  };

  ctx.save();
  ctx.strokeStyle = style.strokeColor;
  ctx.fillStyle = style.pointColor;
  ctx.lineWidth = style.lineWidth;
  ctx.setLineDash(style.dashed);

  const pairs = [
    [leftShoulder, rightShoulder],
    [midShoulder, nose],
    [leftEye, rightEye],
    [leftEar, leftEye],
    [rightEar, rightEye],
  ];

  for (const [a, b] of pairs) {
    if (!a || !b) continue;
    ctx.beginPath();
    ctx.moveTo(a.x * w, a.y * h);
    ctx.lineTo(b.x * w, b.y * h);
    ctx.stroke();
  }

  ctx.setLineDash([]);
  const points = [nose, leftEye, rightEye, leftShoulder, rightShoulder];
  for (const pt of points) {
    if (!pt) continue;
    ctx.beginPath();
    ctx.arc(pt.x * w, pt.y * h, style.radius, 0, Math.PI * 2);
    ctx.fill();
  }

  ctx.restore();
}

// -------------------------
// Eventos de Interface
// -------------------------

function bindEvents() {
  dom.startCameraBtn.addEventListener('click', startCameraAndSession);
  dom.stopSessionBtn.addEventListener('click', stopSession);
  dom.calibrateBtn.addEventListener('click', startCalibration);

  dom.useSavedCalibBtn.addEventListener('click', () => {
    const saved = loadJson(STORAGE_KEYS.CALIBRATION, null);
    if (saved) {
      applyCalibration(saved, 'Calibração recuperada');
    }
  });

  dom.feedbackUsefulBtn.addEventListener('click', () => {
    if (appState.currentCardType === 'BREAK_NEEDED') {
      appState.breakDue = false;
      appState.lastBreakResetAtMs = Date.now();
      addAuditLog('PAUSA_CONFIRMADA', 'Cronômetro de pausa ativa reiniciado');
      clearKnowledgeCard();
      return;
    }

    if (appState.session) appState.session.usefulCount += 1;
    const newTol = appState.comparator.applyFeedback('util');
    dom.toleranceSlider.value = String(newTol);
    dom.settingToleranceVal.textContent = `${newTol.toFixed(2)}x`;
    dom.tolerancePill.textContent = `Tolerância: ${newTol.toFixed(2)}x`;
    persistSettings();

    dom.feedbackConfirmation.textContent =
      'Obrigado! Registro salvo como alerta útil (RF10).';
    dom.feedbackConfirmation.classList.remove('hidden');
    addAuditLog('FEEDBACK_UTIL', `tipo=${appState.currentCardType} tolerância=${newTol}x`);
  });

  dom.feedbackFalseBtn.addEventListener('click', () => {
    if (appState.session) appState.session.falseAlertCount += 1;
    const newTol = appState.comparator.applyFeedback('falso_alerta');
    dom.toleranceSlider.value = String(newTol);
    dom.settingToleranceVal.textContent = `${newTol.toFixed(2)}x`;
    dom.tolerancePill.textContent = `Tolerância: ${newTol.toFixed(2)}x`;
    persistSettings();

    dom.feedbackConfirmation.textContent = `Entendido! Tolerância ajustada para ${newTol.toFixed(
      2
    )}x para reduzir falsos alertas (RF11 / RN09).`;
    dom.feedbackConfirmation.classList.remove('hidden');
    addAuditLog(
      'FEEDBACK_FALSO_ALERTA',
      `tipo=${appState.currentCardType} nova_tolerancia=${newTol}x`
    );
  });

  dom.persistenceSlider.addEventListener('input', () => {
    const sec = Number(dom.persistenceSlider.value);
    dom.settingPersistenceVal.textContent = `${sec.toFixed(1)}s`;
    appState.comparator.setPersistenceMs(sec * 1000);
    persistSettings();
  });

  dom.toleranceSlider.addEventListener('input', () => {
    const factor = Number(dom.toleranceSlider.value);
    dom.settingToleranceVal.textContent = `${factor.toFixed(2)}x`;
    dom.tolerancePill.textContent = `Tolerância: ${factor.toFixed(2)}x`;
    appState.comparator.setToleranceFactor(factor);
    persistSettings();
  });

  dom.breakIntervalSelect.addEventListener('change', () => {
    appState.lastBreakResetAtMs = Date.now();
    appState.breakDue = false;
    persistSettings();
    updateSessionKpis(Date.now());
  });

  dom.soundAlertCheckbox.addEventListener('change', persistSettings);

  dom.browserNotifCheckbox.addEventListener('change', async () => {
    if (dom.browserNotifCheckbox.checked && 'Notification' in window) {
      if (Notification.permission === 'default') {
        const perm = await Notification.requestPermission();
        if (perm !== 'granted') {
          dom.browserNotifCheckbox.checked = false;
        }
      } else if (Notification.permission === 'denied') {
        dom.browserNotifCheckbox.checked = false;
        alert('Notificações estão bloqueadas nas permissões deste site no navegador.');
      }
    }
    persistSettings();
  });

  dom.clearHistoryBtn.addEventListener('click', () => {
    localStorage.removeItem(STORAGE_KEYS.SESSIONS);
    localStorage.removeItem(STORAGE_KEYS.CALIBRATION);
    dom.useSavedCalibBtn.classList.add('hidden');
    renderHistoryTable();
    addAuditLog('HISTORICO_LIMPO', 'Dados locais removidos pelo usuário (RNF09)');
  });

  dom.toggleAuditBtn.addEventListener('click', () => {
    const isHidden = dom.auditPanel.classList.toggle('hidden');
    dom.toggleAuditBtn.setAttribute('aria-expanded', String(!isHidden));
  });

  window.addEventListener('beforeunload', () => {
    finishAndSaveSession();
  });
}

function bootstrap() {
  dom.clinicalDisclaimer.textContent = CLINICAL_DISCLAIMER;
  dom.auditVersionPill.textContent = `Versão: ${PARAMETERS_VERSION}`;
  loadSettings();
  renderHistoryTable();
  bindEvents();
  addAuditLog('APP_PRONTO', 'Protótipo carregado. Aguardando autorização de webcam.');
}

bootstrap();
