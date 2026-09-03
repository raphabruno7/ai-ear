# DEMO — como apresentar o call-copilot

Runbook de 5–8 min para uma demo (vídeo, chamada, apresentação). Tudo aqui corre
**sem uma chamada LiveKit ao vivo** (essa parte está bloqueada em Wi-Fi/CGNAT —
ver `HANDOFF.md`). O pipeline mostra-se por peças.

## Antes de começar (5 min)

```bash
cd listener
.venv/bin/python healthcheck.py        # confirma STS + Transcribe + SES + Supabase 4/4

# terminal A — servidor WS + campos falsos para a extensão
.venv/bin/python ws_push.py --session demo-1

# terminal B — dashboard
cd ../web && npm run dev                # :3000 (ou :3001)
```

Abre em separadores: `/` · `/eval` · `/costs` · `/demo-scheduler` ·
o dashboard do Langfuse.

Carrega a extensão uma vez: `chrome://extensions` → Developer mode →
**Load unpacked** → `extension/` → no popup mete `ws://localhost:8765` + `demo-1`.

---

## Guião

### 1. O problema (30s)
"Um copiloto que **escuta** uma chamada entre uma coordenadora de cuidados
veterinários e uma família. Nunca fala. Transcreve, extrai os campos de
agendamento/clínicos em tempo real, e escreve-os no sistema de scheduling via
extensão Chrome. Segundo workstream: email de briefing pré-visita."

Mostra o diagrama do `README.md`.

### 2. STT + fiabilidade (1 min)
`listener/transcribe_stream.py` — uma stream AWS Transcribe por interlocutor,
16 kHz PCM das frames LiveKit.

**Talking point:** *"O Transcribe fecha a stream em silêncio — a faixa de uma
pessoa fica muda enquanto a outra fala. Diagnostiquei mal como queda de rede
durante várias tentativas; a causa real era o timeout de silêncio. O fix reabre
a stream no próximo envio que falha. Conclusão de chamada no fixture: 30% → 100%."*

### 3. Extração + A/B (2 min)
`listener/extract.py` — `EXTRACT_BACKEND` troca entre Gemini (Vertex AI) e
Claude Haiku (Bedrock) em runtime, atrás da mesma interface. Tool use forçado no
Bedrock, JSON no Gemini, merge só sobrescreve com confiança maior, `finalize()`
faz uma passagem final sobre o transcript inteiro.

Abre `/eval`. **Money talking point:**
*"A/B nas 25 amostras difíceis. Gemini 47%/67% exact/fonético nos nomes, Haiku
40%/60%. Mas o essencial: **os dois modelos falham exatamente as mesmas
amostras** — 'Seán Mac Cárthaigh' → 'Sean McCarvey' nos dois. O input é o mesmo
transcript. **Isolei o gargalo: é o STT (en-US) a estropiar fonemas
não-ingleses, não o LLM.** A alavanca de accuracy é custom vocabulary no
Transcribe ou um STT mais robusto a sotaques — não trocar de modelo."*

### 4. Latência / custo (1 min)
Abre `/costs`. `listener/bench_latency.py` mede tempo-até-primeiro-valor.

**Talking point:** *"O debounce (uma extração a cada ~12s em vez de a cada turno)
corta ~65% das chamadas ao LLM **sem custo de latência** — medi: os tempos são
iguais ou melhores, porque per-turn serializa 14 chamadas sobre fragmentos sem
contexto. O '1 min de lag num campo' que a spec menciona é posição no
transcript: `preferred_time` só é combinado perto do fim — o `finalize()` é a
rede de segurança."*

### 5. Observability (30s)
Dashboard do Langfuse. Abre um trace `eval:gemini-flash`.

**Talking point:** *"Cada chamada ao modelo é um trace com input, output, tokens
e custo. 59 traces do A/B. Instrumento o que construo."*

### 6. A entrega — extensão (1 min)
`/demo-scheduler` com a extensão ligada (badge ●). Os campos preenchem-se a cada
~2.5s à medida que o `ws_push` empurra.

**Talking point:** *"MV3 — service worker faz de cliente WebSocket, content
script preenche `[data-copilot-field]`. Fill React-safe: native setter + evento
`input` bubbling, senão o React sobrescreve no próximo render."*

### 7. Isolamento + incidentes (30s)
`loadtest/run.py` — 6 salas concorrentes, assert de isolamento cross-session.
RLS por `vcc_id` (migração 005). `HEALTH.md` — cada modo de falha visto com
sintoma → check → fix → rollback.

---

## Se perguntarem "posso ver uma chamada real?"

Honestidade: *"O e2e com uma chamada LiveKit ao vivo está bloqueado por
conectividade — o WebRTC media falha atrás de CGNAT numa rede móvel. O
`test_transcribe_wiring.py` corre esse caminho com o fixture (49s, 2 speakers,
14 finais). O resto do pipeline — extração, persistência, Langfuse, extensão —
está provado peça a peça."*

Não inventes uma chamada real que não aconteceu.

## As 3 frases que ficam

1. "Isolei o gargalo de accuracy: é o STT, não o LLM — os dois modelos do A/B
   falham as mesmas amostras."
2. "O debounce corta 65% das chamadas ao LLM sem custo de latência — medido."
3. "Instrumento o que construo: custo por chamada, latência p50/p95, accuracy em
   golden set, traces no Langfuse."
