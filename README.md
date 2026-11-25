# Challenge 2 — Inimigos do Prompt

> **Status:** README provisório (proposta inicial do projeto, sujeita à aprovação do tema e ajustes ao longo das entregas).

## Assistente de IA para Ergonomia e Pausas Ativas

- **Desafio:** Desafio 2 — *Big Idea*: Qualidade de Vida
- **Essential Question:** Como um sistema de IA pode ajudar estudantes e profissionais que trabalham sentados a tomar decisões preventivas sobre ergonomia e pausas, com recomendações rastreáveis a fontes oficiais e sem substituir um profissional de saúde?

---

## Problema

Quem estuda ou programa por horas seguidas sofre com postura inadequada, sedentarismo e dores, e quase ninguém sabe exatamente o que ajustar no próprio posto de trabalho.

## Stakeholders

- **Estudantes e desenvolvedores:** público-alvo direto (facilidade para entrevistas e testes com usuários).
- **Profissionais de saúde e ergonomia:** referência para validação das recomendações e limites de escopo.

## Solução Proposta

O usuário envia uma foto do posto de trabalho (mesa, cadeira, monitor, notebook) e descreve sua rotina. O sistema indica o que ajustar e quando fazer pausas, sempre citando a fonte oficial que embasa cada recomendação.

### Por que esse tema?

- **Evidência pública citável:** a princípio com base na NR-17 e em recomendações da OMS sobre atividade física/sedentarismo (textos e versões atuais a confirmar).
- **Multimodalidade natural:** análise visual da foto do posto de trabalho (prevista para a Semana 4).
- **Validação objetiva:** permite definição clara de métricas para recuperação, geração, visão e segurança.
- **Escopo seguro:** menor risco clínico em comparação a temas como saúde mental ou nutrição, além de evitar o tema alimentação.

---

## Arquitetura e Roadmap

- **Semanas 2/3:** Construção do RAG sobre normas e guias + comparação **LLM puro vs. RAG**.
- **Semana 3:** Arquitetura **multiagente**:
  - **Agente de Visão:** interpreta o posto de trabalho a partir da imagem.
  - **Agente RAG:** recupera trechos e diretrizes rastreáveis nas fontes oficiais.
  - **Agente Planejador:** organiza ajustes ergonômicos e rotina de pausas.
  - **Agente Crítico de Segurança:** barra respostas fora do escopo ou sem respaldo nas fontes.
- **Semana 4:** Agente de visão multimodal analisando a foto do posto de trabalho.
- **Semanas 5/6:** Integração completa, bateria de testes e relatório final.

---

## Métricas de Avaliação

| Dimensão | Métricas / Critérios |
| :--- | :--- |
| **Recuperação (RAG)** | *Hit rate* e MRR em perguntas com resposta de referência |
| **Geração** | Fidelidade às fontes e taxa de alucinação (LLM puro vs. RAG) |
| **Visão** | Concordância do agente com checklist de ergonomia aplicado pela equipe em fotos rotuladas |
| **Segurança** | Taxa de recusa correta em perguntas fora do escopo (ex.: diagnóstico, tratamento) |

---

## Riscos e Limitações

- **LGPD e Privacidade:** fotos podem conter o rosto do usuário ou detalhes do ambiente residencial. A proposta é orientar a fotografar apenas o posto de trabalho e definir regras claras de retenção e descarte das imagens.
- **Análise por foto estática:** a avaliação postural a partir de uma única imagem possui limitações naturais; a precisão real será medida empiricamente em vez de assumida.
- **Não substitui atendimento profissional:** o sistema não substitui avaliação ergonômica presencial nem atendimento médico/fisioterapêutico; relatos de dor persistente devem ser encaminhados a um profissional de saúde.

---

## Documentação

- [Especificação de Requisitos (ErgoAI v1.0)](./docs/especificacao-requisitos.md)
- [Roteiro de Implementação do Protótipo](./docs/roteiro-prototipo.md)
- [Política de Privacidade e Proteção na Foto do Setup](./docs/privacidade-foto-setup.md)

---

## Como Rodar o Protótipo Localmente (MacBook / Windows / Linux)

O protótipo em `prototipo/` roda 100% no navegador utilizando a webcam local e `@mediapipe/tasks-vision` (nenhuma imagem é enviada ao servidor).

**Com Python 3 (nativo no macOS):**
```bash
python3 -m http.server 8000 --directory prototipo
```

**Ou com Node.js:**
```bash
npx serve prototipo -l 8000
```

Em seguida, acesse no navegador (`Chrome`, `Edge` ou `Firefox`):
```text
http://localhost:8000
```

1. Clique em **Ligar Webcam e Carregar IA** e autorize a câmera.
2. **Etapa 1:** Ajuste sua postura confortável na cadeira e clique em **Regular / Calibrar Postura Ideal (3s)**.
3. **Etapa 2:** O algoritmo passa a comparar sua postura atual com a silhueta ideal calibrada e emite alertas apenas para desvios persistentes.

---

## Sugestão de Frentes de Trabalho

1. **Base de conhecimento + RAG + avaliação**
2. **Orquestração dos agentes**
3. **Agente de visão**
4. **Interface e integração**

*(Distribuição a ser fechada após a aprovação do tema.)*
