# Glossário — call-copilot

Todas as expressões técnicas usadas nas conversas sobre o projeto, explicadas.
Organizado por tema. Serve de preparação para a entrevista (Neurons Lab).

---

## 1. Voz e transcrição (STT)

**STT / Speech-to-Text / "transcriber"**
Software que converte áudio de fala em texto. Aqui é o AWS Transcribe.

**Streaming vs batch**
- *Streaming*: o áudio entra em tempo real e o texto sai à medida que a pessoa
  fala (latência de segundos). É o que uma chamada ao vivo exige.
- *Batch*: envias um ficheiro completo e recebes a transcrição depois. Mais
  preciso, mas inútil para um copiloto ao vivo.

**Diarização (speaker diarization / speaker labels)**
Distinguir *quem* falou cada frase ("VCC" vs "família"). O Transcribe tem
`ShowSpeakerLabel`; neste projeto é mais simples — há uma faixa de áudio por
pessoa (o LiveKit separa), portanto cada stream já é de um só falante.

**Transcript**
O texto acumulado da chamada até ao momento. É o input do extrator.

**Turno (turn)**
Uma fala completa de um participante ("Yes, it's Kathleen O'Brien."). O sistema
processa o transcript turno a turno.

**Partial vs final result**
O Transcribe emite hipóteses parciais (vão mudando) e depois um resultado
*final* estável. O código só usa os finais (`is_partial == False`).

**Silence-close / "Transcribe fecha o stream em silêncio"**
O AWS Transcribe fecha a ligação sozinho quando não recebe áudio durante um
tempo — o que acontece na faixa de uma pessoa enquanto a outra fala. Foi
diagnosticado por engano como "queda de rede". Fix: `TranscribeSession` reabre o
stream no próximo envio que falha.

**Custom vocabulary / speech adaptation / phrase hints**
Dar à STT uma lista de palavras difíceis (apelidos, nomes de animais) para ela
as reconhecer melhor. Cada fornecedor chama-lhe algo diferente. É a alavanca
mais barata para o problema dos nomes estrangeiros.

**Keyterm prompting** (Deepgram)
O mesmo conceito, mas os termos são passados inline em cada pedido, não
pré-registados.

**IPA (International Phonetic Alphabet)**
Notação fonética. O Transcribe deixa-te especificar a *pronúncia* de um termo em
IPA, para os casos que a ortografia não resolve.

**WPM (words per minute)**
Ritmo de fala. Fala de telefone descontraída ≈ 150 wpm. O `bench_latency.py`
usa isto para simular a cadência real da chamada.

**VAD (Voice Activity Detection)**
Detetar quando há voz vs silêncio. Relevante em pipelines de voz; aqui é o
Transcribe que trata disso internamente.

---

## 2. Avaliação de precisão (eval)

**Golden-set / dataset dourado**
Um conjunto fixo de casos com a resposta correta conhecida ("verdade"). Aqui:
25 amostras difíceis (nomes irlandeses, vietnamitas, polacos; emails soletrados).
Corres o sistema contra eles e mede o acerto.

**Eval / harness de eval**
O programa que corre o golden-set, compara output vs esperado, e calcula
métricas. `eval/run.py`.

**A/B (teste A/B de modelos)**
Correr o *mesmo* input por dois modelos e comparar. Aqui: Claude Haiku 4.5
(Bedrock) vs Gemini 3.6 Flash (Vertex). A vaga pede exatamente isto.

**Exact match**
O output é *idêntico* ao esperado (depois de normalizar maiúsculas/espaços).
Métrica dura — "Kathleen O'Brien" ≠ "Kathleen O'Brian".

**Phonetic match / Metaphone**
Acerto se as duas strings *soam* igual. Metaphone é um algoritmo que reduz uma
palavra a um código fonético ("Smith" e "Smyth" → mesmo código). Mede se o erro
é só de ortografia, não de compreensão.

**WER (Word Error Rate)**
Percentagem de palavras erradas (inserções + remoções + substituições ÷ total).
0 = perfeito, 1 = tudo errado. Métrica clássica de STT.

**Levenshtein / edit distance / lev_norm**
Número mínimo de edições de *carácter* (inserir/apagar/trocar) para ir de uma
string à outra. `lev_norm` = normalizado 0–1 pelo comprimento. Bom para emails,
onde um carácter conta.

