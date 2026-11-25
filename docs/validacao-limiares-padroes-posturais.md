# Validação Heurística de Limiares, Latência e Evolução Pós-MVP do Motor Postural

**Escopo:** Issue #13 — Frente 3 (Visão Computacional & Análise Multimodal — Prioridade 3 Pós-MVP)  
**Requisitos relacionados:** RF04–RF09, RNF01, RNF06, RNF07, RN03–RN05 e [SPEC.md](../SPEC.md) (§7.1–§7.3, §13.1 e §13.3 — Experimentos 2 e 3)

---

## 1. Escopo e Transparência Metodológica (Sintético vs. Coleta Real)

> **Aviso de Transparência (`SPEC.md` §19.3 e §19.5):**
> 1. **Validação Determinística em Cenários Sintéticos Parametrizados:** Os experimentos descritos neste documento validam matematicamente as fórmulas geométricas, a máquina de estados temporal (EMA + histerese + persistência de `4000 ms`) e a ablação de pesos sobre **séries temporais sintéticas de landmarks** (geradas em memória por `build_validation_dataset()` em [`evals/posture_heuristics_eval.py`](../evals/posture_heuristics_eval.py) e testadas diretamente no motor TypeScript real em [`frontend/src/posture-engine/postureEngine.test.ts`](../frontend/src/posture-engine/postureEngine.test.ts)). Eles constituem um **baseline sintético de regressão e verificação heurística**, não substituindo ensaios clínicos ou coletas de campo com voluntários reais.
> 2. **Escopo das Medições de Latência (`RNF01 <= 500 ms`):** Os tempos medidos automaticamente nos relatórios (`~0.01 ms` médio, `< 0.05 ms` máximo) referem-se **exclusivamente ao tempo de CPU do motor geométrico determinístico** (`extractFeatures` + `PostureComparator.evaluate`). A inferência completa no navegador inclui adicionalmente a execução do `@mediapipe/tasks-vision` (`PoseLandmarker`), cujo tempo depende da GPU/CPU do dispositivo cliente e não é simulado pelo runner offline.

---

## 2. Evolução Pós-MVP Implementada (`postureEngine.ts` v1.1.0-post-mvp)

1. **Novos Padrões Posturais Determinísticos:**
   - **`ELEVATED_SHOULDERS` (Ombros Elevados / Tensão de Trapézio):** mede a elevação bilateral da linha média dos ombros (`midShoulderY`) normalizada pela largura biacromial descontando eventual descida da cabeça (`noseY`). Quando o encurtamento cervical decorre da subida isolada dos ombros (sem avanço em $Z$ nem queda do nariz), o motor desconta essa elevação do cálculo de `FORWARD_HEAD`, evitando falsos positivos cruzados.
   - **`TRUNK_ROTATION` (Rotação Axial de Tronco):** combina a variação de profundidade relativa entre os ombros ($\Delta z = z_{\text{esq}} - z_{\text{dir}}$) com o estreitamento projetivo 2D da largura dos ombros **compensado pela escala interocular (`shoulderScale / eyeScale`)** e condicionado a $\Delta z \ge 3\%$, garantindo que o simples afastamento linear do usuário em relação à webcam não dispare falso alerta de rotação.
   - **`PROLONGED_ABSENCE` (Ausência Prolongada do Posto):** detecta afastamento contínuo ($\ge 60\text{ s}$ sem landmarks válidos), registra pausa de recuperação e limpa os acumuladores de desvios posturais ativos.
2. **Múltiplos Perfis de Calibração (`notebook` vs. `external_monitor`):**
   - Persistência independente em `localStorage` para os perfis calibrados (`ergoai_calibration_profiles_v1`) e para o perfil ativo selecionado (`ergoai_active_profile_v1`), preservando a chave legada (`ergoai_calibration_v1`) exclusivamente para retrocompatibilidade do perfil `notebook`.

---

## 3. Ablação Heurística de `TOO_CLOSE` (60% Olhos / 40% Ombros)

Conforme documentado no `SPEC.md` §7.1 (Condição 2), a distância interocular isolada sofre com pequenos giros de cabeça, enquanto a largura dos ombros isolada varia durante a abdução de braços ao digitar. A escala composta utilizada é:

$$\text{proximityScale} = 0{,}60 \cdot \frac{d_{\text{olhos}}}{d_{\text{olhos, ref}}} + 0{,}40 \cdot \frac{L_{\text{ombros}}}{L_{\text{ombros, ref}}}$$

$$\text{TOO\_CLOSE (\%)} = \max\left(0,\; (\text{proximityScale} - 1) \times 100\right)$$

### Resultados da Ablação Sintética (`thresholdOn = 18.0%`)

