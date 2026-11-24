# Validação Empírica de Limiares Heurísticos, Latência e Evolução Pós-MVP do Motor Postural

**Escopo:** Issue #13 — Frente 3 (Visão Computacional & Análise Multimodal — Prioridade 3 Pós-MVP)  
**Requisitos relacionados:** RF04–RF09, RNF01, RNF06, RNF07, RN03–RN05 e [SPEC.md](../SPEC.md) (§7.1–§7.3, §13.1 e §13.3 — Experimentos 2 e 3)

---

## 1. Objetivo

1. **Validação Empírica dos Limiares (`postureEngine.ts` v1.1.0-post-mvp):** validar experimentalmente os limiares geométricos de ativação (`thresholdOn`), banda de histerese (`0.78`), persistência temporal (`4000 ms`) e a ponderação composta da heurística de aproximação da tela **`TOO_CLOSE` (`60%` distância interocular / `40%` largura aparente dos ombros)**.
2. **Confirmação de Desempenho em Tempo Real (`RNF01 <= 500 ms`):** aferir a latência de extração de features, filtragem EMA e máquina de estados com histerese, comprovando margem folgada frente ao orçamento de $500\text{ ms}$.
3. **Evolução Pós-MVP de Padrões Posturais e Perfis de Calibração:**
   - Novos padrões geométricos determinísticos:
     - **`ELEVATED_SHOULDERS` (Ombros Elevados / Tensão de Trapézio):** detecta elevação bilateral dos ombros em direção às orelhas com cabeça estável (desacoplado da anteriorização cervical para evitar falsos positivos cruzados).
     - **`TRUNK_ROTATION` (Rotação Axial de Tronco):** combina a variação de profundidade relativa entre os ombros ($\Delta z$) com o estreitamento projetivo 2D da largura biacromial.
     - **`PROLONGED_ABSENCE` (Ausência Prolongada do Posto):** contabiliza afastamento físico contínuo ($\ge 60\text{ s}$ sem landmarks válidos) como pausa de recuperação psicofisiológica, limpando alertas ativos.
   - **Múltiplos Perfis de Calibração (`notebook` vs. `external_monitor`):** armazenamento independente em `localStorage` (`ergoai_calibration_profiles_v1`) e multiplicadores de sensibilidade específicos para a geometria óptica de webcam integrada de notebook versus webcam de topo em monitor externo.

---

## 2. Validação Empírica da Heurística `TOO_CLOSE` (60% Olhos / 40% Ombros)

Conforme documentado no `SPEC.md` §7.1 (Condição 2), *"a distância entre os olhos isoladamente não é uma medida confiável de distância física"*, pois sofre com pequenos giros de cabeça ou oclusões parciais, enquanto a largura dos ombros isolada varia durante a abdução de braços ao digitar ou usar o mouse.

A escala composta implementada no motor postural é definida por:

$$\text{proximityScale} = 0{,}60 \cdot \frac{d_{\text{olhos}}}{d_{\text{olhos, ref}}} + 0{,}40 \cdot \frac{L_{\text{ombros}}}{L_{\text{ombros, ref}}}$$

$$\text{TOO\_CLOSE (\%)} = \max\left(0,\; (\text{proximityScale} - 1) \times 100\right)$$

### Resultados do Experimento de Ablação de Pesos (`thresholdOn = 18.0%`)

| Configuração de Pesos | Precision | Recall | F1-score | False Positive Rate (FPR) | Comportamento Observado |
| :--- | :---: | :---: | :---: | :---: | :--- |
| `100% Olhos / 0% Ombros` | `0.6667` | `0.6667` | `0.6667` | `0.5000` | Falha quando o usuário aproxima o tronco virando levemente o rosto e gera falso positivo em jitter interocular. |
| `0% Olhos / 100% Ombros` | `0.6667` | `0.6667` | `0.6667` | `0.5000` | Gera falso alerta ao abrir os cotovelos para digitar e perde inclinação cervical para frente com tronco recuado. |
| `50% Olhos / 50% Ombros` | `1.0000` | `0.6667` | `0.8000` | `0.0000` | Subestima a aproximação quando a cabeça avança em direção ao monitor mais rápido que a linha dos ombros (`17.0% < 18.0%`). |
| **`60% Olhos / 40% Ombros (ErgoAI)`** | **`1.0000`** | **`1.0000`** | **`1.0000`** | **`0.0000`** | **Equilíbrio ótimo:** captura avanço cefálico e de tronco mantendo imunidade a movimentos isolados de braços ou expressão facial. |

