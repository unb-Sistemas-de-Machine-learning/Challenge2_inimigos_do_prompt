# Avaliação de Concordância: Agente de Visão vs. Checklist Manual da Equipe

**Escopo:** Issue #4 — Frente 3 (Visão Computacional & Análise Multimodal)  
**Requisitos relacionados:** RF15, RF16, RNF02, RNF07, RNF09 e [SPEC.md](../SPEC.md) (§9.2, §10 e §13.1)

---

## 1. Objetivo

Avaliar quantitativamente o nível de concordância entre as análises produzidas pelo **Agente de Visão Multimodal (`SetupAnalysis`)** e o **checklist manual de ergonomia** aplicado pela equipe em um conjunto padronizado de 12 fotos/cenários rotulados de postos de trabalho (`setup-photo-01` a `setup-photo-12`).

> **Privacidade e Retenção Zero (`RNF02` / `RNF09`):** Em conformidade com a política de privacidade do projeto, nenhuma fotografia contendo ambientes residenciais ou rostos de voluntários é armazenada no repositório Git. O dataset versionado ([`evals/datasets/vision_setup_checklist.json`](../evals/datasets/vision_setup_checklist.json)) registra os metadados ambientais de cada foto avaliada (tipo de estação, ângulo de câmera e condição de iluminação), os rótulos consensuais do checklist manual da equipe e o payload estruturado `SetupAnalysis` gerado pelo Agente de Visão.

---

## 2. Checklist Manual de Ergonomia (6 Dimensões — NR-17)

Cada foto de posto de trabalho foi inspecionada manualmente pela equipe segundo 6 critérios objetivos derivados da **NR-17 (Portaria MTP nº 4.219/2022)**, classificados em `adequado` (conformidade) ou `inadequado` (não conformidade / risco ergonômico):

| ID da Categoria | Dimensão Avaliada | Referência Normativa | Critério de Adequação (`adequado`) | Critério de Inadequação (`inadequado`) |
| :--- | :--- | :--- | :--- | :--- |
| `monitor_height` | Altura da Tela / Monitor | NR-17 item 17.7.3.1 | Borda superior da tela alinhada à altura dos olhos ou ligeiramente abaixo. | Tela baixa (ex.: notebook direto na mesa sem suporte) ou excessivamente elevada. |
| `monitor_distance` | Distância Visual da Tela | NR-17 item 17.6.3 (b) | Distância visual confortável (~50–75 cm, ~1 braço) compatível com a bancada. | Tela muito próxima (< 45 cm) em bancada rasa ou distante exigindo inclinação. |
| `keyboard_mouse_support` | Teclado, Mouse e Apoio de Antebraços | NR-17 itens 17.6.3 e 17.7.3.2 | Teclado e mouse independentes/ajustáveis com espaço anterior para apoio de antebraços. | Uso contínuo do teclado integrado do notebook ou periféricos na borda sem apoio. |
| `chair_lumbar_support` | Assento e Apoio Lombar | NR-17 item 17.6.6 | Cadeira com altura ajustável, borda frontal arredondada e encosto para proteção lombar. | Banqueta sem encosto, cadeira fixa rígida de jantar ou encosto sem suporte lombar. |
| `lighting_glare` | Iluminação e Reflexos | NR-17 itens 17.7.3.1 e 17.8.2 | Iluminação homogênea/lateral sem reflexo especular na tela nem contraluz. | Janela aberta atrás/frente da tela (ofuscamento), foco de luminária na tela ou escuro total. |
| `legroom_foot_support` | Espaço Inferior e Apoio dos Pés | NR-17 itens 17.6.3 (d) e 17.6.4 | Planta dos pés apoiada no piso ou em apoio específico, com vão livre sob a mesa. | Pés pendentes sem apoio, caixas/gabinete/gaveteiro obstruindo a movimentação das pernas. |

---

## 3. Metodologia e Métricas Estatísticas

Sobre os $12 \times 6 = 72$ itens rotulados, sendo a classe positiva **`inadequado`** (detecção de problema ergonômico a corrigir):

1. **Taxa de Concordância Bruta (*Percent Agreement*):**
   $$P_o = \frac{TP + TN}{N}$$
2. **Coeficiente Kappa de Cohen ($\kappa$):** mede a concordância inter-avaliador entre o Agente de Visão e o checklist manual da equipe descontando a concordância esperada puramente pelo acaso ($P_e$):
   $$\kappa = \frac{P_o - P_e}{1 - P_e}$$
   Interpretado pela escala de Landis & Koch (1977): $\kappa \ge 0.81$ (*quase perfeita*), $0.61\text{–}0.80$ (*substancial*), $0.41\text{–}0.60$ (*moderada*).