**Isolar o gargalo (STT vs LLM)**
O achado central do projeto: todas as falhas vêm da STT a estropiar fonemas
não-ingleses; o LLM é fiel ao transcript que recebe. Logo, a alavanca de
precisão é a STT, não a escolha de LLM. Provado por o A/B: os dois modelos
falham *as mesmas* amostras.

---

## 3. Extração e LLM

**Extração estruturada (structured extraction)**
Tirar campos organizados (nome, telefone, email, tipo de visita…) de texto
livre. O output é um objeto com campos, não prosa.

**Backend de extração / `EXTRACT_BACKEND`**
Variável de ambiente que escolhe qual o motor de extração em runtime:
`bedrock` (Claude Haiku) ou `gemini` (via Vertex ou chave AI Studio). Trocável
sem mexer no código — é o "A/B em produção".

**Forced tool use / forced `emit_fields` tool**
Obrigar o modelo a responder chamando uma *ferramenta* (função) com um schema
fixo, em vez de texto livre. Garante JSON válido. O Bedrock faz assim
(`toolChoice`).

**JSON mode / `response_mime_type: application/json`**
O equivalente no Gemini — pedir ao modelo que devolva só JSON.

**Structured outputs**
Termo geral para forçar o formato da resposta (schema). Reduz parsing frágil.

**Schema Pydantic**
Definição em Python dos campos e tipos esperados (`AppointmentFields`). Documenta
e valida a forma dos dados.

**Debounce**
Não extrair a cada turno — esperar um intervalo mínimo (`min_extract_gap_s`,
12s) + contagem de turnos antes de chamar o modelo outra vez. Reduz ~65% das
chamadas ao LLM sem perder cobertura, e (medido) não custa latência.

**`finalize()` / passagem final**
Ao fim da chamada, uma extração sobre o *transcript inteiro*. Rede de segurança:
apanha qualquer campo que as extrações incrementais falharam (ex.: por
throttling) e o campo `preferred_time`, que só é dito perto do fim.

**`merge()` / confidence gate**
Ao juntar um novo valor de campo com o que já lá está: só sobrescreve se a
*confiança* for maior. Evita que uma extração pior estrague uma boa.

**Confidence / score de confiança**
Número 0–1 que o modelo atribui a cada campo. Usado no merge e (planeado) para
sinalizar campos duvidosos ao humano confirmar.

**Time-to-first-field / time-to-all-fields**
Quanto tempo desde o início da chamada até o primeiro campo aparecer no ecrã / até
todos aparecerem. Métrica de UX do agent-assist. `bench_latency.py` mede-a.

**p50 / p95 (percentis de latência)**
p50 = mediana (metade das chamadas é mais rápida). p95 = 95% são mais rápidas
que isto; captura os piores casos. Padrão para reportar latência.

**"remove ~1 min lag on one field type"** (frase da vaga)
Referia-se a um campo que demorava ~1 min a aparecer. Aqui esse campo é o
`preferred_time` — mas o atraso é *posição no transcript* (a marcação só é
combinada perto do fim), não o extrator. Mitigação: o `finalize()`.

**Sliding window / janela deslizante**
Otimização futura: enviar só os últimos ~40s do transcript ao modelo, não a
chamada toda — trava o crescimento dos tokens de input.

**Prompt caching**
O Bedrock deixa "cachear" a parte fixa do prompt (system + schema) e só cobra
tokens novos pelo transcript que cresce. Otimização de custo futura.

---

## 4. Cloud e modelos

**Bedrock (AWS)**
Serviço da AWS que serve modelos de várias empresas (incl. Anthropic Claude) por
API. `bedrock-runtime` + `converse` é a API de chat.

**Inference profile / `us.anthropic.claude-…`**
Um ID de modelo no Bedrock que encaminha para a região com capacidade. O Haiku
4.5 *exige* o inference profile (`us.anthropic.…`); o ID "on-demand" simples
(`anthropic.…`) dá "Not supported".

**Throttling / `ThrottlingException`**
A AWS recusa o pedido por excesso de uso. Aqui era um **cap diário de tokens**
específico de contas novas — não o TPM/RPM normal.

**TPM / RPM (tokens/requests per minute)**
Limites de ritmo padrão. Estavam nos defaults (5M) — não eram o problema. O
problema era um limite *diário* separado.

**Daily token cap**
Tecto de tokens por *dia* que a AWS põe em contas novas nos primeiros dias.
Resolve-se com um caso de suporte ("Account and billing", grátis) ou sozinho
com o tempo.

