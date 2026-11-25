import ergoLogo from '../../assets/img/ergoAI-fundo.jpeg';
import ergoPNG from '../../assets/img/ergo.gif';
import ergoFront from '../../assets/img/ergo-front.gif';
import { CLINICAL_DISCLAIMER } from '../data/knowledgeCards';

interface LandingPageProps {
  onStartMonitoring: () => void;
}

export function LandingPage({ onStartMonitoring }: LandingPageProps) {
  return (
    <div>
      <div className="top-announcement">
        <span>100% Local no Navegador</span> — Nenhuma imagem da webcam sai da sua máquina
      </div>

      <div className="navbar-wrapper">
        <header className="navbar">
          <a href="#top" className="brand-link">
            <img src={ergoLogo} alt="Logo ErgoAI" className="brand-logo" />
            <span>ErgoAI.</span>
          </a>

          <nav className="nav-links" aria-label="Navegação principal">
            <a href="#como-funciona">Como Funciona</a>
            <a href="#calibracao">Calibração</a>
            <a href="#rag">RAG &amp; Dicas</a>
            <a href="#setup">Setup</a>
          </nav>

          <button
            type="button"
            className="btn-ink btn-primary"
            onClick={onStartMonitoring}
          >
            Iniciar Monitoramento
          </button>
        </header>
      </div>

      <div className="hero-orange-band">
        <section id="top" className="hero">
          <div className="hero-badge">
            <span className="hero-badge-tag">MediaPipe + RAG</span>
            <span>Validação postural em tempo real</span>
          </div>

          <h1 className="hero-title">
            Cuide da sua postura 
            <br />em
            <span className="hero-highlight">tempo real</span>
          </h1>

          <p className="hero-subtitle">
            O ErgoAI rastreia coordenadas de ombro, pescoço e inclinação do rosto pela
            webcam, identifica desvios persistentes e usa RAG para explicar riscos e
            dicas práticas de ajuste.
          </p>

          <div className="hero-actions">
            <button
              type="button"
              className="btn-ink btn-coral"
              onClick={onStartMonitoring}
            >
              Iniciar Monitoramento
            </button>
            <a href="#como-funciona" className="btn-ink btn-white">
              ▶ Como Funciona
            </a>
          </div>

          <div className="hero-trust">
            <span>
              <i className="dot-emerald" /> Processamento 100% local
            </span>
            <span>✓ Dicas fundamentadas via RAG</span>
            <span>✓ Calibração individual</span>
          </div>
        </section>

        {/* Wave suave de transição para o início da seção Como Funciona */}
        <svg
          className="hero-wave-transition"
          viewBox="0 0 1440 160"
          preserveAspectRatio="none"
          fill="none"
          xmlns="http://www.w3.org/2000/svg"
          aria-hidden="true"
        >
          <path
            d="M0 95C320 140 620 42 960 22C1180 10 1340 34 1440 58V160H0V95Z"
            fill="#FFFFFF"
          />
        </svg>
      </div>

      <section id="como-funciona" className="how-section">
        <div className="how-card">
          <div className="how-image-frame">
            <img src={ergoPNG} alt="Mascote ErgoAI usando o computador" />
          </div>

          <div className="how-content">
            <h2>Como o ErgoAI funciona no seu dia a dia</h2>
            <p>
              Pensado para quem estuda ou programa por horas no computador, o sistema
              combina visão computacional local com um assistente via RAG para orientar
              ajustes preventivos sem enviar seu vídeo para a nuvem.
            </p>

            <div className="how-steps">
              <div className="how-step">
                <span className="step-num">1</span>
                <div>
                  <strong>Calibração da sua postura ideal</strong>
                  <span>
                    Você ajusta sua posição confortável na cadeira e grava os pontos de
                    referência de ombros, pescoço e rosto.
                  </span>
                </div>
              </div>

              <div className="how-step">
                <span className="step-num">2</span>
                <div>
                  <strong>Rastreamento contínuo por X minutos</strong>
                  <span>
                    O MediaPipe acompanha desvios persistentes (como cabeça projetada ou
                    ombros desalinhados) ignorando movimentos rápidos.
                  </span>
                </div>
              </div>

              <div className="how-step">
                <span className="step-num">3</span>
                <div>
                  <strong>Alertas interpretados com RAG</strong>
                  <span>
                    Quando o desvio persiste, o modelo interpreta as métricas e traz
                    riscos e dicas práticas para corrigir sua postura.
                  </span>
                </div>
              </div>
            </div>
          </div>
        </div>

        {/* Wave suave de transição para a seção de Calibração (amarelo) */}
        <svg
          className="section-wave-transition"
          viewBox="0 0 1440 160"
          preserveAspectRatio="none"
          fill="none"
          xmlns="http://www.w3.org/2000/svg"
          aria-hidden="true"
        >
          <path
            d="M0 70C360 15 680 135 1040 95C1220 75 1350 45 1440 28V160H0V70Z"
            fill="#FFD15C"
          />
        </svg>
      </section>

      <section id="calibracao" className="calib-section">
        <div className="calib-grid">
          <div className="calib-content">
            <span className="calib-pill">Etapa 1 · Calibração da Webcam</span>
            <h2>Como fica a calibração da sua câmera</h2>
            <p>
              Antes de iniciar o monitoramento, você olha normalmente para a tela por
              alguns segundos. O sistema mapeia os pontos-chave do seu rosto e ombros
              para criar uma referência personalizada — sem enviar nenhuma imagem.
            </p>

            <div className="calib-points">
              <div className="calib-point">
                <strong>Pontos mapeados na hora</strong>
                <span>
                  Olhos, nariz e linha dos ombros são detectados frontalmente pelo
                  MediaPipe direto no navegador.
                </span>
              </div>
              <div className="calib-point">
                <strong>Referência por mediana</strong>
                <span>
                  O cálculo descarta movimentos rápidos e fixa sua postura confortável
                  como linha base para os alertas.
                </span>
              </div>
              <div className="calib-point">
                <strong>Adaptação ao seu setup</strong>
                <span>
                  Funciona independente da altura da cadeira, distância do notebook ou
                  ângulo da webcam.
                </span>
              </div>
            </div>

            <div style={{ marginTop: '1.5rem' }}>
              <button
                type="button"
                className="btn-ink btn-coral"
                onClick={onStartMonitoring}
              >
                Testar Calibração Agora
              </button>
            </div>
          </div>

          <div className="calib-image-frame">
            <img
              src={ergoFront}
              alt="Exemplo de calibração frontal da webcam com pontos de rastreamento no ErgoAI"
            />
          </div>
        </div>
      </section>

      <footer
        style={{
          background: 'var(--amber)',
          padding: '0 1.5rem 2.5rem',
          textAlign: 'center',
          fontSize: '0.78rem',
          color: 'var(--ink)',
          opacity: 0.85,
        }}
      >
        <div style={{ maxWidth: '900px', margin: '0 auto' }}>{CLINICAL_DISCLAIMER}</div>
      </footer>
    </div>
  );
}