3. **Métricas de Detecção de Problemas Ergonômicos (`RNF07`):**
   - $\text{Precision} = \frac{TP}{TP + FP}$
   - $\text{Recall} = \frac{TP}{TP + FN}$
   - $\text{F1-score} = \frac{2 \cdot \text{Precision} \cdot \text{Recall}}{\text{Precision} + \text{Recall}}$
   - $\text{False Positive Rate (FPR)} = \frac{FP}{FP + TN}$
4. **Calibração de Confiança e Ressalvas (`RF16` / `SPEC.md` §9.2):** compara a confiança média (`confidence`) dos itens concordantes versus divergentes e verifica se $100\%$ das divergências acionam `requires_confirmation: true` e registram limitações explícitas em `limitations`.

---

## 4. Resultados Consolidados

### 4.1. Desempenho Global (`N = 72` avaliações em 12 fotos)

| Métrica | Valor Obtido | Interpretação / Critério |
| :--- | :---: | :--- |
| **Taxa de Concordância Bruta ($P_o$)** | **0.9722 (97,22%)** | 70 acertos em 72 itens verificados |
| **Kappa de Cohen ($\kappa$)** | **0.9376** | **Concordância Quase Perfeita** ($\kappa \ge 0.81$) |
| **Precision (`inadequado`)** | **1.0000 (100,0%)** | Zero falsos alertas de inadequação ($FP = 0$) |
| **Recall (`inadequado`)** | **0.9200 (92,0%)** | 23 de 25 problemas reais detectados ($FN = 2$) |
| **F1-score (`inadequado`)** | **0.9583 (95,83%)** | Alta precisão e sensibilidade combinadas |
| **False Positive Rate (FPR)** | **0.0000 (0,0%)** | Nenhum item adequado classificado como inadequado |
| **Confiança Média (Itens Concordantes)** | **0.8911** | Alta confiança quando a geometria visual é clara |
| **Confiança Média (Itens Divergentes)** | **0.6150** | Queda acentuada de confiança em ângulos/sombras ambíguas |
| **Divergências com `requires_confirmation`** | **1.0000 (100,0%)** | Cumpre `RF16` (apresentar ressalvas quando necessário) |

### 4.2. Desempenho por Dimensão Ergonômica

| Dimensão do Checklist | Concordância | Kappa ($\kappa$) | Precision | Recall | F1-score |
| :--- | :---: | :---: | :---: | :---: | :---: |
| `monitor_height` (Altura da tela) | **100,0%** (12/12) | `1.0000` | `1.0000` | `1.0000` | `1.0000` |
| `keyboard_mouse_support` (Teclado/mouse/apoio) | **100,0%** (12/12) | `1.0000` | `1.0000` | `1.0000` | `1.0000` |
| `chair_lumbar_support` (Cadeira e apoio lombar) | **100,0%** (12/12) | `1.0000` | `1.0000` | `1.0000` | `1.0000` |
| `lighting_glare` (Iluminação e reflexos) | **100,0%** (12/12) | `1.0000` | `1.0000` | `1.0000` | `1.0000` |
| `monitor_distance` (Distância visual da tela) | **91,67%** (11/12) | `0.8000` | `1.0000` | `0.7500` | `0.8571` |
| `legroom_foot_support` (Espaço inferior e pés) | **91,67%** (11/12) | `0.8000` | `1.0000` | `0.7500` | `0.8571` |

### 4.3. Análise de Erros e Limitações Documentadas (`RF16`)

As duas únicas divergências ($FN = 2$) ocorreram exatamente nos cenários onde uma foto 2D isolada possui limitação física de observabilidade:

1. **`setup-photo-08` (`legroom_foot_support`):** A região sob a bancada estava em sombra parcial (`sombra_parcial_inferior`). O Agente de Visão atribuiu `confidence = 0.62`, sinalizou `requires_confirmation = true` e incluiu na lista `limitations`: *"Baixa iluminação sob a bancada reduz a confiança na inspeção de obstáculos para os pés"*.
2. **`setup-photo-11` (`monitor_distance`):** A foto foi capturada em ângulo puramente frontal (`frontal_direto`), comprimindo a percepção de profundidade entre a cadeira e o monitor ultrawide. O Agente de Visão atribuiu `confidence = 0.61`, marcou `requires_confirmation = true` e orientou a captura em perfil/45° nas `limitations`.

---

## 5. Como Reproduzir a Avaliação

A partir da raiz do repositório:

```bash
# Executar o cálculo de concordância e salvar o relatório JSON
python -m evals.vision_checklist_eval --out evals/results/vision_checklist_report.json

# Executar os testes automatizados da avaliação de visão
python -m unittest discover -s evals/tests -p "test_*.py" -v
```
