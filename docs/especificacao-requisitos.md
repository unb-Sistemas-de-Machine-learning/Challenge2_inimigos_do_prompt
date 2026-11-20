# Especificação de Requisitos — ErgoAI

**Sistema:** Sistema de IA para Ergonomia  
**Nome provisório:** ErgoAI  
**Versão:** 1.0  

---

## Objetivo do Sistema

Desenvolver um sistema web que utilize visão computacional e inteligência artificial para auxiliar usuários a monitorar sua postura durante o trabalho, identificar possíveis desvios posturais, recomendar pausas ativas e fornecer orientações fundamentadas em fontes confiáveis.

Este documento organiza os requisitos funcionais, não funcionais, regras de negócio e critérios de validação propostos para o MVP.

---

## 1. Requisitos Funcionais (RF)

Descrevem as funcionalidades e os serviços que o sistema deve oferecer.

| ID | Descrição | Prioridade |
| :--- | :--- | :--- |
| **RF01** | Permitir iniciar e encerrar uma sessão de monitoramento postural utilizando a webcam. | Alta |
| **RF02** | Solicitar permissão de acesso à webcam antes de iniciar a captura de imagens. | Alta |
| **RF03** | Detectar pontos de referência corporais (*landmarks*) por meio do MediaPipe. | Alta |
| **RF04** | Permitir calibração inicial para estabelecer uma referência postural individual. | Alta |
| **RF05** | Identificar possíveis desvios posturais com base nos pontos corporais e em critérios geométricos definidos. | Alta |
| **RF06** | Monitorar, no mínimo, anteriorização da cabeça, aproximação excessiva da tela e tempo prolongado sem pausas. | Alta |
| **RF07** | Utilizar filtros temporais e histerese para evitar alertas causados por alterações momentâneas. | Alta |
| **RF08** | Emitir notificações visuais quando identificar um possível desvio postural persistente. | Alta |
| **RF09** | Apresentar recomendações para correção dos desvios identificados. | Alta |
| **RF10** | Permitir que o usuário informe se um alerta foi útil ou se foi um falso alerta. | Média |
| **RF11** | Utilizar o feedback do usuário para ajustar parâmetros de tolerância do monitoramento. | Média |
| **RF12** | Permitir consultar informações sobre ergonomia e pausas ativas. | Alta |
| **RF13** | Recuperar informações relevantes de uma base de conhecimento utilizando RAG. | Alta |
| **RF14** | Apresentar as fontes e os trechos utilizados para fundamentar recomendações. | Alta |
| **RF15** | Analisar informações sobre o ambiente de trabalho a partir de uma imagem enviada pelo usuário. | Média |
| **RF16** | Identificar possíveis problemas ergonômicos no ambiente analisado, apresentando ressalvas quando necessário. | Média |
| **RF17** | Disponibilizar painel com tempo em postura adequada, desvios identificados e duração da sessão. | Média |
| **RF18** | Permitir consultar o histórico de sessões e feedbacks registrados. | Média |
| **RF19** | Disponibilizar modo de auditoria com pontos detectados, evidências recuperadas e decisões do mecanismo de segurança. | Média |
| **RF20** | Bloquear solicitações de diagnósticos médicos ou recomendações clínicas fora do escopo do projeto. | Alta |
| **RF21** | Recomendar pausas ativas após períodos prolongados de atividade, conforme intervalos configurados. | Média |
| **RF22** | Permitir configurar preferências de monitoramento, notificações e intervalos de pausa. | Média |

---

## 2. Requisitos Não Funcionais (RNF)

Definem atributos de qualidade, restrições e critérios de operação do sistema.

| ID | Atributo | Descrição / Critério de Aceitação |
| :--- | :--- | :--- |
| **RNF01** | Desempenho | O processamento postural deve ocorrer em tempo próximo do real; meta inicial de até 500 ms entre captura e atualização da análise, em equipamento de referência. |
| **RNF02** | Privacidade | Priorizar processamento local das imagens da webcam. As imagens não devem ser enviadas ao backend nem armazenadas pelo sistema. |
| **RNF03** | Segurança | Proteger comunicações remotas por HTTPS em ambiente de produção. |
| **RNF04** | Usabilidade | Permitir que o usuário inicie uma sessão e realize a calibração sem auxílio externo. |
| **RNF05** | Compatibilidade | Funcionar em versões atuais de Chrome, Edge e Firefox que suportem as APIs necessárias. |
| **RNF06** | Confiabilidade | Evitar alertas excessivos provocados por detecções isoladas, utilizando persistência temporal e limiares configuráveis. |
| **RNF07** | Precisão | Avaliar a identificação dos desvios por *Precision*, *Recall*, *F1-score* e taxa de falsos positivos em conjunto de testes rotulado. |
| **RNF08** | Transparência | Recomendações baseadas no RAG devem apresentar fonte e trecho de evidência para rastreabilidade. |
| **RNF09** | Segurança da informação | Minimizar dados pessoais, não armazenar imagens, evitar dados identificáveis em logs e permitir limpar o histórico local. |
| **RNF10** | Manutenibilidade | Organizar o código em módulos independentes para interface, visão computacional, lógica postural, RAG e API. |
| **RNF11** | Escalabilidade | Permitir adicionar indicadores e fontes de conhecimento sem reescrever o núcleo do sistema. |
| **RNF12** | Disponibilidade | Manter detecção e alertas básicos funcionando sem conexão com a internet, desde que as dependências locais estejam disponíveis. |
| **RNF13** | Portabilidade | Permitir execução da aplicação web em Windows, Linux e macOS por meio de navegador compatível. |
| **RNF14** | Observabilidade | Registrar latência, erros, chamadas de modelos, consumo de tokens e resultados de experimentos, sem incluir imagens pessoais. |
| **RNF15** | Documentação | Disponibilizar README com arquitetura, dependências, configuração e instruções de execução. |

