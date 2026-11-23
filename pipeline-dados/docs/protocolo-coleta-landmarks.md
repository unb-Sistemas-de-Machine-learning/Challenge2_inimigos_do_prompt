# Protocolo de coleta e rotulagem de landmarks (PROPOSTA)

Objetivo: montar o conjunto de teste rotulado do RNF07 (precision, recall, F1 e falsos positivos) **sem guardar imagens**.
Este documento é uma proposta do papel de Dados: o grupo (e, se possível, o professor) precisa validar antes da coleta.

## 1. Princípios
- **Sem imagens:** o navegador processa o vídeo e grava só coordenadas dos pontos do corpo (ver `schema/coleta.ts`).
- **Voluntários adultos, com consentimento:** termo curto e claro (o que é gravado, para quê, quem acessa, como pedir exclusão). Confirmar com o professor se a disciplina exige algum procedimento formal.
- **Anonimato:** cada voluntário recebe um código; a tabela que liga código e pessoa não é guardada.
- **Minimização:** guardar só os pontos do corpo necessários. Pontos do rosto só se o grupo decidir que são indispensáveis; pontos faciais podem ser dado pessoal sensível (biometria) pela LGPD, então confirmem no texto da lei e registrem a decisão em ADR.
- **Exclusão:** o voluntário pode pedir a remoção das suas gravações a qualquer momento antes do congelamento do conjunto de teste.

## 2. O que é gravado
- Uma gravação por cenário, em arquivo `.jsonl` (um quadro por linha: `t_ms` e `pose`).
- Nota de compatibilidade: `schema/coleta.ts` nomeia a confiança do ponto como `visibilidade`, enquanto `prototipo/js/posture-engine.js` lê `visibility`; o adaptador de avaliação (`eval/run_posture_engine.mjs`) aceita ambos.
- Para o cálculo de métricas (Precision, Recall, F1 e FPR) e o baseline sintético de regressão, ver [protocolo-avaliacao-rnf07.md](./protocolo-avaliacao-rnf07.md).
- Cabeçalho com versão do modelo de visão, FPS médio, iluminação e posição da câmera.
- Registrar sempre a mesma configuração de câmera nos testes principais (frontal) e anotar quando for diferente.

## 3. Roteiro de cenários (cada voluntário)
1. Postura adequada, sentado normalmente (referência de calibração).
2. Cada tipo de desvio da lista em `cards/_tipos_desvio.yaml`, mantido por um tempo definido pelo grupo.
3. Mudança momentânea de posição (deve **não** gerar alerta: testa a RN03).
4. Pessoa saindo do enquadramento ou com baixa visibilidade (testa RN04 e RN05).
O tempo de cada cenário e o número de voluntários devem ser definidos com o grupo. Não prometam um tamanho de conjunto antes de saber quanto dá para coletar.

## 4. Rotulagem
- O grupo escreve **primeiro** os critérios de cada rótulo (o que conta como "cabeça para frente", "ombros desalinhados" etc.) e se compromete a não mudá-los depois de ver os resultados.
- Cada gravação é rotulada por **duas pessoas**, de forma independente, em segmentos (`inicio_ms`, `fim_ms`, `rotulo`).
- Divergências são resolvidas em conversa e o resultado final é registrado. Se quiserem medir o acordo entre anotadores, o coeficiente kappa de Cohen é uma opção (confirmem o método em uma referência confiável).
- O rótulo vem da equipe, **não** do feedback do usuário (que é opinião e serve ao ajuste de tolerância).

## 5. Divisão dos dados
- Separar treino/ajuste e teste **por voluntário**, não por quadro. Quadros do mesmo voluntário parecem muito entre si, e misturar infla as métricas.
- Congelar o conjunto de teste (e a versão dos parâmetros) antes de medir. Depois de congelado, não ajustar limiares olhando o teste.

## 6. Armazenamento e versionamento
- Os arquivos ficam fora do GitHub público até o grupo decidir (por segurança, mesmo sem imagens). O repositório guarda só o esquema, o protocolo e dados sintéticos de exemplo.
- Versionar o conjunto (por exemplo, com DVC ou hashes registrados em um manifesto; confirmem a ferramenta). O manifesto lista arquivos, hash, versão do esquema e versão do modelo.
- Acesso restrito à equipe; definir prazo de retenção e descartar ao fim da disciplina.

## 7. Limitações a registrar no relatório
- Poucos voluntários e ambientes parecidos limitam a generalização.
- Webcam frontal não avalia todos os desvios.
- Os rótulos são de pessoas leigas em ergonomia, a menos que um profissional revise.

## 8. Quem faz o quê (sugestão)
- **Dados:** formato, scripts de validação, manifesto e versionamento.
- **Cientista:** critérios de rotulagem, divisão e métricas.
- **IA/Arquiteto:** modo de gravação no navegador.
- **MLOps:** rodar a avaliação automática sobre o conjunto congelado.
