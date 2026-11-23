/**
 * Contratos de dados da sessão e da API do ErgoAI (alinhados ao SPEC.md §9 e §11).
 *
 * - Dados locais (IndexedDB / LocalStorage): nomes em inglês e camelCase (SPEC.md §11.2).
 * - Contratos JSON de API/eventos: nomes em inglês e snake_case (SPEC.md §9).
 * - Datas em ISO 8601 (string). NUNCA armazenar imagens da webcam (RNF02).
 * - Mudanças de formato devem incrementar SCHEMA_VERSION e DB_VERSION.
 */
export const SCHEMA_VERSION = 2;

export const DB_NAME = "ergoai";
export const DB_VERSION = 2;
export const STORES = {
  sessions: "sessions",
  events: "events",
  feedbacks: "feedbacks",
  userParameters: "userParameters",
} as const;

export type CameraMode = "frontal" | "lateral";

/** A lista oficial de códigos de desvio fica em cards/_tipos_desvio.yaml. */
export type DeviationType = string;

/** @deprecated Use DeviationType. Mantido para compatibilidade com schema/coleta.ts. */
export type TipoDesvio = DeviationType;

export type FeedbackType = "helpful" | "false_alert";

// ============================================================================
// Armazenamento local — SPEC.md §11.2 (camelCase)
// ============================================================================

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
  origin: "default" | "feedback_adjustment" | "manual";
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
  type: DeviationType;
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

// ============================================================================
// Contratos JSON de API e eventos — SPEC.md §9 (snake_case)
// Espelho dos modelos Pydantic do backend; manter snake_case exatamente como no SPEC.
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
  features: PostureFeatures;
  classification: PostureClassification;
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

export interface RecommendationEvidence {
  document_id: string;
  source: string;
  section: string;
  page: number;
  exact_quote: string;
}

/** SPEC.md §9.3 */
export interface GroundedRecommendation {
  recommendation_id: string;
  recommendation: string;
  category: string;
  confidence: number;
  evidence: RecommendationEvidence[];
}

/** SPEC.md §9.4 */
export interface SafetyDecision {
  approved: boolean;
  scope: string;
  evidence_verified: boolean;
  requires_professional: boolean;
  reason: string;
}
