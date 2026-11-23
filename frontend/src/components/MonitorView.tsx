import { FilesetResolver, PoseLandmarker } from '@mediapipe/tasks-vision';
import { useEffect, useRef, useState } from 'react';
import calibrationVideo from '../../assets/img/calibration.mp4';
import ergoGif from '../../assets/img/ergo.gif';
import ergoLogo from '../../assets/img/ergoAI-fundo.jpeg';
import typeTooClose from '../../assets/img/types/type-1.jpg';
import typeHeadTilt from '../../assets/img/types/type-3.jpg';
import typeShoulderTilt from '../../assets/img/types/type-5.jpg';
import typeForwardHead from '../../assets/img/types/type-7.jpg';
import { KNOWLEDGE_CARDS, type DeviationType } from '../data/knowledgeCards';
import {
  CalibrationCollector,
  POSE_INDEX,
  PostureComparator,
  extractFeatures,
  type CalibrationData,
  type LandmarkPoint,
} from '../posture-engine/postureEngine';

interface MonitorViewProps {
  onBack: () => void;
}

type SidebarTab = 'calibrar' | 'monitor' | 'setup';

const MEDIAPIPE_WASM_URL =
  'https://cdn.jsdelivr.net/npm/@mediapipe/tasks-vision@0.10.14/wasm';
const POSE_MODEL_URL =
  'https://storage.googleapis.com/mediapipe-models/pose_landmarker/pose_landmarker_lite/float16/1/pose_landmarker_lite.task';
const CALIBRATION_STORAGE_KEY = 'ergoai_calibration_v1';

const DEVIATION_MEME_IMAGES: Record<
  DeviationType,
  { src: string; caption: string }
> = {
  FORWARD_HEAD: {
    src: typeForwardHead,
    caption: 'Você não quer ficar assim, né? Recue o queixo e apoie as costas.',
  },
  TOO_CLOSE: {
    src: typeTooClose,
    caption: 'Colado na tela assim? Afaste o tronco cerca de um braço.',
  },
  SHOULDER_TILT: {
    src: typeShoulderTilt,
    caption: 'Ombros desalinhados (> 25%)! Relaxe e apoie os dois lados por igual.',
  },
  HEAD_TILT: {
    src: typeHeadTilt,
    caption: 'Cabeça tombada? Centralize o olhar no monitor.',
  },
};

function getMetricLevel(ratio?: number): 'ok' | 'warn' | 'danger' {
  if (ratio === undefined) return 'ok';
  if (ratio >= 1) return 'danger';
  if (ratio >= 0.6) return 'warn';
  return 'ok';
}

const POSE_CONNECTIONS: [number, number][] = [
  [POSE_INDEX.LEFT_EAR, POSE_INDEX.LEFT_EYE],
  [POSE_INDEX.LEFT_EYE, POSE_INDEX.NOSE],
  [POSE_INDEX.NOSE, POSE_INDEX.RIGHT_EYE],
  [POSE_INDEX.RIGHT_EYE, POSE_INDEX.RIGHT_EAR],
  [POSE_INDEX.LEFT_SHOULDER, POSE_INDEX.RIGHT_SHOULDER],
];

function isVisible(lm?: { visibility?: number; presence?: number }): boolean {
  if (!lm) return false;
  const score = lm.visibility ?? lm.presence ?? 1;
  return score >= 0.45;
}

function drawNeckAxis(
  ctx: CanvasRenderingContext2D,
  width: number,
  height: number,
  nose?: { x: number; y: number },
  leftShoulder?: { x: number; y: number },
  rightShoulder?: { x: number; y: number },
) {
  if (!nose || !leftShoulder || !rightShoulder) return;
  const midX = ((leftShoulder.x + rightShoulder.x) / 2) * width;
  const midY = ((leftShoulder.y + rightShoulder.y) / 2) * height;
  ctx.beginPath();
  ctx.moveTo(midX, midY);
  ctx.lineTo(nose.x * width, nose.y * height);
  ctx.stroke();
}

