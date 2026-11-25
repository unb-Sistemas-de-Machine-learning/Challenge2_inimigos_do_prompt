/**
 * Formato das gravações de landmarks para montar o conjunto de avaliação (RNF07).
 * NUNCA inclui imagens. Ver docs/protocolo-coleta-landmarks.md.
 * Proposta: o grupo valida. Um arquivo .jsonl por gravação (uma amostra por linha) + um JSON de rótulos.
 */
import type { DeviationCode } from './contracts';

export const COLETA_SCHEMA_VERSION = 1;

export interface Ponto {
  x: number; // coordenadas normalizadas conforme saída do modelo
  y: number;
  z: number;
  visibilidade: number; // confiança do ponto (equivalente a visibility no MediaPipe)
}

/** Um quadro. "pose" guarda os pontos do corpo (o Pose Landmarker rastreia 33). Pontos do rosto: só se o grupo decidir. */
export interface AmostraLandmarks {
  t_ms: number; // tempo desde o início da gravação
  pose: Ponto[];
}

export interface CabecalhoGravacao {
  id_gravacao: string;
  id_voluntario: string; // código anônimo; a tabela de correspondência NÃO é guardada
  versao_consentimento: string;
  versao_modelo_visao: string;
  fps_medio: number;
  condicoes: {
    iluminacao: 'boa' | 'media' | 'ruim';
    posicao_camera: 'frontal' | 'outra';
    observacoes?: string;
  };
}

export type RotuloPostura = DeviationCode | 'postura_adequada' | 'movimento_momentaneo';

/** Segmento rotulado por UMA pessoa; cada gravação é rotulada por duas (ver protocolo). */
export interface RotuloSegmento {
  id_gravacao: string;
  inicio_ms: number;
  fim_ms: number;
  rotulo: RotuloPostura;
  anotador_id: string;
}