**Free Plan → pay-as-you-go**
Contas AWS novas entram num "Free Plan" que é uma sandbox — Bedrock/Transcribe
gated. É preciso fazer "Upgrade plan" na consola de Billing.

**Service Quotas**
Consola da AWS onde se veem e pedem aumentos de limites.

**IAM / IAM user / least-privilege policy**
Gestão de identidades e permissões da AWS. O projeto usa um utilizador IAM
dedicado (`call-copilot-listener`) com uma política mínima (só as ações que
precisa: `bedrock:InvokeModel*`, `transcribe:StartStream*`, `ses:SendEmail`).

**STS / `sts:GetCallerIdentity`**
"Quem sou eu na AWS agora." Usado nos healthchecks para confirmar que as
credenciais funcionam.

**SES (Simple Email Service)**
Serviço de envio de email da AWS. Usado para o briefing pré-visita.

**SES sandbox**
Modo inicial do SES: só podes enviar para endereços *verificados*. Sair do
sandbox precisa de pedido à AWS.

**Vertex AI (Google Cloud)**
O serviço de IA da Google Cloud. Serve Gemini *e* (via Model Garden) Claude,
Llama, etc. Faturado no projeto GCP — sem o cap diário do free tier do AI Studio.

**Model Garden**
O catálogo de modelos do Vertex AI, incluindo os da Anthropic.

**AI Studio (aistudio.google.com)**
A porta "developer" da Google para o Gemini — chave `AQ.…`, free tier de
20 pedidos/dia/modelo. Diferente do Vertex.

**ADC (Application Default Credentials)**
Como o SDK da Google descobre as credenciais sem chave de API:
`gcloud auth application-default login` grava um token que o SDK lê sozinho.

**`GCP_PROJECT` / `GCP_LOCATION`**
Variáveis que dizem ao cliente Vertex qual o projeto e a região. `global` é
preciso para o `gemini-3.6-flash` (o `us-central1` só serve o 2.5-flash).

**Tokens (input / output)**
Unidade de faturação dos LLMs — ~4 caracteres = 1 token. Preços dados "por 1M
tokens", separados para input (o que envias) e output (o que o modelo gera).

**Model ID / snapshot / `@version`**
Identificador exato do modelo. No Vertex, snapshots datados usam `@`
(`claude-opus-4-5@20251101`), modelos correntes usam o nome simples.

---

## 5. Chamada, LiveKit e rede

**LiveKit**
Plataforma de salas de áudio/vídeo em tempo real (WebRTC gerido). Aqui: uma sala
= 2 humanos + 1 "listener" silencioso.

**`rtc.Room` vs livekit-agents worker**
O projeto usa `rtc.Room` diretamente (juntar-se a uma sala nomeada) em vez da
framework de "workers" com dispatch/scaling. Mais simples para um listener de
uma sala só.

**Listener / participante silencioso**
O agente junta-se à sala, *subscreve* o áudio dos dois humanos, mas nunca
*publica* áudio. Nunca fala. Daí "copiloto que escuta".

**Publish / subscribe (de faixas)**
*Publicar* = enviar a tua faixa de áudio para a sala. *Subscrever* = receber a
de outro participante. O `sim_call.py` publica dois WAV como dois participantes.

**Token (LiveKit) / listener_token / publisher_token**
Credencial JWT que autoriza entrar numa sala com certas permissões
(subscribe-only vs publish).

**SIP**
Protocolo de telefonia. O LiveKit tem SIP para ligar números de telefone reais
a salas — como uma chamada real chegaria em produção.

**WebRTC**
A tecnologia por trás de áudio/vídeo em tempo real no browser/apps. Duas
camadas: *sinalização* (negociação, por WebSocket) e *media* (o áudio em si,
por UDP).

**Signalling / "signal client"**
O canal de controlo (WebSocket) que negoceia a ligação. Funciona mesmo em redes
más — é TCP.

**ICE (Interactive Connectivity Establishment)**
O processo de descobrir um caminho de rede por onde o *media* (UDP) pode passar
entre os dois lados. É o que falhava no hotspot.

**PeerConnection / "pc state failed"**
A ligação WebRTC ponto-a-ponto. "pc state failed" = o ICE não encontrou caminho
para o media.

**Ping timeout / "session close"**
O LiveKit desiste da sessão quando o media não estabelece a tempo.

