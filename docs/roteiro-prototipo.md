# Roteiro de Implementação do Protótipo — ErgoAI

Este documento descreve, passo a passo, a arquitetura e a implementação do protótipo funcional do **ErgoAI**, projetado para rodar **100% localmente no navegador** (compatível com macOS/MacBook, Windows e Linux) respeitando o requisito de privacidade (**RNF02**: nenhuma imagem da webcam sai da máquina).

---

## Visão Geral do Fluxo em Duas Etapas

1. **Etapa 1 — Regulagem / Calibração da Postura Ideal (`RF04`, `RN02`, `RNF04`):**
   - O usuário autoriza o acesso à webcam (`RF02`, `RN01`), ajusta sua cadeira/tela e pressiona **Regular / Calibrar Postura Ideal (3s)**.
   - Durante 3 segundos, o sistema coleta amostras válidas e calcula a **mediana estatística** de sua referência individual, travando um "esqueleto fantasma" (linha tracejada em ciano) na tela.
2. **Etapa 2 — Monitoramento e Comparação Contínua (`RF05`–`RF11`, `RF14`, `RF17`, `RF19`):**
   - A cada ~100 ms (~10 FPS), o algoritmo extrai os pontos atuais, suaviza o sinal com filtro exponencial (EMA), compara com a referência calibrada e aplica **histerese + persistência temporal** antes de disparar alertas ligados a **Cartões de Conhecimento** rastreáveis.

---

## Passo a Passo Técnico da Implementação

### Passo 1 — Captura Local da Webcam (`prototipo/js/app.js`)
- A câmera é solicitada explicitamente após ação do usuário (`startCameraAndSession`) via `navigator.mediaDevices.getUserMedia({ video: { width: { ideal: 640 }, height: { ideal: 480 }, facingMode: 'user' }, audio: false })`.
- Resolução `640x480` garante rapidez na inferência sem perda de precisão geométrica.
- O elemento `<video>` é exibido espelhado via CSS (`transform: scaleX(-1)`) junto ao `<canvas>` sobreposto.

### Passo 2 — Detecção de Landmarks com MediaPipe e Filtro de Confiança (`prototipo/js/app.js` e `prototipo/js/posture-engine.js`)
- Utiliza `@mediapipe/tasks-vision` (`PoseLandmarker` com `pose_landmarker_lite.task`) via WebAssembly + WebGL (`delegate: 'GPU'`, com fallback automático para `'CPU'`).
- A função `extractFeatures(landmarks)` valida os 5 pontos essenciais (`NOSE = 0`, `LEFT_EYE = 2`, `RIGHT_EYE = 5`, `LEFT_SHOULDER = 11`, `RIGHT_SHOULDER = 12`):
  - **Filtro de confiança (`RN04`, `RN05`):** se `avgConfidence < 0.55` ou `minConfidence < 0.40` (ou se `shoulderWidth < 0.06` / `eyeDist < 0.015`), o quadro é marcado como `LOW_CONFIDENCE` e nenhuma classificação conclusiva é emitida.

### Passo 3 — Extração das 4 Variáveis Geométricas Normalizadas (`extractFeatures`)
Para lidar com diferentes alturas, tamanhos de tela e distâncias da câmera do MacBook, o motor calcula razões adimensionais e ângulos:

1. **Anteriorização da Cabeça / "Postura Camarão" (`FORWARD_HEAD`):**
   - Razão vertical pescoço-ombros normalizada pela largura dos ombros:
     $$\text{neckHeightRatio} = \frac{\text{midShoulderY} - \text{nose.y}}{\text{shoulderWidth}}$$
   - Reforço de profundidade relativa:
     $$\text{noseDepthDelta} = \text{midShoulderZ} - \text{nose.z}$$
   - Quando a pessoa curva o tronco ou projeta a cabeça para a frente, `neckHeightRatio` diminui e `noseDepthDelta` aumenta em relação à referência calibrada.
