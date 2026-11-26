# Política de Privacidade, Retenção Zero e Proteção na Foto do Setup

**Escopo:** Frente 3 — Visão Computacional & Análise Multimodal (Issue #5)  
**Requisitos relacionados:** RF15, RF16, RNF02, RNF03, RNF09, RNF14 e [SPEC.md](../SPEC.md) (§9.2, §10, §13.4 e §14)  
**Status:** Especificação técnica e operacional (controles obrigatórios antes de habilitar `POST /api/v1/setup/analyze`)

---

## 1. Escopo, requisitos e limites

Este documento define as regras de privacidade para o fluxo opcional de análise ergonômica por imagem do ambiente de trabalho (`POST /api/v1/setup/analyze`, descrito em [SPEC.md](../SPEC.md) §10 e [Especificação de Requisitos](./especificacao-requisitos.md)).

### Separação entre fluxos de imagem

| Fluxo | Processamento | Envio ao backend | Persistência |
| :--- | :--- | :--- | :--- |
| **Monitoramento postural por webcam** (RNF02) | 100% local no navegador (MediaPipe) | Proibido (nenhum frame sai do dispositivo) | Proibida |
| **Análise de foto do setup** (RF15, RF16, RNF09) | Preparação e mascaramento no navegador; inferência multimodal sob demanda no backend | Apenas imagem sanitizada (sem EXIF e mascarada), sob ação explícita do usuário | **Retenção zero** (processamento apenas em memória e descarte imediato após inferência) |

### Aviso sobre conformidade legal (SPEC.md §14)

As regras aqui definidas estabelecem controles técnicos de minimização de dados, segurança e retenção zero. Conforme o [SPEC.md](../SPEC.md) §14, a adoção desses controles técnicos e do armazenamento local **não equivale, por si só, a uma declaração de conformidade jurídica completa com a LGPD**. Antes de qualquer exposição pública ou uso fora do ambiente acadêmico, a equipe deve revisar dependências, termos de provedores externos e eventuais requisitos legais aplicáveis.

---

## 2. Política de retenção zero (ciclo de vida da foto do setup)

Toda imagem enviada para `POST /api/v1/setup/analyze` segue o ciclo abaixo, sem persistência em nenhuma etapa:

1. **Recebimento em memória:** o backend recebe a imagem diretamente em memória (RAM), sem gravar arquivos temporários em disco (incluindo `/tmp`) nem utilizar diretórios de upload.
2. **Validação e limpeza defensiva de metadados:** antes de acionar o modelo multimodal, o backend valida o formato/tamanho aceito e remove defensivamente eventuais metadados EXIF, IPTC e XMP remanescentes (geolocalização, modelo de câmera, data/hora e identificadores do dispositivo).
3. **Inferência multimodal:** a imagem sanitizada é encaminhada em memória ao modelo multimodal apenas para produzir a estrutura `SetupAnalysis` ([SPEC.md](../SPEC.md) §9.2).
4. **Descarte imediato pós-inferência:** concluída a inferência — ou imediatamente em caso de erro, timeout, exceção ou cancelamento — o backend libera as referências ao buffer da imagem em bloco `try/finally` e retorna apenas o JSON de resultado.

### Proibições explícitas

- **Armazenamento:** é proibido gravar a foto original, a foto mascarada, miniaturas ou representações base64 em disco local, banco de dados, object storage, `localStorage`, `IndexedDB` ou Cache Storage do navegador.
- **Cache HTTP/proxy:** respostas e requisições envolvendo a foto devem usar cabeçalhos restritivos (`Cache-Control: no-store`), e a comunicação em produção deve ocorrer exclusivamente via HTTPS (RNF03).
- **Logs e observabilidade:** é proibido registrar bytes da imagem, strings base64, metadados EXIF ou nomes originais de arquivos que possam conter informações pessoais em stdout, arquivos de log ou ferramentas de observabilidade (RNF14 e [SPEC.md](../SPEC.md) §13.4).
- **Provedor multimodal:** caso a inferência utilize API externa, o provedor selecionado deve oferecer política documentada de não retenção (*zero-data-retention*) e não utilização dos payloads para treinamento de modelos; caso contrário, deve-se optar por inferência local/self-hosted (ver seção 6).

---

## 3. Proteção no cliente antes do upload (orientações e mascaramento)

Antes que qualquer dado saia do navegador, a interface deve reduzir a exposição de dados pessoais na origem por meio de orientação clara e mascaramento local.

### 3.1. Orientações visuais obrigatórias antes da captura ou seleção

Exibir um aviso curto e legível antes de o usuário selecionar ou tirar a foto:

- Enquadre apenas o posto de trabalho (mesa, cadeira, monitor/notebook, teclado e iluminação).
- Evite incluir pessoas ou rostos na imagem.
- Feche ou oculte telas com e-mails, mensagens, senhas, documentos de trabalho ou dados bancários.
- Retire do enquadramento crachás, documentos de identidade, correspondências, endereços e objetos pessoais identificáveis.

### 3.2. Fluxo de preparação e mascaramento no navegador

O botão de envio só deve ser habilitado após o fluxo local abaixo:

1. **Carregamento local sem envio automático:** a imagem escolhida pelo usuário é carregada apenas na memória do navegador (`<canvas>`), sem upload automático ao selecionar o arquivo.
2. **Remoção automática de EXIF no cliente:** ao renderizar a imagem no `<canvas>` e re-encodificá-la antes do envio, todos os metadados EXIF/IPTC/XMP são descartados no dispositivo do usuário.
3. **Etapa de mascaramento:** disponibilizar ao usuário a marcação de áreas sensíveis (rostos, monitores ligados, crachás, documentos e itens pessoais) aplicando tarja opaca sólida ou desfoque irreversível diretamente nos pixels do `<canvas>` antes da exportação (a estratégia exata — manual, automática para rostos ou híbrida — está registrada na seção 6).
4. **Pré-visualização e confirmação explícita:** exibir a imagem final já mascarada com confirmação explícita do usuário de que ela está pronta para envio sob retenção zero.
5. **Envio sanitizado e limpeza local:** enviar apenas o blob re-encodificado (com nome de arquivo genérico, ex. `setup.jpg`, sem o nome original do dispositivo), revogar imediatamente o `ObjectURL` (`URL.revokeObjectURL`) e limpar o `<canvas>` após o envio ou cancelamento.

---

## 4. Contrato de saída e observabilidade segura

O resultado retornado pelo backend deve seguir estritamente o contrato `SetupAnalysis` definido em [SPEC.md](../SPEC.md) §9.2 (`analysis_id`, `observations` com `category`, `description`, `confidence` e `requires_confirmation`, além de `limitations`), sem incluir a imagem ou referências de arquivo na resposta.

| Permitido em logs e métricas técnicas (RNF14) | Proibido em logs, traces e telemetria (RNF09 / §13.4) |
| :--- | :--- |
| `analysis_id` (UUID sem vínculo nominal), timestamp, status HTTP | Bytes da imagem, base64, URLs temporárias ou miniaturas |
| Latência de processamento, nome do modelo, consumo de tokens | Metadados EXIF/IPTC/XMP (GPS, câmera, horário original) |
| Decisão do Safety Validator e códigos/tipos genéricos de erro | Nome original do arquivo enviado pelo dispositivo do usuário |
| Quantidade de observações retornadas | Textos ou conteúdos lidos em telas, crachás ou documentos visíveis na foto |

---

## 5. Critérios de aceite técnicos verificáveis

A funcionalidade de análise da foto do setup só pode ser habilitada após todos os itens abaixo serem verificados:

### Frontend
- [ ] A tela exibe as orientações de privacidade antes da seleção/captura da imagem.
- [ ] A imagem selecionada não dispara requisição de rede automaticamente; o envio exige revisão da prévia mascarada e confirmação explícita do usuário.
- [ ] O payload inspecionado na aba Network do navegador não contém metadados EXIF (GPS, modelo de câmera, data original) nem o nome original do arquivo do usuário.
- [ ] O mascaramento altera os pixels da imagem exportada antes do envio (não é apenas uma camada visual CSS sobre a imagem original).
- [ ] Nenhuma imagem (original ou mascarada) é gravada em `localStorage`, `IndexedDB` ou Cache Storage, e `ObjectURL` / buffers de `<canvas>` são liberados ao concluir ou cancelar.

### Backend (`POST /api/v1/setup/analyze`)
- [ ] O endpoint lê o upload estritamente em memória, sem gravar arquivos em disco ou em diretórios temporários.
- [ ] O backend executa validação de formato/tamanho e remoção defensiva de metadados EXIF antes de chamar o modelo multimodal.
- [ ] O descarte das referências em memória ocorre em bloco `try/finally`, inclusive quando a inferência falha ou excede o timeout.
- [ ] As respostas incluem `Cache-Control: no-store` e, em produção, o endpoint exige HTTPS (RNF03).
- [ ] Os logs gerados durante requisições válidas e com erro não contêm bytes de imagem, base64, EXIF ou nome original do arquivo.

### IA / MLOps
- [ ] A política de retenção e não uso para treino do provedor multimodal escolhido está documentada antes do uso em ambiente integrado.
- [ ] A ferramenta de observabilidade configurada não captura nem armazena anexos/payloads de imagem nos traces.
- [ ] Existe teste automatizado de privacidade para `/api/v1/setup/analyze` verificando que: (a) nenhum arquivo residual é criado em disco durante a execução, (b) metadados EXIF são descartados e (c) os logs capturados não contêm base64 nem dados pessoais da imagem.

---

## 6. Pendências e decisões em aberto

Os pontos abaixo não estão fechados no repositório atual e devem ser decididos pela equipe antes da implementação final da funcionalidade (prioridade P3 no [SPEC.md](../SPEC.md) §19.2):

| # | Decisão em aberto | Responsável sugerido | Impacto |
| :--- | :--- | :--- | :--- |
| 1 | **Provedor do modelo multimodal:** escolher entre API externa com política documentada de *zero-data-retention* / opt-out de treino ou modelo multimodal local/self-hosted. | Engenheiro de IA + MLOps | Define a garantia real de retenção zero fora da infraestrutura do projeto e eventuais restrições contratuais/de custo. |
| 2 | **Mecanismo de mascaramento no navegador:** definir se no MVP será manual (pincel/caixa de tarja ou desfoque no `<canvas>`), automático para rostos no navegador ou híbrido (detecção automática de rosto + edição manual para telas/crachás/objetos). | Arquiteto / Frontend + Visão | Impacta complexidade de implementação no cliente, tempo de entrega e risco de rosto não mascarado por esquecimento do usuário. |
| 3 | **Limites operacionais da imagem:** definir formatos aceitos, tamanho máximo em MB e resolução máxima de re-encodificação no cliente e no backend. | Frontend + Backend | Controla consumo de memória (RAM), latência, custo de tokens multimodais e redução de detalhes pessoais desnecessários. |
| 4 | **Ferramenta de observabilidade:** fechar a escolha entre Arize Phoenix, Langfuse ou alternativa ([SPEC.md](../SPEC.md) §13.4) e documentar a configuração que desabilita captura de payloads binários/de imagem. | MLOps / LLM Ops | Evita vazamento acidental da foto do setup para bancos de telemetria e traces. |
| 5 | **Conjunto de teste fixo de fotos (Semana 4):** definir se a avaliação de visão usará apenas fotos sintéticas/públicas ou voluntárias com termo de consentimento próprio, separado do fluxo de retenção zero da aplicação. | Cientista de Dados + Engenheiro de Dados | Garante base ética e reproduzível para medir concordância do agente de visão sem violar a regra de retenção zero em produção. |