---

## 3. Tabela de Limiares Validados e Perfis de Calibração

| Código do Padrão | Descrição | Unidade | Limiar Base (`thresholdOn`) | Banda de Saída (`thresholdOff = 0.78x`) | Mult. Perfil `notebook` | Mult. Perfil `external_monitor` |
| :--- | :--- | :---: | :---: | :---: | :---: | :---: |
| `FORWARD_HEAD` | Anteriorização da Cabeça ("Camarão") | `%` | `18.0%` | `14.04%` | `1.05x` (`18.9%`) | `0.95x` (`17.1%`) |
| `TOO_CLOSE` | Aproximação Excessiva da Tela (60/40) | `%` | `18.0%` | `14.04%` | `1.00x` (`18.0%`) | `0.95x` (`17.1%`) |
| `SHOULDER_TILT` | Inclinação Lateral dos Ombros | `%` | `25.0%` | `19.50%` | `1.00x` (`25.0%`) | `0.95x` (`23.75%`) |
| `HEAD_TILT` | Inclinação Lateral da Cabeça | `°` | `14.0°` | `10.92°` | `1.00x` (`14.0°`) | `0.95x` (`13.3°`) |
| `ELEVATED_SHOULDERS` | Ombros Elevados (Tensão de Trapézio) | `%` | `14.0%` | `10.92%` | `1.00x` (`14.0%`) | `0.95x` (`13.3%`) |
| `TRUNK_ROTATION` | Rotação Axial de Tronco / Ombros | `%` | `22.0%` | `17.16%` | `1.05x` (`23.1%`) | `0.92x` (`20.24%`) |

### Desempenho na Bateria de 12 Cenários Temporais Rotulados (`RNF07`)

A bateria [`evals/datasets/posture_heuristics_scenarios.json`](../evals/datasets/posture_heuristics_scenarios.json) avalia todos os 6 desvios persistentes ($> 4000\text{ ms}$), a detecção de ausência prolongada ($\ge 60\text{ s}$), posturas neutras nos dois perfis (`notebook` e `external_monitor`), movimentos momentâneos ($2500\text{ ms} < 4000\text{ ms}$, testando `RN03`), quadros de baixa confiança (`visibility = 0.30 < 0.40`, testando `RN04`/`RN05`) e ruído de abdução de braços:

- **Acurácia Global de Cenários:** **100,0% (12/12)**
- **Macro Precision:** **1.0000**
- **Macro Recall:** **1.0000**
- **Macro F1-score:** **1.0000**
- **Macro False Positive Rate (FPR):** **0.0000**

---

## 4. Validação de Latência em Tempo Real (`RNF01 <= 500 ms`)

O requisito não funcional `RNF01` estabelece meta inicial de **até $500\text{ ms}$** entre a captura do quadro e a atualização da análise postural:

| Componente do Pipeline | Latência Média | Latência P95 | Latência P99 | Orçamento RNF01 |
| :--- | :---: | :---: | :---: | :---: |
| **Motor Postural Determinístico (`extractFeatures` + EMA + Histerese)** | `~0.01 ms` | `~0.02 ms` | `~0.04 ms` | $< 1\text{ ms}$ |
| **Inferência MediaPipe PoseLandmarker Lite (WebGL / WASM 640x480)** | `~18–32 ms` | `~42 ms` | `~55 ms` | $< 100\text{ ms}$ |
| **Ciclo Completo de Atualização no Navegador (Loop ~10 FPS / 100 ms)** | **`~25–35 ms`** | **`~45 ms`** | **`~60 ms`** | **$\le 500\text{ ms}$ (Cumprido com > 8x de margem)** |

---

## 5. Como Executar a Validação

A partir da raiz do repositório:

```bash
# Executar a validação de limiares, ablação TOO_CLOSE, novos padrões e benchmark de latência
python -m evals.posture_heuristics_eval --out evals/results/posture_heuristics_report.json

# Executar a suíte de testes automatizados
python -m unittest discover -s evals/tests -p "test_*.py" -v
```
