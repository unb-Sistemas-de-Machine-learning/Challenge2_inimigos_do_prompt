/**
 * Esquema dos dados da sessão (armazenados localmente no navegador; nunca imagens).
 * Nomes dos campos seguem o combinado pelo grupo (snake_case). Datas em ISO 8601 (string).
 * Proposta: o grupo valida. Mudanças de formato devem incrementar SCHEMA_VERSION.
 */
export const SCHEMA_VERSION = 1;

export const DB_NAME = "ergoai";
export const DB_VERSION = 1;
export const STORES = {
  sessoes: "sessoes",
  eventos: "eventos",
  feedbacks: "feedbacks",
  parametros: "parametros_usuario",
} as const;

/** A lista oficial de tipos fica em cards/_tipos_desvio.yaml (os cartões partem dela). */
export type TipoDesvio = string;

export type Classificacao = "util" | "falso_alerta";

/** Valores de referência da calibração: apenas números (ângulos/razões), sem imagens. */
export interface Calibracao {
  criada_em: string;
  referencia: Record<string, number>;
  versao_modelo_visao: string;
}

/**
 * Cada ajuste de tolerância vira uma NOVA versão (nunca sobrescreve a anterior),
 * para os resultados serem reproduzíveis. Ajustes de feedback (RF11) só afetam estas
 * tolerâncias locais; a bateria de avaliação (RNF07) usa parâmetros congelados à parte.
 */
export interface ParametrosUsuario {
  id: string; // é o "versao_parametros" referenciado em Sessao
  criado_em: string;
  origem: "padrao" | "ajuste_feedback" | "manual";
  tolerancias: Record<string, number>;
}

export interface Sessao {
  id: string;
  inicio: string;
  fim: string | null;
  versao_parametros: string; // id de ParametrosUsuario
  calibracao: Calibracao;
  versao_app: string;
}

export interface Evento {
  id: string;
  sessao_id: string;
  timestamp: string;
  tipo: TipoDesvio;
  duracao_ms: number;
  confianca: number; // 0 a 1 (RN04/RN05)
  virou_alerta: boolean;
  /** Rastreabilidade: qual cartão e qual versão da base geraram a orientação mostrada. */
  cartao_id: string | null;
  versao_cartao: string | null;
  versao_base: string | null;
}

/** Opinião do usuário. NÃO é rótulo verdadeiro: serve ao ajuste de tolerância, não à métrica (RNF07). */
export interface Feedback {
  evento_id: string;
  classificacao: Classificacao;
  timestamp: string;
}
