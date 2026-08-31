# call-copilot — o que este projeto acrescenta ao teu perfil

Análise honesta do que construíste e verificaste vs. o que está escrito mas por
correr. Base para actualizar CV / LinkedIn.

---

## 1. Estado real do projeto

### Verificado end-to-end (podes afirmar sem ressalvas)
- **Listener de voz em tempo real** — junta-se a uma sala LiveKit como participante
  silencioso, subscreve uma faixa de áudio por interlocutor, transcreve os 49s da
  conversa de teste inteira (2 speakers, 14 transcrições finais, labels correctos).
- **STT streaming em produção** — AWS Transcribe streaming, resample de 16 kHz PCM
  a partir das frames LiveKit, gestão de ciclo de vida do stream (reabre quando o
  Transcribe fecha em silêncio). Fix de fiabilidade: conclusão de chamada 30% → 100%
  no fixture.
- **Briefing por email** — AWS SES, email real enviado e recebido.
- **Golden-set eval (lado Gemini)** — 25 amostras difíceis, métricas de accuracy
  fonética (metaphone), WER, Levenshtein normalizado. Resultado: nomes 60% phonetic;
  **achado analítico** — 100% das falhas são o STT a estropiar fonemas não-ingleses,
  o LLM é fiel ao transcript. Conclusão: a alavanca de accuracy é o STT.
- **Concorrência + isolamento de dados** — 6 salas LiveKit em paralelo, sem falhas,
  assert de isolamento cross-session passa.
- **Optimização de custo** — debounce: **−69% de chamadas ao LLM** (13→4 no
  fixture de 49s), ~−67% de tokens no fixture (o transcript curto faz o prompt
  fixo dominar; numa chamada real de 8 min a poupança encolhe — por medir).
  Modelo de custo por chamada (~$0.26 / 8 min); tabela + dashboard de custo real.
- **Health checks** — endpoint de liveness + script de deep-check (STS, Transcribe,
  SES, Supabase — 4/4 ok).

### Código escrito, à espera de quota externa (afirma como "construído", não "provado à escala")
- Extracção estruturada incremental com merge por confiança + latência por campo
  (backends AWS Bedrock **e** Gemini, trocáveis por env var — é o A/B de modelo em
  runtime que a vaga pede). Bloqueado: cap diário de tokens do Bedrock em conta nova.
- A/B completo Haiku vs Gemini sobre o golden-set. Bloqueado no lado Bedrock.
- Langfuse (wired, sem keys).

### Não feito
- Deploy em produção (Railway/Vercel).
- Redução de P95 documentada com antes→depois (instrumentado, sem a narrativa ainda).

---

## 2. Skills / áreas NOVAS (não estão no CV v6)

| Área | Evidência concreta neste projeto |
|---|---|
| **AWS** (o CV é Azure + GCP) | Bedrock (Claude via inference profiles `us.anthropic.*`), Transcribe streaming, SES, desenho de política IAM de menor privilégio, Service Quotas, migração Free Plan → pay-as-you-go, `boto3` |
| **Agent-assist / copiloto que escuta** | padrão oposto ao voice-bot: transcreve chamada humano-humano e extrai campos em tempo real — nomeado explicitamente na indústria de contact-center |
| **Avaliação de modelos (golden-set / evals)** | harness próprio, dataset de casos difíceis, métricas de accuracy fonética (metaphone), WER, Levenshtein, comparação A/B, isolamento de gargalo (STT vs LLM) |
| **A/B de modelo em runtime** | backend de extracção trocável (Bedrock ⇄ Gemini) atrás da mesma interface, via env var |
| **Chrome Extension (MV3)** | service worker de background, content script, injecção em DOM React-safe (native setter + eventos bubbling), cliente WebSocket, popup de config |
| **Teste de concorrência + isolamento de dados** | harness de load test, N salas concorrentes, asserts de fuga cross-session, RLS por tenant (`vcc_id`) |
| **Cost engineering com números** | modelo de preço, tabela de custo por chamada + dashboard, optimização por debounce medida, plano de optimização documentado (`OPTIMIZATION.md`) |
| **Incident handling / runbook** | `HEALTH.md` — cada modo de falha visto (throttle Bedrock, 429 Gemini, queda LiveKit, fecho de stream Transcribe, blip DNS) com sintoma → check → fix → rollback |
| **Servidor WebSocket fan-out** | pub/sub por sessão, isolamento, com teste |
| **Debugging sistemático** | diagnóstico errado (queda de rede LiveKit) → causa real (timeout de silêncio do Transcribe) → fix de reabertura de stream |

---

## 3. Skills REFORÇADAS (já no CV, agora com prova mais funda)