2. **Aproximação Excessiva da Tela (`TOO_CLOSE`):**
   - Em vez de usar apenas a distância entre os olhos (limitação citada na Seção 6 da especificação), combina a escala da distância interocular (**60%**) com a escala da largura aparente dos ombros (**40%**) frente ao valor calibrado:
     $$\text{proximityScale} = 0{,}6 \cdot \frac{\text{eyeDist}}{\text{eyeDist}_{\text{ref}}} + 0{,}4 \cdot \frac{\text{shoulderWidth}}{\text{shoulderWidth}_{\text{ref}}}$$
3. **Inclinação Lateral dos Ombros (`SHOULDER_TILT`):**
   - Diferença absoluta em graus entre o ângulo atual da linha dos ombros e o ângulo calibrado (`shoulderAngleDeg`).
4. **Inclinação Lateral da Cabeça (`HEAD_TILT`):**
   - Diferença absoluta em graus entre o ângulo atual da linha dos olhos e o ângulo calibrado (`headAngleDeg`).

### Passo 4 — Calibração da Postura Ideal (`CalibrationCollector`)
- Durante `3000 ms` (exigindo ao menos `10` quadros válidos), `CalibrationCollector` armazena todas as métricas e os pontos de referência (`[0, 2, 5, 7, 8, 11, 12]`).
- Na finalização (`finalize()`), calcula a **mediana** (`median(...)`) de cada métrica e coordenada para descartar oscilações pontuais.
- O resultado é salvo localmente (`localStorage`, sem imagens) e desenhado como contorno tracejado ciano no `<canvas>`.

### Passo 5 — Comparação Contínua, EMA e Histerese (`PostureComparator`)
- **Suavização EMA (`emaAlpha = 0.28`):** reduz tremor natural quadro a quadro.
- **Limiares base (`BASE_THRESHOLDS`) multiplicados pelo fator de tolerância (`toleranceFactor`, padrão `1.00x`):**
  - `FORWARD_HEAD`: `16.0%`
  - `TOO_CLOSE`: `20.0%`
  - `SHOULDER_TILT`: `7.5°`
  - `HEAD_TILT`: `10.0°`
- **Persistência temporal e histerese (`RF07`, `RNF06`, `RN03`):**
  - Um alerta só entra no estado `ALERT_PERSISTENT` quando o desvio permanece acima de `thresholdOn` por todo o tempo de persistência configurado (padrão `4.0s`).
  - Para sair do alerta, o usuário precisa corrigir a postura abaixo de `thresholdOff = thresholdOn * 0.78` por `1200 ms`, evitando oscilação de alertas na borda do limiar.

### Passo 6 — Cartões de Conhecimento, Feedback, Dashboard e Auditoria
- **Cartões de Conhecimento (`prototipo/js/knowledge-cards.js`):** exibem orientações determinísticas sem depender de LLM (`RN10`) com citação da fonte e trecho de evidência (**NR-17 — Portaria MTP nº 423/2021** e **OMS 2020**), cumprindo `RF09`, `RF14` e `RNF08`, além do aviso de escopo não médico (`RF20`, `RN07`).
- **Feedback (`RF10`, `RF11`, `RN09`):** marcar **"👎 Falso Alerta (+Tolerância)"** eleva o fator de tolerância em `+0.10x` (limitado ao teto seguro de `1.60x`).
- **Pausa Ativa (`RF21`) e Painel (`RF17`, `RF18`, `RNF09`):** cronômetro de pausa configurável (incluindo modo demo de `10s`), estatísticas da sessão, histórico salvo localmente sem imagens e botão **Limpar Histórico Local**.
- **Modo Auditoria (`RF19`, `RNF14`):** exibe em tempo real latência de inferência (`ms`), confiança dos pontos, métricas de referência vs. suavizadas e log cronológico de decisões.

---

## Como Executar Localmente no MacBook (ou Windows / Linux)

A API da webcam (`getUserMedia`) exige `http://localhost` ou `https://` (não funciona abrindo `file://` diretamente).

No terminal, a partir da raiz do repositório:

```bash
python3 -m http.server 8000 --directory prototipo
```

Depois, abra no navegador (**Chrome**, **Edge** ou **Firefox**):

```text
http://localhost:8000
```

> **Dica para MacBook:** Ao testar notificações em segundo plano enquanto trabalha em outro app, ative a caixa **"Notificações do navegador"** nas preferências do painel e permita notificações quando o navegador solicitar.
