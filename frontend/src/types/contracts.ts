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

export interface PostureEvent {
  event_id: string;
  timestamp: string;
  camera_mode: 'frontal' | 'lateral';
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

export interface GroundedRecommendation {
  recommendation_id: string;
  recommendation: string;
  category: string;
  confidence: number;
  evidence: EvidenceItem[];
}