**Resume / reconnect**
Quando a ligação cai, o LiveKit tenta *retomar* (resume) sem perder o estado, ou
*reconectar* de novo. Um resume pode "engolir" o evento de participante-saiu —
foi por isso que se adicionou o *idle watchdog*.

**NAT / CGNAT (Carrier-Grade NAT)**
NAT = a tua rede local partilha um IP público. CGNAT = o *operador móvel* mete
milhares de clientes atrás de um só IP. Quebra o "hole-punching" de UDP que o
WebRTC precisa → o media não passa.

**Hotspot / partilha de internet do iPhone**
Rede móvel partilhada. Gateway `172.20.10.1` é a assinatura. Combinada com CGNAT,
mata o WebRTC — foi a causa-raiz das 8 tentativas de e2e falhadas.

**`en14 constrained`**
Flag do macOS que marca a interface como "com dados limitados" (rede móvel).
Outra pista de que era hotspot.

**TURN (server)**
Servidor de relay que reencaminha o media quando a ligação direta falha.
Ajuda com NAT, mas em CGNAT + rede móvel instável continua frágil.

**`utun` (interfaces)**
Interfaces de túnel do macOS. As 6 que apareceram são do sistema (iCloud Private
Relay, etc.), não uma VPN.

**Idle watchdog**
Tarefa de fundo que termina a chamada se não chegarem transcrições novas durante
N segundos (`CALL_IDLE_END_S`, 30). Rede de segurança para quando o LiveKit não
dá o evento de fim de chamada.

**Teardown**
A sequência de encerramento da chamada: fechar streams → `finalize()` → `flush()`
de custos → marcar sessão terminada. Tinha um bug (`CancelledError` a escapar)
que saltava tudo isto.

**`CancelledError`**
Exceção do `asyncio` quando uma tarefa é cancelada. É `BaseException`, não
`Exception` — por isso escapava aos `except Exception` e partia o teardown.

---

## 6. Observabilidade

**Observability / tracing**
Ver *o que o sistema fez por dentro* — cada chamada ao modelo, input, output,
latência, custo, erros — para depurar e otimizar.

**Langfuse**
Plataforma de observability para apps de LLM. Guarda "traces" e mostra-os num
dashboard. A vaga nomeia-a duas vezes.

**Trace / span**
- *Trace*: um pedido/operação completa.
- *Span*: um passo dentro dela (ex.: "extract_turn"). Tem input, output,
  metadata, duração.

**`@observe` / context manager `span()`**
Formas de instrumentar o código para gerar spans. Aqui: `with span("...") as s:`.

**No-op / "no-ops without keys"**
`trace.py` não faz nada (silenciosamente) se não houver chaves Langfuse — para o
código correr na mesma sem a dependência configurada.

**SDK drift / v3 vs v4**
A API do SDK Langfuse mudou entre versões (v3: `start_as_current_span`; v4:
`start_as_current_observation`). O `trace.py` estava escrito para a v3 e teria
falhado — corrigido nesta sessão.

**`flush()`**
Forçar o envio dos traces em buffer antes de o programa terminar.

---

## 7. Web, dashboard e extensão

**Next.js / App Router**
Framework React para o dashboard (`web/`). "App Router" é o modelo de
routing moderno (pastas = rotas).

**Server Component / service_role**
Páginas que correm no servidor e leem o Supabase com a chave `service_role`
(privilegiada, bypassa RLS). Nunca exposta ao browser.

**Chrome extension MV3 (Manifest V3)**
A versão atual do formato de extensões Chrome. Componentes:
- *manifest.json*: declaração (permissões, ficheiros).
- *background / service worker*: script persistente — aqui, o cliente WebSocket.
- *content script*: injetado na página-alvo — aqui, preenche os campos.
- *popup*: a mini-UI ao carregar no ícone — aqui, configuração.

**"Load unpacked"**
Carregar uma extensão a partir de uma pasta local (não da Chrome Web Store),
para desenvolvimento. `chrome://extensions` → "Load unpacked".

**Content script / `[data-copilot-field]`**
O content script procura elementos com o atributo `data-copilot-field="owner_name"`
e escreve o valor lá. É o "contrato" entre a extensão e o formulário.

**Native setter + input event**
Para preencher um campo de um form React de fora, não basta `input.value = x` —
é preciso chamar o setter nativo e disparar um evento `input` para o React
reagir. É o que o `content.js` faz.

**WebSocket (WS) / fan-out**
Canal bidirecional persistente. O `ws_server.py` no processo listener faz
*fan-out*: recebe atualizações de campos e reenvia-as a todos os clientes
(extensões) subscritos àquela sessão.