| Configuração de Pesos | Precision | Recall | F1-score | False Positive Rate (FPR) | Comportamento Observado nos Casos de Borda |
| :--- | :---: | :---: | :---: | :---: | :--- |
| `100% Olhos / 0% Ombros` | `0.6667` | `0.6667` | `0.6667` | `0.5000` | Falha quando o usuário aproxima o tronco virando levemente o rosto e gera falso positivo em jitter interocular. |
| `0% Olhos / 100% Ombros` | `0.6667` | `0.6667` | `0.6667` | `0.5000` | Gera falso alerta ao abrir os cotovelos para digitar e perde inclinação cervical para frente com tronco recuado. |
| `50% Olhos / 50% Ombros` | `1.0000` | `0.6667` | `0.8000` | `0.0000` | Subestima a aproximação quando a cabeça avança em direção ao monitor mais rápido que a linha dos ombros (`17.0% < 18.0%`). |
| **`60% Olhos / 40% Ombros (ErgoAI)`** | **`1.0000`** | **`1.0000`** | **`1.0000`** | **`0.0000`** | **Equilíbrio ótimo no benchmark sintético:** captura avanço cefálico e de tronco mantendo imunidade a abdução de braços ou jitter facial isolado. |

---

## 4. Tabela de Limiares e Perfis de Calibração

| Código do Padrão | Descrição | Unidade | Limiar Base (`thresholdOn`) | Banda de Saída (`thresholdOff = 0.78x`) | Mult. Perfil `notebook` | Mult. Perfil `external_monitor` |
| :--- | :--- | :---: | :---: | :---: | :---: | :---: |
| `FORWARD_HEAD` | Anteriorização da Cabeça ("Camarão") | `%` | `18.0%` | `14.04%` | `1.05x` (`18.9%`) | `0.95x` (`17.1%`) |
| `TOO_CLOSE` | Aproximação Excessiva da Tela (60/40) | `%` | `18.0%` | `14.04%` | `1.00x` (`18.0%`) | `0.95x` (`17.1%`) |
| `SHOULDER_TILT` | Inclinação Lateral dos Ombros | `%` | `25.0%` | `19.50%` | `1.00x` (`25.0%`) | `0.95x` (`23.75%`) |
| `HEAD_TILT` | Inclinação Lateral da Cabeça | `°` | `14.0°` | `10.92°` | `1.00x` (`14.0°`) | `0.95x` (`13.3°`) |
| `ELEVATED_SHOULDERS` | Ombros Elevados (Tensão de Trapézio) | `%` | `14.0%` | `10.92%` | `1.00x` (`14.0%`) | `0.95x` (`13.3%`) |
| `TRUNK_ROTATION` | Rotação Axial de Tronco / Ombros | `%` | `22.0%` | `17.16%` | `1.05x` (`23.1%`) | `0.92x` (`20.24%`) |

### Desempenho na Bateria Sintética de 12 Cenários Temporais (`RNF07`)

A bateria gerada em memória (`build_validation_dataset()`) avalia os 6 desvios persistentes ($> 4000\text{ ms}$), a detecção de ausência prolongada ($\ge 60\text{ s}$), posturas neutras nos dois perfis (`notebook` e `external_monitor`), movimentos momentâneos ($2500\text{ ms} < 4000\text{ ms}$, testando `RN03`), quadros de baixa confiança (`visibility = 0.30 < 0.40`, testando `RN04`/`RN05`) e ruído de abdução de braços:

- **Acurácia nos Cenários Sintéticos:** `1.0000` (12/12)
- **Macro Precision / Recall / F1-score:** `1.0000`
- **Macro False Positive Rate (FPR):** `0.0000`

---

## 5. Medição de Latência do Motor Determinístico (`RNF01 <= 500 ms`)

| Escopo Aferido | Natureza do Dado | Latência Média | Latência P95 | Latência P99 | Latência Máxima | Meta RNF01 |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: |
| **Motor Postural Determinístico (`extractFeatures` + EMA + Histerese, 290 frames)** | **Medido experimentalmente** | `~0.008 ms` | `~0.014 ms` | `~0.017 ms` | `~0.022 ms` | $\le 500\text{ ms}$ |
| **Orçamento restante para captura + MediaPipe PoseLandmarker Lite no navegador** | **Orçamento disponível** | — | — | — | **`> 499.9 ms` livres** | $\le 500\text{ ms}$ |

Como o cálculo geométrico e a máquina de estados consomem menos de `0.05 ms` por quadro, praticamente todo o orçamento de `500 ms` do `RNF01` permanece livre para a inferência WebGL/WASM do MediaPipe no navegador.

---

## 6. Como Executar os Testes (Frontend TypeScript + Evals Python)

A partir da raiz do repositório:

```bash
# 1. Testes unitários Vitest diretamente sobre o motor TypeScript real (postureEngine.ts)
npm --prefix frontend test

# 2. Build e checagem de tipos do frontend
npm --prefix frontend run build

# 3. Validação heurística, ablação TOO_CLOSE e benchmark de latência em Python (gera cenários em memória)
python -m evals.posture_heuristics_eval --out evals/results/posture_heuristics_report.json
python -m unittest discover -s evals/tests -p "test_*.py" -v
```
