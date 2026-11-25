/**
 * Contratos de dados da API (SPEC.md §9) e do armazenamento local (SPEC.md §11.2) do ErgoAI.
 *
 * - Contratos JSON de API/eventos: inglês e snake_case (espelho de backend/app/schemas/contracts.py).
 * - Armazenamento local (IndexedDB / LocalStorage): inglês e camelCase (SPEC.md §11.2).
 * - Datas em ISO 8601 (string). NUNCA armazenar imagens da webcam (RNF02).
 * - Mudanças de formato no armazenamento local devem incrementar SCHEMA_VERSION e DB_VERSION.
 */

export type CameraMode = 'frontal' | 'lateral';
export type FeedbackType = 'helpful' | 'false_alert';

/** A lista oficial de códigos de desvio fica em knowledge_base/cards/_tipos_desvio.yaml. */
export type DeviationCode = string;

// ============================================================================
// Contratos JSON de API e eventos — SPEC.md §9 (snake_case)
// Espelho de backend/app/schemas/contracts.py
// ============================================================================

export interface PostureFeatures {
  head_forward_offset: number;
  trunk_inclination: number;
  shoulder_asymmetry: number;
  apparent_face_scale: number;
}

export interface PostureClassification {
  label: string;
  confidence: number;
}

/** SPEC.md §9.1 */
export interface PostureEvent {
  event_id: string;
  timestamp: string;
  camera_mode: CameraMode;
  landmarks_confidence: number;
  duration_minutes: number;
  features: PostureFeatures;
  classification: PostureClassification;
}

export interface EvidenceItem {
  document_id: string;
  source: string;
  section?: string;
  page?: number;
  exact_quote: string;
}

/** SPEC.md §9.3 */
export interface GroundedRecommendation {
  recommendation_id: string;
  recommendation: string;
  category: string;
  confidence: number;
  evidence: EvidenceItem[];
}

/** SPEC.md §9.4 */
export interface SafetyDecision {
  approved: boolean;
  scope: string;
  evidence_verified: boolean;
  requires_professional: boolean;
  reason: string;
}

export interface SetupObservation {
  category: string;
  description: string;
  confidence: number;
  requires_confirmation: boolean;
}

/** SPEC.md §9.2 */
export interface SetupAnalysis {
  analysis_id: string;
  observations: SetupObservation[];
  limitations: string[];
}

export interface ChatRequest {
  question: string;
}

export interface FeedbackRequest {
  event_id: string;
  feedback_type: FeedbackType;
}

// ============================================================================
// Armazenamento local (IndexedDB / LocalStorage) — SPEC.md §11.2 (camelCase)
// ============================================================================

export const SCHEMA_VERSION = 2;

export const DB_NAME = 'ergoai';
export const DB_VERSION = 2;
export const STORES = {
  sessions: 'sessions',
  events: 'events',
  feedbacks: 'feedbacks',
  userParameters: 'userParameters',
} as const;

export interface UserSettings {
  cameraMode: CameraMode;
  notificationEnabled: boolean;
  breakIntervalMinutes: number;
  postureSensitivity: number;
}

/** Valores de referência da calibração: apenas números (ângulos/razões), sem imagens. */
export interface Calibration {
  createdAt: string;
  referenceFeatures: Record<string, number>;
  cameraMode: CameraMode;
  visionModelVersion?: string;
}

/**
 * Cada ajuste de tolerância cria uma NOVA versão (nunca sobrescreve a anterior),
 * para os resultados serem reproduzíveis. Ajustes de feedback (RF11) só afetam estas
 * tolerâncias locais; a bateria de avaliação (RNF07) usa parâmetros congelados à parte.
 */
export interface UserParameters {
  id: string; // referenciado por Session.parametersVersion
  createdAt: string;
  origin: 'default' | 'feedback_adjustment' | 'manual';
  tolerances: Record<string, number>;
}

export interface Session {
  id: string;
  startedAt: string;
  endedAt?: string;
  durationSeconds: number;
  alertsCount: number;
  postureMetrics: Record<string, number>;
  parametersVersion?: string; // id de UserParameters
  calibration?: Calibration;
  appVersion?: string;
}

export interface SessionEvent {
  id: string;
  sessionId: string;
  timestamp: string;
  type: DeviationCode;
  durationMs: number;
  confidence: number; // 0 a 1 (RN04/RN05)
  triggeredAlert: boolean;
  /** Rastreabilidade: qual cartão e qual versão da base geraram a orientação mostrada. */
  cardId: string | null;
  cardVersion: string | null;
  knowledgeBaseVersion: string | null;
}

/** Opinião do usuário. NÃO é rótulo verdadeiro: serve ao ajuste de tolerância, não à métrica (RNF07). */
export interface UserFeedback {
  id: string;
  eventId: string;
  type: FeedbackType;
  createdAt: string;
}