function drawPoseOverlay(
  ctx: CanvasRenderingContext2D,
  width: number,
  height: number,
  landmarks: LandmarkPoint[] | null,
  calibration: CalibrationData | null,
  hasAlert: boolean,
) {
  ctx.clearRect(0, 0, width, height);

  if (calibration?.referenceLandmarks) {
    const ref = calibration.referenceLandmarks;
    ctx.save();
    ctx.strokeStyle = 'rgba(16, 185, 129, 0.7)';
    ctx.lineWidth = 2;
    ctx.setLineDash([6, 6]);
    for (const [aId, bId] of POSE_CONNECTIONS) {
      const a = ref[aId];
      const b = ref[bId];
      if (!a || !b) continue;
      ctx.beginPath();
      ctx.moveTo(a.x * width, a.y * height);
      ctx.lineTo(b.x * width, b.y * height);
      ctx.stroke();
    }
    drawNeckAxis(
      ctx,
      width,
      height,
      ref[POSE_INDEX.NOSE],
      ref[POSE_INDEX.LEFT_SHOULDER],
      ref[POSE_INDEX.RIGHT_SHOULDER],
    );
    ctx.restore();
  }

  if (!landmarks) return;

  const lineColor = hasAlert ? '#FF6B4A' : '#FFD15C';
  ctx.save();
  ctx.strokeStyle = lineColor;
  ctx.lineWidth = 2.5;
  ctx.lineCap = 'round';

  for (const [aId, bId] of POSE_CONNECTIONS) {
    const a = landmarks[aId];
    const b = landmarks[bId];
    if (!isVisible(a) || !isVisible(b)) continue;
    ctx.beginPath();
    ctx.moveTo(a.x * width, a.y * height);
    ctx.lineTo(b.x * width, b.y * height);
    ctx.stroke();
  }

  const nose = landmarks[POSE_INDEX.NOSE];
  const leftShoulder = landmarks[POSE_INDEX.LEFT_SHOULDER];
  const rightShoulder = landmarks[POSE_INDEX.RIGHT_SHOULDER];
  if (isVisible(nose) && isVisible(leftShoulder) && isVisible(rightShoulder)) {
    drawNeckAxis(ctx, width, height, nose, leftShoulder, rightShoulder);
  }

  for (const id of Object.values(POSE_INDEX)) {
    const lm = landmarks[id];
    if (!isVisible(lm)) continue;
    ctx.beginPath();
    ctx.arc(lm.x * width, lm.y * height, 4.5, 0, Math.PI * 2);
    ctx.fillStyle = hasAlert ? '#FF6B4A' : '#10B981';
    ctx.fill();
    ctx.lineWidth = 1.8;
    ctx.strokeStyle = '#FFFFFF';
    ctx.stroke();
  }
  ctx.restore();
}