> **Nota:** Os valores de desempenho são metas iniciais propostas, não resultados comprovados. Devem ser medidos em equipamentos e condições de teste definidos.

---

## 3. Regras de Negócio (RN)

| ID | Regra |
| :--- | :--- |
| **RN01** | O monitoramento postural somente poderá começar após a autorização de acesso à webcam. |
| **RN02** | A calibração deve ser realizada antes da primeira sessão ou quando o usuário desejar redefinir sua referência. |
| **RN03** | Um alerta postural não deve ser emitido com base em uma única detecção isolada. |
| **RN04** | O sistema deve considerar a confiança da detecção dos pontos corporais antes de classificar uma postura. |
| **RN05** | Quando a confiança estiver abaixo do limite definido, o sistema deve evitar emitir uma classificação conclusiva. |
| **RN06** | As recomendações devem ser fundamentadas em fontes recuperadas ou em regras previamente definidas. |
| **RN07** | O sistema não deve apresentar suas análises como diagnósticos médicos. |
| **RN08** | O usuário deve poder desativar o monitoramento e encerrar a sessão a qualquer momento. |
| **RN09** | O feedback negativo deve ser considerado no ajuste de tolerâncias, sem alterar automaticamente critérios clínicos ou científicos. |
| **RN10** | As funções básicas de detecção e alerta não devem depender de chamadas a modelos de linguagem. |

---

## 4. Priorização do MVP

A priorização abaixo considera o prazo de duas semanas e separa o núcleo demonstrável das funcionalidades complementares.

| Nível | Requisitos | Escopo |
| :--- | :--- | :--- |
| **Prioridade 1 — Essencial** | RF01–RF09, RF12–RF14 e RF20; RNF01, RNF02, RNF06 e RNF07. | Webcam, calibração, detecção, alertas, orientações com fontes e bloqueio de pedidos médicos. |
| **Prioridade 2 — Importante** | RF10, RF11, RF15–RF19 e RF21–RF22. | Feedback, análise do setup, painel, histórico, auditoria, pausas e configurações. |
| **Prioridade 3 — Evolução** | Funcionalidades posteriores ao MVP. | Novos padrões posturais, personalização avançada, relatórios comparativos e gamificação. |

---

## 5. Critérios de Validação

Os cenários a seguir podem ser utilizados nos testes funcionais e na demonstração do projeto.

| Cenário de teste | Resultado esperado |
| :--- | :--- |
| **Início do monitoramento** | A webcam é ativada após autorização e os pontos corporais são detectados. |
| **Calibração** | O sistema registra uma referência postural para a sessão ou perfil local. |
| **Desvio persistente** | A anteriorização da cabeça mantida por tempo suficiente gera um alerta apropriado. |
| **Mudança momentânea** | Uma mudança rápida de posição não gera alerta desnecessário. |
| **Ausência de pausa** | Após o período configurado, o sistema recomenda uma pausa ativa. |
| **Pergunta sobre ergonomia** | O RAG recupera conteúdo relevante e apresenta a fonte utilizada. |
| **Solicitação de diagnóstico** | O sistema informa que não realiza diagnósticos e orienta a procurar profissional adequado. |
| **Modo auditoria** | São exibidos dados técnicos e evidências que fundamentaram a decisão. |
| **Encerramento** | O monitoramento é interrompido e os indicadores da sessão ficam disponíveis. |

---

## 6. Escopo e Limitações

- A detecção postural é uma estimativa baseada em pontos corporais, não uma avaliação clínica.
- Uma webcam frontal não permite avaliar todos os ângulos e desvios posturais.
- A proximidade da tela não pode ser medida com precisão apenas pela distância entre os olhos; a heurística precisa ser definida e validada.
- O RAG deve fornecer informações educativas, sem substituir profissionais de saúde ou segurança do trabalho.
- O sistema não deve prometer precisão perfeita ou ausência de falsos positivos.

### Diretriz de Desenvolvimento

Priorizar primeiro a webcam, o MediaPipe, a lógica de detecção e os alertas. Em seguida, integrar RAG, rastreabilidade e auditoria. Recursos complementares devem ser implementados somente após o fluxo principal estar funcional.