**`ws_push.py`**
Ferramenta de dev: corre um servidor WS local com dados falsos (Kathleen/Luna)
para demonstrar a extensão sem cloud nenhuma.

---

## 8. Dados

**Supabase**
Postgres gerido + APIs + auth. Guarda `sessions`, `extracted_fields`,
`call_costs`, `eval_runs`.

**Migration (SQL)**
Ficheiro versionado que altera o schema da base de dados
(`001_sessions.sql`, …). Corre-se por ordem.

**RLS (Row-Level Security)**
Regras do Postgres que filtram *que linhas* cada utilizador vê. A migração `005`
adiciona políticas por `vcc_id` — a "história de isolamento multi-tenant" que a
vaga pede. Ainda não aplicada.

**service_role key vs anon key**
- *anon*: chave pública, sujeita a RLS.
- *service_role*: chave secreta, ignora RLS. O listener e o dashboard usam esta.

**FK (foreign key)**
`extracted_fields.session_id` aponta para `sessions.id`. Não podes inserir um
campo para uma sessão que não existe — foi por isso que o teste de persistência
reutilizou uma sessão existente.

**Upsert**
Insert-ou-update: escreve a linha, ou atualiza se a chave já existe. `call_costs`
faz upsert por `session_id`.

---

## 9. Custo

**Cost model / per-call cost**
Estimativa do custo de uma chamada: segundos de Transcribe + tokens do LLM,
convertidos a USD por `pricing.py`. ≈ $0.26 numa chamada de 8 min ($0.19 STT +
$0.07 LLM).

**`LLM_RATES` / tarifa por backend**
Dicionário em `pricing.py` com o preço input/output por 1M tokens de cada
backend (Bedrock Haiku vs Gemini Flash). Antes cobrava tudo à tarifa Bedrock.

**Introductory pricing**
Preço promocional de lançamento. O Gemini 3.6 Flash está a $0.75/$3.75 por 1M
até fim de 2026; depois sobe para $1.50/$7.50.

**1k/mo projection**
Projeção de custo para 1000 chamadas/mês — número que o dashboard `/costs`
mostra.

**Load test / concorrência**
Abrir N salas LiveKit ao mesmo tempo e verificar que aguentam e que a sessão A
nunca vê dados da sessão B. Testado com 6 salas. A vaga pede "5–10+".

**Data isolation assert**
O teste que confirma programaticamente que não há fuga de dados entre sessões.

---

## 10. Método e jargão de processo

**Portfolio piece / prova de portfólio**
Não é um produto para vender — é código real, hands-on, com números, para
mostrar numa entrevista. (Vender este projeto durante o processo com a Neurons
Lab seria conflito de interesses.)

**Gap → vaga**
O plano mapeia cada requisito da vaga (A–H) a uma peça a construir. "Fechar um
gap" = levá-lo de "zero" a "feito, com evidência".

**e2e (end-to-end)**
Teste do fluxo completo: chamada real → transcrição → extração → campos na base
de dados → dashboard. É o único passo ainda bloqueado (precisa de Wi-Fi estável).

**Smoke test**
Verificação mínima de que algo básico funciona ("o Bedrock responde `pong`?").

**Healthcheck / deep-check**
Script que testa cada dependência externa (STS, Transcribe, SES, Supabase) e
falha com código de saída ≠ 0 se alguma estiver em baixo.

**Sleep mode** (Bedrock)
Deixar o código de um backend intacto mas não o usar — pronto a reativar
mudando uma variável de ambiente, sem re-trabalho.

**YAGNI ("You Aren't Gonna Need It")**
Não construir o que não é preciso agora. Princípio do modo "ponytail" — a
solução mais simples que funciona.

**Debounce vs throttle** (geral)
Ambos limitam a frequência de uma ação. *Throttle*: no máximo 1× por intervalo.
*Debounce*: espera até parar de haver eventos (+ aqui, uma contagem de turnos).

**Brainstorming / bounded / architectural**
Classificação do tamanho de uma mudança antes de a fazer:
- *spike*: pergunta de viabilidade.
- *bounded*: mudança pequena a código existente (ex.: adicionar o backend Vertex).
- *architectural*: subsistema novo → precisa de spec escrita.

---

*Última atualização: 2026-09-02. Se um termo aqui deixar de bater certo com o
código, o código manda.*