export function MonitorView({ onBack }: MonitorViewProps) {
  const videoRef = useRef<HTMLVideoElement | null>(null);
  const canvasRef = useRef<HTMLCanvasElement | null>(null);
  const pipCanvasRef = useRef<HTMLCanvasElement | null>(null);
  const pipVideoRef = useRef<HTMLVideoElement | null>(null);
  const memeImgsRef = useRef<Partial<Record<DeviationType, HTMLImageElement>>>({});
  const landmarkerRef = useRef<PoseLandmarker | null>(null);
  const collectorRef = useRef(new CalibrationCollector(3000, 10));
  const comparatorRef = useRef(new PostureComparator());
  const calibrationRef = useRef<CalibrationData | null>(null);
  const calibratingRef = useRef(false);
  const showOverlayRef = useRef(true);

  const [isPreloading, setIsPreloading] = useState(true);
  const [modelReady, setModelReady] = useState(false);
  const [cameraActive, setCameraActive] = useState(false);
  const [isPiPActive, setIsPiPActive] = useState(false);
  const [cameraError, setCameraError] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState<SidebarTab>('calibrar');
  const [showOverlay, setShowOverlay] = useState(true);
  const [ragAlertsEnabled, setRagAlertsEnabled] = useState(true);
  const [isCalibrating, setIsCalibrating] = useState(false);
  const [calibProgress, setCalibProgress] = useState(0);
  const [calibMessage, setCalibMessage] = useState<string | null>(null);
  const [calibration, setCalibration] = useState<CalibrationData | null>(() => {
    try {
      const saved = localStorage.getItem(CALIBRATION_STORAGE_KEY);
      return saved ? (JSON.parse(saved) as CalibrationData) : null;
    } catch {
      return null;
    }
  });
  const [liveStatus, setLiveStatus] = useState<string>('Aguardando webcam');
  const [activeAlerts, setActiveAlerts] = useState<DeviationType[]>([]);
  const [measured, setMeasured] = useState<Record<DeviationType, number> | null>(null);
  const [ratios, setRatios] = useState<Record<DeviationType, number> | null>(null);

  useEffect(() => {
    showOverlayRef.current = showOverlay;
  }, [showOverlay]);

  useEffect(() => {
    calibrationRef.current = calibration;
    comparatorRef.current.setCalibration(calibration);
  }, [calibration]);

  // Pré-carrega imagens de alerta e escuta fechamento da janela Picture-in-Picture
  useEffect(() => {
    for (const [key, item] of Object.entries(DEVIATION_MEME_IMAGES) as [
      DeviationType,
      { src: string; caption: string },
    ][]) {
      const img = new Image();
      img.src = item.src;
      memeImgsRef.current[key] = img;
    }

    const pipVideo = pipVideoRef.current;
    const handleLeavePiP = () => setIsPiPActive(false);
    pipVideo?.addEventListener('leavepictureinpicture', handleLeavePiP);
    return () => {
      pipVideo?.removeEventListener('leavepictureinpicture', handleLeavePiP);
    };
  }, []);

  const togglePiP = async () => {
    const pipVideo = pipVideoRef.current;
    const pipCanvas = pipCanvasRef.current;
    if (!pipVideo || !pipCanvas || !document.pictureInPictureEnabled) return;

    try {
      if (document.pictureInPictureElement) {
        await document.exitPictureInPicture();
        setIsPiPActive(false);
        return;
      }

      if (!pipVideo.srcObject) {
        pipCanvas.width = 640;
        pipCanvas.height = 360;
        const stream = pipCanvas.captureStream(10);
        pipVideo.srcObject = stream;
      }
      await pipVideo.play();
      await pipVideo.requestPictureInPicture();
      setIsPiPActive(true);
    } catch {
      setIsPiPActive(false);
    }
  };

  // Tenta abrir PiP automaticamente ao sair da aba com a câmera ativa
  useEffect(() => {
    if (!cameraActive) return;

    const handleVisibility = () => {
      if (document.hidden && !document.pictureInPictureElement) {
        void togglePiP();
      }
    };

    document.addEventListener('visibilitychange', handleVisibility);

    if ('mediaSession' in navigator) {
      try {
        navigator.mediaSession.setActionHandler(
          'enterpictureinpicture' as MediaSessionAction,
          () => {
            if (!document.pictureInPictureElement) {
              void togglePiP();
            }
          },
        );
      } catch {
        // Navegador não suporta enterpictureinpicture automático
      }
    }

    return () => {
      document.removeEventListener('visibilitychange', handleVisibility);
      if ('mediaSession' in navigator) {
        try {
          navigator.mediaSession.setActionHandler(
            'enterpictureinpicture' as MediaSessionAction,
            null,
          );
        } catch {
          // Ignora
        }
      }
    };
  }, [cameraActive]);

  const stopCamera = () => {
    if (document.pictureInPictureElement) {
      void document.exitPictureInPicture();
      setIsPiPActive(false);
    }
    const stream = videoRef.current?.srcObject as MediaStream | null;
    stream?.getTracks().forEach((track) => track.stop());
    if (videoRef.current) videoRef.current.srcObject = null;
    setCameraActive(false);
    setLiveStatus('Webcam pausada');
  };

  const startCamera = async () => {
    setCameraError(null);
    try {
      const stream = await navigator.mediaDevices.getUserMedia({
        video: { width: { ideal: 1280 }, height: { ideal: 720 }, facingMode: 'user' },
        audio: false,
      });
      if (videoRef.current) {
        videoRef.current.srcObject = stream;
      }
      setCameraActive(true);
      setLiveStatus(
        calibrationRef.current ? 'Monitorando postura' : 'Pronto para calibrar',
      );
    } catch {
      setCameraError(
        'Não foi possível acessar a webcam. Verifique as permissões do navegador.',
      );
      setCameraActive(false);
    }
  };

  const startCalibration = () => {
    if (!cameraActive) {
      setCalibMessage('Ligue a webcam antes de iniciar a calibração.');
      return;
    }
    setCalibMessage(null);
    setCalibProgress(0);
    collectorRef.current.start();
    calibratingRef.current = true;
    setIsCalibrating(true);
    setActiveTab('calibrar');
  };

  // Preloading + inicialização do MediaPipe PoseLandmarker
  useEffect(() => {
    let cancelled = false;

    async function initMediaPipe() {
      try {
        const vision = await FilesetResolver.forVisionTasks(MEDIAPIPE_WASM_URL);
        let landmarker: PoseLandmarker;
        try {
          landmarker = await PoseLandmarker.createFromOptions(vision, {
            baseOptions: { modelAssetPath: POSE_MODEL_URL, delegate: 'GPU' },
            runningMode: 'VIDEO',
            numPoses: 1,
          });
        } catch {
          landmarker = await PoseLandmarker.createFromOptions(vision, {
            baseOptions: { modelAssetPath: POSE_MODEL_URL, delegate: 'CPU' },
            runningMode: 'VIDEO',
            numPoses: 1,
          });
        }
        if (!cancelled) {
          landmarkerRef.current = landmarker;
          setModelReady(true);
        }
      } catch {
        if (!cancelled) setModelReady(false);
      } finally {
        if (!cancelled) setIsPreloading(false);
      }
    }

    const fallbackTimer = window.setTimeout(() => {
      if (!cancelled) setIsPreloading(false);
    }, 2200);

    initMediaPipe();

    return () => {
      cancelled = true;
      window.clearTimeout(fallbackTimer);
      landmarkerRef.current?.close();
      stopCamera();
    };
  }, []);

  // Loop de inferência e desenho dos landmarks (~10 FPS)
  useEffect(() => {
    if (!cameraActive || !modelReady) return;

    let lastVideoTime = -1;
    const intervalId = window.setInterval(() => {
      const video = videoRef.current;
      const canvas = canvasRef.current;
      const landmarker = landmarkerRef.current;
      if (!video || !canvas || !landmarker || video.readyState < 2) return;
      if (video.currentTime === lastVideoTime) return;
      lastVideoTime = video.currentTime;

      if (canvas.width !== video.videoWidth || canvas.height !== video.videoHeight) {
        canvas.width = video.videoWidth || 640;
        canvas.height = video.videoHeight || 480;
      }

      const result = landmarker.detectForVideo(video, performance.now());
      const landmarks = (result.landmarks?.[0] as LandmarkPoint[] | undefined) ?? null;
      const features = extractFeatures(landmarks ?? undefined);

      if (calibratingRef.current) {
        const step = collectorRef.current.addSample(features);
        setCalibProgress(Math.round(step.progress * 100));
        if (step.done) {
          calibratingRef.current = false;
          setIsCalibrating(false);
          const finalized = collectorRef.current.finalize();
          if (finalized.ok) {
            localStorage.setItem(
              CALIBRATION_STORAGE_KEY,
              JSON.stringify(finalized.calibration),
            );
            setCalibration(finalized.calibration);
            setCalibMessage('Calibração concluída! Iniciando monitoramento.');
            setActiveTab('monitor');
          } else {
            setCalibMessage(finalized.reason);
          }
        }
      }

      const evaluation = comparatorRef.current.evaluate(features);
      setActiveAlerts(evaluation.activeAlerts);
      if ('measuredValues' in evaluation && evaluation.measuredValues) {
        setMeasured(evaluation.measuredValues);
      }
      if ('ratios' in evaluation && evaluation.ratios) {
        setRatios(evaluation.ratios);
      }
      if (!features.valid) {
        setLiveStatus('Confiança baixa — centralize rosto e ombros');
      } else if (!calibrationRef.current) {
        setLiveStatus('Landmarks detectados · Calibragem pendente');
      } else if (evaluation.activeAlerts.length > 0) {
        setLiveStatus('Desvio persistente identificado');
      } else {
        setLiveStatus('Postura adequada');
      }

      const ctx = canvas.getContext('2d');
      if (ctx) {
        if (showOverlayRef.current) {
          drawPoseOverlay(
            ctx,
            canvas.width,
            canvas.height,
            landmarks,
            calibrationRef.current,
            evaluation.activeAlerts.length > 0,
          );
        } else {
          ctx.clearRect(0, 0, canvas.width, canvas.height);
        }
      }

      // Atualiza o canvas espelhado usado pelo modo Miniatura (Picture-in-Picture)
      const pipCanvas = pipCanvasRef.current;
      if (pipCanvas) {
        if (pipCanvas.width !== canvas.width || pipCanvas.height !== canvas.height) {
          pipCanvas.width = canvas.width;
          pipCanvas.height = canvas.height;
        }
        const pctx = pipCanvas.getContext('2d');
        if (pctx) {
          pctx.save();
          pctx.scale(-1, 1);
          pctx.drawImage(video, -pipCanvas.width, 0, pipCanvas.width, pipCanvas.height);
          pctx.restore();

          if (showOverlayRef.current) {
            pctx.save();
            pctx.scale(-1, 1);
            pctx.drawImage(canvas, -pipCanvas.width, 0, pipCanvas.width, pipCanvas.height);
            pctx.restore();
          }

          if (evaluation.activeAlerts.length > 0) {
            const topAlert = evaluation.activeAlerts[0];
            pctx.save();
            pctx.strokeStyle = '#EF4444';
            pctx.lineWidth = 14;
            pctx.strokeRect(7, 7, pipCanvas.width - 14, pipCanvas.height - 14);

            const memeImg = memeImgsRef.current[topAlert];
            if (memeImg && memeImg.complete && memeImg.naturalWidth > 0) {
              const boxSize = Math.min(130, Math.round(pipCanvas.width * 0.24));
              const pad = 18;
              pctx.fillStyle = 'rgba(255, 255, 255, 0.94)';
              pctx.fillRect(pad, pad, boxSize, boxSize);
              pctx.drawImage(memeImg, pad + 4, pad + 4, boxSize - 8, boxSize - 8);
              pctx.strokeStyle = '#EF4444';
              pctx.lineWidth = 3;
              pctx.strokeRect(pad, pad, boxSize, boxSize);
            }
            pctx.restore();
          }
        }
      }
    }, 100);

    return () => window.clearInterval(intervalId);
  }, [cameraActive, modelReady]);

  if (isPreloading) {
    return (
      <div className="preload-screen">
        <div className="preload-card">
          <img src={ergoGif} alt="Carregando ErgoAI" className="preload-gif" />
          <h2>Preparando monitoramento local...</h2>
          <p>
            Carregando modelo MediaPipe PoseLandmarker e ambiente 100% privado no seu
            navegador.
          </p>
          <div className="preload-track" aria-hidden="true">
            <div className="preload-fill" />
          </div>
        </div>
      </div>
    );
  }

  const primaryCard = activeAlerts[0] ? KNOWLEDGE_CARDS[activeAlerts[0]] : null;

  return (
    <div className="monitor-workspace">
      <header className="monitor-topbar">
        <div className="monitor-topbar-left">
          <button
            type="button"
            className="btn-ink btn-white monitor-back-btn"
            onClick={() => {
              stopCamera();
              onBack();
            }}
          >
            ← Voltar
          </button>
          <div className="monitor-brand">
            <img src={ergoLogo} alt="ErgoAI" className="brand-logo" />
            <span>ErgoAI Monitor</span>
          </div>
        </div>

        <div className="monitor-segmented">
          <button
            type="button"
            className={`monitor-seg-btn ${activeTab === 'calibrar' ? 'active' : ''}`}
            onClick={() => setActiveTab('calibrar')}
          >
            1. Calibrar
          </button>
          <button
            type="button"
            className={`monitor-seg-btn ${activeTab === 'monitor' ? 'active' : ''}`}
            onClick={() => setActiveTab('monitor')}
          >
            2. Monitorar
          </button>
          <button
            type="button"
            className={`monitor-seg-btn ${activeTab === 'setup' ? 'active' : ''}`}
            onClick={() => setActiveTab('setup')}
          >
            3. Foto Setup
          </button>
        </div>

        <div className={`monitor-status-pill ${cameraActive ? 'online' : ''}`}>
          <i className="dot-status" />
          <span>{cameraActive ? liveStatus : 'Aguardando webcam'}</span>
        </div>
      </header>

      <main className="monitor-layout">
        {/* Barra lateral esquerda branca: Coordenadas ao Vivo */}
        <aside className="monitor-sidebar">
          <div className="sidebar-block">
            <h3>Coordenadas ao Vivo</h3>
            <div className="monitor-metrics-list">
              <div
                className={`monitor-metric-item level-${getMetricLevel(ratios?.FORWARD_HEAD)}`}
              >
                <span>Pescoço / Anteriorização</span>
                <strong>
                  {measured ? `${measured.FORWARD_HEAD.toFixed(1)} %` : '-- %'}
                </strong>
              </div>
              <div
                className={`monitor-metric-item level-${getMetricLevel(ratios?.TOO_CLOSE)}`}
              >
                <span>Distância da Tela</span>
                <strong>
                  {measured ? `${measured.TOO_CLOSE.toFixed(1)} %` : '-- %'}
                </strong>
              </div>
              <div
                className={`monitor-metric-item level-${getMetricLevel(ratios?.SHOULDER_TILT)}`}
              >
                <span>Inclinação dos Ombros</span>
                <strong>
                  {measured ? `${measured.SHOULDER_TILT.toFixed(1)} %` : '-- %'}
                </strong>
              </div>
              <div
                className={`monitor-metric-item level-${getMetricLevel(ratios?.HEAD_TILT)}`}
              >
                <span>Inclinação do Rosto</span>
                <strong>
                  {measured ? `${measured.HEAD_TILT.toFixed(1)} °` : '-- °'}
                </strong>
              </div>
            </div>
          </div>

          <div className="sidebar-block">
            <h3>Status do Motor</h3>
            <div className="sidebar-chips">
              <span>{modelReady ? 'MediaPipe OK' : 'Carregando IA'}</span>
              <span>{calibration ? 'Calibrado' : 'Sem referência'}</span>
              <span>100% Local</span>
            </div>
          </div>
        </aside>

        {/* Centro: Vídeo + Controles logo abaixo */}
        <section className="monitor-center-stage">
          <div
            className={`monitor-stage-grid ${activeTab === 'calibrar' ? 'split-1x2' : ''}`}
          >
            <div className="monitor-video-frame">
              <video ref={videoRef} autoPlay playsInline muted className="monitor-video" />
              <canvas ref={canvasRef} className="monitor-canvas" />

              {!cameraActive && (
                <div className="monitor-video-fallback">
                  <img src={ergoLogo} alt="ErgoAI" className="cam-fallback-logo" />
                  <h2>
                    {activeTab === 'calibrar'
                      ? 'Etapa 1: Ligue a webcam para calibrar'
                      : 'Câmera pronta para iniciar'}
                  </h2>
                  <p>
                    {cameraError ??
                      'Autorize a webcam para visualizar os pontos do MediaPipe em tempo real. Nenhuma imagem sai do navegador.'}
                  </p>
                  <button type="button" className="btn-ink btn-coral" onClick={startCamera}>
                    Ligar Webcam
                  </button>
                </div>
              )}
            </div>

            {activeTab === 'calibrar' && (
              <div className="calib-reference-panel">
                <span className="calib-ref-badge">Posição de Referência</span>
                <video
                  src={calibrationVideo}
                  autoPlay
                  loop
                  muted
                  playsInline
                  className="calib-ref-gif"
                />
                <p className="calib-ref-caption">
                  Fique alinhado como o personagem: costas apoiadas, olhar reto para a
                  webcam e ombros relaxados.
                </p>
              </div>
            )}
          </div>

          {/* Controles abaixo do vídeo */}
          <div className="monitor-controls-bar">
            <button
              type="button"
              className={`control-btn control-btn-cam ${cameraActive ? 'active' : ''}`}
              onClick={cameraActive ? stopCamera : startCamera}
            >
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round">
                <path d="M23 7l-7 5 7 5V7z" />
                <rect x="1" y="5" width="15" height="14" rx="2" ry="2" />
              </svg>
              <span>{cameraActive ? 'Pausar Webcam' : 'Ligar Webcam'}</span>
            </button>

            <button
              type="button"
              className={`control-btn control-btn-points ${showOverlay ? 'active' : ''}`}
              onClick={() => setShowOverlay((v) => !v)}
            >
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round">
                <circle cx="12" cy="12" r="9" />
                <circle cx="12" cy="12" r="3" />
              </svg>
              <span>Pontos: {showOverlay ? 'ON' : 'OFF'}</span>
            </button>

            <button
              type="button"
              className={`control-btn control-btn-rag ${ragAlertsEnabled ? 'active' : ''}`}
              onClick={() => setRagAlertsEnabled((v) => !v)}
            >
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round">
                <path d="M18 8A6 6 0 0 0 6 8c0 7-3 9-3 9h18s-3-2-3-9" />
                <path d="M13.73 21a2 2 0 0 1-3.46 0" />
              </svg>
              <span>Alertas RAG: {ragAlertsEnabled ? 'ON' : 'OFF'}</span>
            </button>

            <button
              type="button"
              className={`control-btn control-btn-mode ${activeTab === 'calibrar' ? 'active' : ''}`}
              onClick={() => setActiveTab(activeTab === 'calibrar' ? 'monitor' : 'calibrar')}
            >
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round">
                <path d="M12 2v4M12 18v4M4.93 4.93l2.83 2.83M16.24 16.24l2.83 2.83M2 12h4M18 12h4" />
              </svg>
              <span>{activeTab === 'calibrar' ? 'Ir para Monitorar' : 'Calibrar Postura'}</span>
            </button>

            <button
              type="button"
              className={`control-btn control-btn-pip ${isPiPActive ? 'active' : ''}`}
              onClick={togglePiP}
              disabled={!cameraActive}
              title="Abre janela flutuante no canto da tela para acompanhar em outras abas"
            >
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round">
                <rect x="2" y="4" width="20" height="16" rx="2" />
                <rect x="11" y="11" width="9" height="7" rx="1" />
              </svg>
              <span>{isPiPActive ? 'Fechar Miniatura' : 'Miniatura (PiP)'}</span>
            </button>
          </div>

          {/* Elementos ocultos usados para gerar o stream da janela Picture-in-Picture */}
          <canvas ref={pipCanvasRef} style={{ display: 'none' }} />
          <video
            ref={pipVideoRef}
            muted
            playsInline
            style={{ display: 'none' }}
          />
        </section>

        {/* Barra lateral direita branca: Somente Alertas e Dicas de Postura */}
        <aside className="monitor-sidebar">
          {activeTab === 'calibrar' ? (
            <>
              <div className="sidebar-block">
                <h3>Guia para Calibrar</h3>
                <div className="calib-guide-box">
                  <ol className="calib-guide-steps">
                    <li>Apoie as costas confortavelmente na cadeira.</li>
                    <li>Olhe reto para a tela na altura dos olhos.</li>
                    <li>Mantenha ombros relaxados e alinhados por 3s.</li>
                  </ol>
                </div>

                {isCalibrating && (
                  <div style={{ marginTop: '0.75rem' }}>
                    <div className="preload-track">
                      <div
                        className="preload-fill"
                        style={{
                          animation: 'none',
                          transform: `scaleX(${calibProgress / 100})`,
                        }}
                      />
                    </div>
                    <small style={{ color: 'var(--text-muted)', fontWeight: 700 }}>
                      Coletando referência... {calibProgress}%
                    </small>
                  </div>
                )}

                {calibMessage && (
                  <p className="calib-feedback-msg">{calibMessage}</p>
                )}
              </div>

              <div style={{ display: 'flex', flexDirection: 'column', gap: '0.55rem' }}>
                <button
                  type="button"
                  className="btn-ink btn-primary"
                  style={{ width: '100%' }}
                  onClick={cameraActive ? startCalibration : startCamera}
                  disabled={isCalibrating}
                >
                  {!cameraActive
                    ? 'Ligar Webcam'
                    : isCalibrating
                      ? 'Calibrando (3s)...'
                      : 'Iniciar Calibração (3s)'}
                </button>
                {calibration && (
                  <button
                    type="button"
                    className="btn-ink btn-white"
                    style={{ width: '100%' }}
                    onClick={() => setActiveTab('monitor')}
                  >
                    Ir para Monitoramento
                  </button>
                )}
              </div>
            </>
          ) : (
            <div className="sidebar-block" style={{ flex: 1 }}>
              <h3>Alertas &amp; Dicas de Postura</h3>
              {ragAlertsEnabled && primaryCard && activeAlerts[0] && (
                <div className="alert-meme-card">
                  <img
                    src={DEVIATION_MEME_IMAGES[activeAlerts[0]].src}
                    alt={primaryCard.titulo}
                    className="alert-meme-img"
                  />
                  <p className="alert-meme-caption">
                    {DEVIATION_MEME_IMAGES[activeAlerts[0]].caption}
                  </p>
                </div>
              )}
              <div className="monitor-rag-box">
                {!ragAlertsEnabled ? (
                  'Alertas e dicas de postura pausados no momento.'
                ) : primaryCard ? (
                  <>
                    <strong
                      style={{
                        display: 'block',
                        marginBottom: '0.35rem',
                        color: 'var(--coral)',
                      }}
                    >
                      {primaryCard.titulo}
                    </strong>
                    <p style={{ marginBottom: '0.5rem' }}>{primaryCard.orientacaoCurta}</p>
                    <p style={{ marginBottom: '0.5rem', color: 'var(--ink)', fontWeight: 600 }}>
                      Dica: {primaryCard.acaoRecomendada}
                    </p>
                    <small style={{ opacity: 0.75 }}>{primaryCard.fonte}</small>
                  </>
                ) : (
                  <>
                    <strong style={{ display: 'block', marginBottom: '0.35rem', color: '#059669' }}>
                      Postura alinhada
                    </strong>
                    <p>
                      Seus ombros, pescoço e inclinação estão dentro da referência
                      calibrada. Quando um desvio persistir, os alertas e dicas
                      aparecerão aqui.
                    </p>
                  </>
                )}
              </div>
            </div>
          )}
        </aside>
      </main>
    </div>
  );
}
