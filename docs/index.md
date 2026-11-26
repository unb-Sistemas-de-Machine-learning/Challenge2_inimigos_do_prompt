---
hide:
  - navigation
---

# ErgoAI — Documentação Técnica

<div class="ergo-doc-hero">
  <div class="ergo-doc-hero-grid">
    <div>
      <div class="ergo-hero-badge">
        <span class="ergo-hero-badge-tag">MediaPipe + RAG</span>
        <span>Privacidade 100% Local · Challenge 2</span>
      </div>
      <h1>
        Cuide da sua postura em <span class="ergo-highlight">tempo real</span>
      </h1>
      <p class="ergo-hero-lead">
        O <strong>ErgoAI</strong> rastreia coordenadas de ombros, pescoço e inclinação da cabeça diretamente no navegador via webcam, detecta desvios persistentes com histerese e oferece recomendações educativas fundamentadas na <strong>NR-17</strong> e na <strong>OMS</strong> com citações literais verificadas.
      </p>
      <div class="ergo-hero-actions">
        <a href="especificacao-requisitos/" class="ergo-btn ergo-btn-amber">Especificação de Requisitos</a>
        <a href="roteiro-prototipo/" class="ergo-btn ergo-btn-white">▶ Roteiro do Protótipo</a>
      </div>
      <div class="ergo-hero-trust">
        <span>● Processamento 100% local (RN01/RNF02)</span>
        <span>✓ Recomendações com exact_quote</span>
        <span>✓ Trava de segurança clínica (RF20)</span>
      </div>
    </div>
    <div class="ergo-mascot-card">
      <img src="assets/img/ergo.gif" alt="Mascote ErgoAI monitorando a postura no computador" />
      <span class="ergo-mascot-caption">ErgoAI · Assistente Postural</span>
    </div>
  </div>
</div>

---

## Visão Geral da Arquitetura

<div class="ergo-cards-grid">
  <div class="ergo-card">
    <span class="ergo-tag ergo-tag-coral">P0 · Navegador</span>
    <h3>1. Frontend &amp; Motor Postural</h3>
    <p>
      Executa <code>@mediapipe/tasks-vision</code> (<code>PoseLandmarker</code>) 100% localmente em React + TypeScript para extrair coordenadas posturais, calibração por mediana, suavização EMA e histerese sem enviar frames ao servidor.
    </p>
  </div>
  <div class="ergo-card">
    <span class="ergo-tag ergo-tag-amber">P1 · FastAPI + RAG</span>
    <h3>2. Backend &amp; Safety Validator</h3>
    <p>
      API em FastAPI com recuperação híbrida (vetorial ChromaDB + lexical BM25), geração fundamentada com verificação literal de <code>exact_quote</code> e bloqueio estrito de escopo médico/clínico.
    </p>
  </div>
  <div class="ergo-card">
    <span class="ergo-tag ergo-tag-emerald">NR-17 &amp; OMS</span>
    <h3>3. Base de Conhecimento</h3>
    <p>
      Corpus normativo e científico indexado em <code>knowledge_base/</code> com metadados rastreáveis (documento, seção, página e trecho literal) e cartões locais para fallback offline imediato.
    </p>
  </div>
  <div class="ergo-card">
    <span class="ergo-tag ergo-tag-amber">P2 · RNF07</span>
    <h3>4. Avaliação Empírica</h3>
    <p>
      Baterias reproduzíveis em <code>evals/</code> aferindo Precision, Recall, F1-score, FPR e latência do motor postural (<code>&le; 500 ms</code>), além de Hit Rate, MRR e fidelidade do RAG.
    </p>
  </div>
</div>

---

## Por Dentro do ErgoAI (Interface & Fluxo Visual)

A documentação reflete a mesma identidade visual **neo-brutalista** da aplicação web — combinando fundo creme (`#FAF6F0`), laranja-coral (`#FF6B4A`), amarelo-âmbar (`#FFD15C`) e bordas em tinta preta (`#161616`):

<div class="ergo-showcase-grid">
  <div class="ergo-shot-card">
    <img src="assets/img/preview-landing.png" alt="Landing Page do ErgoAI com banner coral e destaque Tempo Real" />
    <div class="ergo-shot-body">
      <strong>Landing Page &amp; Proposta de Valor</strong>
      <span>Apresentação do fluxo 100% local no navegador, etapas de calibração e aviso de privacidade no topo.</span>
    </div>
  </div>
  <div class="ergo-shot-card">
    <img src="assets/img/preview-monitor.png" alt="Workspace de Monitoramento Postural em Tempo Real do ErgoAI" />
    <div class="ergo-shot-body">
      <strong>Workspace de Monitoramento &amp; Calibração</strong>
      <span>Painel em 3 colunas com coordenadas ao vivo, guia de posição de referência, controles de overlay/PiP e alertas RAG.</span>
    </div>
  </div>
  <div class="ergo-shot-card">
    <img src="assets/img/ergo-front.gif" alt="Demonstração da calibração frontal com pontos do MediaPipe" />
    <div class="ergo-shot-body">
      <strong>Mapeamento Frontal MediaPipe</strong>
      <span>Rastreamento geométrico de olhos, nariz e linha biacromial para estabelecer a linha de base individual do usuário.</span>
    </div>
  </div>
</div>

---

## Princípios Invioláveis do Sistema

| Princípio | Requisito | Garantia Técnica |
| :--- | :---: | :--- |
| **Privacidade da Webcam** | `RNF02` / `RNF09` | Zero frames da webcam saem do navegador; nenhuma imagem pessoal é persistida em disco, banco ou logs. |
| **Tempo Real Independente de LLM** | `RNF01` / `RN10` | A detecção geométrica e a histerese rodam a `<= 500 ms` localmente e funcionam mesmo com o backend offline. |
| **Rastreabilidade Literal** | `RF14` / `RNF08` | Toda orientação do RAG exige `exact_quote` validado literalmente contra o chunk recuperado. |
| **Não Diagnóstico Clínico** | `RF20` / `RN07` | O *Safety Validator* recusa solicitações de diagnóstico médico, prescrição ou tratamento fisioterapêutico. |

---

## Documentos Principais

- **[Especificação de Requisitos](especificacao-requisitos.md)** — Requisitos funcionais (`RF01–RF21`), não funcionais (`RNF01–RNF14`), regras de negócio (`RN01–RN10`), contratos de dados e arquitetura C4.
- **[Roteiro de Implementação do Protótipo](roteiro-prototipo.md)** — Guia prático do fluxo da interface, motor postural determinístico e integração entre os módulos.
- **[Política de Privacidade na Foto do Setup](privacidade-foto-setup.md)** — Regras de retenção zero, remoção de EXIF e mascaramento local antes do envio opcional.
- **[Cartões de Conhecimento e Esquema de Dados](cartoes-e-esquema.md)** — Estrutura dos cartões normativos com `exact_quote` e contratos de sessão/coleta.
- **[Protocolo de Coleta de Landmarks](protocolo-coleta-landmarks.md)** — Procedimento ético e técnico para gravação anonimizada de coordenadas posturais.
- **[Protocolo de Avaliação Quantitativa (RNF07)](protocolo-avaliacao-rnf07.md)** — Métricas de Precision, Recall, F1-score, FPR, Hit Rate e MRR.
