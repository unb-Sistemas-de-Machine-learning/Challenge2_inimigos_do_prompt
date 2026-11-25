export type DeviationType =
  | 'FORWARD_HEAD'
  | 'TOO_CLOSE'
  | 'SHOULDER_TILT'
  | 'HEAD_TILT'
  | 'ELEVATED_SHOULDERS'
  | 'TRUNK_ROTATION';

export type KnowledgeCardType =
  | DeviationType
  | 'PROLONGED_ABSENCE'
  | 'BREAK_NEEDED';

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
      'NR-17 — Ergonomia (Portaria MTP nº 4.219/2022) — Item 17.7.3.1 (Equipamentos com Terminais de Vídeo)',
    trechoEvidencia:
      'Os equipamentos devem ter condições de mobilidade suficiente para permitir o ajuste da tela do equipamento à iluminação do ambiente, protegendo-a contra reflexos, e proporcionar corretos ângulos de visibilidade ao trabalhador.',
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
      'NR-17 — Ergonomia (Portaria MTP nº 4.219/2022) — Item 17.6.3 (b) (Mobiliário dos Postos de Trabalho)',
    trechoEvidencia:
      'Altura e características da superfície de trabalho compatíveis com o tipo de atividade, com a distância requerida dos olhos ao campo de trabalho e com a altura do assento.',
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
      'NR-17 — Ergonomia (Portaria MTP nº 4.219/2022) — Item 17.6.3 (a) (Posicionamento dos Segmentos Corporais)',
    trechoEvidencia:
      'Características dimensionais que possibilitem posicionamento e movimentação dos segmentos corporais de forma a não comprometer a saúde e não ocasionar amplitudes articulares excessivas ou posturas nocivas de trabalho.',
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
      'NR-17 — Ergonomia (Portaria MTP nº 4.219/2022) — Item 17.4.3 (a) (Prevenção de Posturas Nocivas)',
    trechoEvidencia:
      'Devem ser implementadas medidas de prevenção que evitem que os trabalhadores, ao realizar suas atividades, sejam obrigados a efetuar de forma contínua e repetitiva posturas extremas ou nocivas do tronco, do pescoço e da cabeça.',
  },
  ELEVATED_SHOULDERS: {
    id: 'CARD_ELEVATED_SHOULDERS',
    tipo: 'ELEVATED_SHOULDERS',
    titulo: 'Ombros Elevados (Tensão de Trapézio)',
    severidadeLabel: 'Sobrecarga Muscular Estática',
    orientacaoCurta:
      'Seus ombros estão contraídos e elevados em direção às orelhas sem projeção anterior da cabeça.',
    acaoRecomendada:
      'Solte o ar, deixe os ombros descerem suavemente e ajuste a altura dos apoios de braço ou da mesa para não digitar com os ombros suspensos.',
    fonte:
      'NR-17 — Ergonomia (Portaria MTP nº 4.219/2022) — Item 17.4.2 (Sobrecarga Muscular Estática)',
    trechoEvidencia:
      'Nas atividades que exijam sobrecarga muscular estática ou dinâmica do tronco, do pescoço, da cabeça, dos membros superiores e dos membros inferiores, devem ser adotadas medidas técnicas, organizacionais e/ou administrativas para eliminar ou reduzir essas sobrecargas.',
  },
  TRUNK_ROTATION: {
    id: 'CARD_TRUNK_ROTATION',
    tipo: 'TRUNK_ROTATION',
    titulo: 'Rotação Axial de Tronco / Ombros',
    severidadeLabel: 'Torção Postural',
    orientacaoCurta:
      'Seu tronco ou linha dos ombros está rotacionado em relação ao plano frontal da estação de trabalho.',
    acaoRecomendada:
      'Alinhe a cadeira e o teclado diretamente em frente ao monitor principal para evitar trabalhar com o tronco torcido por períodos prolongados.',
    fonte:
      'NR-17 — Ergonomia (Portaria MTP nº 4.219/2022) — Item 17.4.3 (a) e Item 17.6.3 (c)',
    trechoEvidencia:
      'As bancadas e mesas devem proporcionar área de trabalho de fácil alcance e visualização pelo trabalhador, evitando posturas extremas ou torções contínuas do tronco e do pescoço.',
  },
  PROLONGED_ABSENCE: {
    id: 'CARD_PROLONGED_ABSENCE',
    tipo: 'PROLONGED_ABSENCE',
    titulo: 'Ausência Prolongada Detectada (Pausa de Recuperação)',
    severidadeLabel: 'Recuperação / Ausência do Posto',
    orientacaoCurta:
      'Você permaneceu fora do enquadramento da estação pelo tempo mínimo de pausa de recuperação.',
    acaoRecomendada:
      'Excelente! O afastamento físico do posto interrompe o comportamento sedentário contínuo e limpa os alertas posturais acumulados.',
    fonte:
      'OMS (2020) — Diretrizes sobre Comportamento Sedentário & NR-17 Item 17.4.3.1',
    trechoEvidencia:
      'Adultos devem interromper períodos prolongados na posição sentada com pausas ativas. As pausas para recuperação psicofisiológica propiciam a variação de postura e redução da fadiga.',
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
