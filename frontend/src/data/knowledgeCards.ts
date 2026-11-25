export type DeviationType =
  | 'FORWARD_HEAD'
  | 'TOO_CLOSE'
  | 'SHOULDER_TILT'
  | 'HEAD_TILT';

export type KnowledgeCardType = DeviationType | 'BREAK_NEEDED';

export interface KnowledgeCard {
  id: string;
  tipo: KnowledgeCardType;
  titulo: string;
  severidadeLabel: string;
  orientacaoCurta: string;
  acaoRecomendada: string;
  fonte: string;
  trechoEvidencia: string;
}

export const KNOWLEDGE_CARDS: Record<KnowledgeCardType, KnowledgeCard> = {
  FORWARD_HEAD: {
    id: 'CARD_FORWARD_HEAD',
    tipo: 'FORWARD_HEAD',
    titulo: 'Anteriorização da Cabeça ("Postura Camarão")',
    severidadeLabel: 'Desvio Cervical / Tronco',
    orientacaoCurta:
      'Sua cabeça projetou-se para a frente ou baixou em relação à linha calibrada dos ombros.',
    acaoRecomendada:
      'Recue o queixo suavemente ("queixo para trás"), apoie as costas no encosto da cadeira e eleve a tela se estiver olhando para baixo.',
    fonte:
      'NR-17 — Ergonomia (Portaria MTP nº 423/2021) — Mobiliário e Equipamentos de Trabalho com Telas',
    trechoEvidencia:
      'As condições e equipamentos de vídeo devem permitir que o trabalhador mantenha a cabeça e o pescoço em posturas neutras, com a borda superior da tela na altura dos olhos ou ligeiramente abaixo.',
  },
  TOO_CLOSE: {
    id: 'CARD_TOO_CLOSE',
    tipo: 'TOO_CLOSE',
    titulo: 'Aproximação Excessiva da Tela',
    severidadeLabel: 'Distância Visual',
    orientacaoCurta:
      'Você está significativamente mais próximo da webcam/tela do que na sua postura ideal calibrada.',
    acaoRecomendada:
      'Afaste o tronco para manter cerca de um braço de distância da tela e, se necessário, aumente o zoom do sistema em vez de inclinar o corpo para a frente.',
    fonte:
      'NR-17 — Ergonomia (Portaria MTP nº 423/2021) — Posicionamento de Telas e Conforto Visual',
    trechoEvidencia:
      'Os monitores e superfies de trabalho devem ser posicionados a uma distância confortável de visualização e sem reflexos, evitando posturas forçadas ou inclinação anterior do tronco.',
  },
  SHOULDER_TILT: {
    id: 'CARD_SHOULDER_TILT',
    tipo: 'SHOULDER_TILT',
    titulo: 'Desalinhamento Lateral dos Ombros',
    severidadeLabel: 'Simetria de Tronco',
    orientacaoCurta:
      'Um dos ombros está mais elevado ou caído do que na sua postura de referência.',
    acaoRecomendada:
      'Relaxe ambos os ombros, verifique se os antebraços estão apoiados de forma simétrica na mesa/apoios e evite apoiar o peso em apenas um lado.',
    fonte:
      'NR-17 — Ergonomia (Portaria MTP nº 423/2021) — Adaptação do Posto de Trabalho',
    trechoEvidencia:
      'O mobiliário do posto de trabalho deve permitir apoio correto dos segmentos corporais e movimentação livre, prevenindo tensões musculares prolongadas e assimetrias posturais.',
  },
  HEAD_TILT: {
    id: 'CARD_HEAD_TILT',
    tipo: 'HEAD_TILT',
    titulo: 'Inclinação Lateral da Cabeça',
    severidadeLabel: 'Alinhamento Cervical',
    orientacaoCurta:
      'A linha dos olhos está inclinada lateralmente em relação ao eixo calibrado.',
    acaoRecomendada:
      'Centralize o olhar no monitor principal e alinhe as orelhas horizontalmente para evitar sobrecarga unilateral na cervical.',
    fonte:
      'NR-17 — Ergonomia (Portaria MTP nº 423/2021) — Postura Neutra de Cabeça e Pescoço',
    trechoEvidencia:
      'Recomenda-se manter alinhamento neutro da região cervical frente ao plano de trabalho, evitando torções ou inclinações laterais mantidas por longos períodos.',
  },
  BREAK_NEEDED: {
    id: 'CARD_BREAK_NEEDED',
    tipo: 'BREAK_NEEDED',
    titulo: 'Pausa Ativa Recomendada',
    severidadeLabel: 'Tempo Prolongado Sentado',
    orientacaoCurta:
      'Você atingiu o intervalo configurado de trabalho contínuo sentado sem pausa ativa.',
    acaoRecomendada:
      'Levante-se por 2 a 5 minutos, olhe para um ponto distante para descansar a visão e faça uma caminhada leve ou alongamento suave.',
    fonte:
      'OMS — Diretrizes para Atividade Física e Comportamento Sedentário (2020) & NR-17 Cap. 17.4',
    trechoEvidencia:
      'Adultos devem limitar o tempo em comportamento sedentário e interromper períodos prolongados sentados com atividade física de qualquer intensidade ("todo movimento conta"). A NR-17 prevê pausas para recuperação psicofisiológica em atividades contínuas.',
  },
};

export const CLINICAL_DISCLAIMER =
  'Aviso de Escopo (RF20 / RN07): O ErgoAI realiza estimativas geométricas educativas por câmera frontal e não realiza diagnósticos médicos ou fisioterapêuticos. Em caso de dor persistente, procure um profissional de saúde.';