| Já no CV | O que este projeto acrescenta |
|---|---|
| LiveKit | uso como transporte de áudio multi-participante para um agente *listener* (não um bot), tokens subscribe-only, `rtc.Room` puro sem o framework de workers |
| Streaming speech / VAD | agora também AWS Transcribe streaming, diarização por faixa, resample de frames |
| Structured extraction (Pandas/Docling) | agora extracção estruturada **em tempo real** durante uma chamada, com tool use forçado / JSON schema e merge incremental por confiança |
| Prompt engineering | system prompt + tool schema para extracção multi-campo; lidar com "thinking tokens" do Gemini 3.x que comem o `max_output_tokens` |
| FastAPI / WebSocket / Docker | agente Python containerizado (Railway), servidor WS embutido, health HTTP server |
| Next.js / Supabase | dashboard server-components com RLS, `.throwOnError()`, symlink de env, `proxy.ts` (Next 16), Server Actions para auth |
| Cost-hardening (Azure agent) | agora com tabela de custo real por chamada, projecção mensal, e uma optimização medida (debounce: −69% chamadas / ~−67% tokens no fixture) |
| GDPR / dados sensíveis | isolamento de dados clínicos por coordenador (RLS por `vcc_id`), políticas deny-all em tabelas operacionais |
| Git / Claude Code | ~22 commits pequenos e descritos, plano de 9 fases executado, docs de handoff |

---

## 4. Bullets prontos para CV / LinkedIn

### Novo projeto para a secção "Selected Projects"

> **Real-Time Call Copilot** · agent-assist for scheduling workflows
> A listening voice copilot: joins a live two-party call as a silent participant,
> streams each speaker to AWS Transcribe, and extracts appointment/clinical fields
> in real time with an LLM (AWS Bedrock Claude Haiku / Gemini — runtime-swappable
> backend for A/B). Fields flow over WebSocket to a Chrome extension (MV3) that
> fills the scheduling form; a pre-visit briefing goes out via AWS SES. Built a
> golden-set evaluation harness (phonetic name/email accuracy — metaphone, WER)
> that isolated STT, not the LLM, as the accuracy bottleneck. Concurrency +
> cross-session data-isolation tested; per-call cost instrumented, LLM
> invocations cut ~70% (13→4/call) via debounced extraction. Python, LiveKit,
> AWS (Bedrock/Transcribe/SES), Supabase,
> Next.js, Langfuse.

### Adições à secção "STACK"

- **Cloud / AI:** acrescentar `AWS (Bedrock, Transcribe streaming, SES, IAM)`
- **Voice & Audio:** acrescentar `AWS Transcribe (streaming, per-speaker diarization)`
- **AI & Agents:** acrescentar `structured extraction (tool use / JSON schema), model evaluation (golden sets, phonetic accuracy, WER), A/B model routing`
- **Observability:** nova linha → `Langfuse, per-call cost dashboards, health checks / runbooks`
- **Frontend:** acrescentar `Chrome Extensions (MV3, service workers, content scripts)`
- **Testing:** nova linha → `golden-set evals, load / concurrency testing, data-isolation assertions, pytest`

### LinkedIn "About" / headline — frases utilizáveis

- "Real-time voice pipelines: streaming STT, turn handling, low-latency LLM extraction — hands-on."
- "I instrument what I build: per-call cost, extraction latency (p50/p95), model accuracy on golden sets."
- "Agent-assist and voice-bot patterns, on AWS and Azure."

---

## 5. O que NÃO afirmar ainda

- ❌ "Reduzi P95 em produção de Xs para Ys" — tens a instrumentação, não a narrativa
  com números reais. Corre a optimização e mede primeiro.
- ❌ "A/B Claude Haiku vs GPT/Gemini com resultados" — só o lado Gemini correu.
- ❌ "Em produção / com utilizadores reais" para *este* projeto — é portfolio,
  verificado em fixture. (O `voice-demo` e o Azure agent são a tua prova de
  "voice AI a atender chamadas reais".)
- ❌ "Langfuse in production" — está wired, sem uma corrida real.
- ⚠️ Cuidado ao mostrar/descrever — o domínio (hospício veterinário, VCC) é o
  produto exacto do cliente da Neurons Lab. Como portfolio *para eles*: forte.
  Publicamente / para vender: reposiciona para outro vertical.

---

## 6. Edições concretas ao CV v6

1. **SUMMARY** — a frase "like multilingual voice agents answering real calls 24/7"
   pode ganhar "…and a real-time agent-assist copilot that transcribes live calls
   and extracts structured fields as they happen."
2. **STACK → Cloud / AI** — hoje só Azure + GCP. Adiciona **AWS (Bedrock, Transcribe,
   SES)**. É a maior lacuna que este projeto fecha.
3. **STACK → nova linha "Evaluation & Observability"** — `golden-set evals, phonetic
   accuracy metrics, load / concurrency testing, Langfuse, cost dashboards`.
4. **SELECTED PROJECTS** — adicionar o "Real-Time Call Copilot" (bullet acima),
   idealmente logo abaixo do "AI Voice Agent System" para agrupar a competência de
   voz.
5. **STACK → Frontend** — acrescentar `Chrome Extensions (MV3)`.
6. Manter o "AI Voice Agent System" e o "Azure Voice Live Agent" — juntos com o
   call-copilot mostram três abordagens (bots que falam, speech-to-speech
   EU-compliant, copiloto que escuta) = amplitude a sério em voice AI.
