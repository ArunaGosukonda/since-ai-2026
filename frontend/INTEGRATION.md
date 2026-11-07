# Frontend ↔ backend integration

**`dsa.pipeline` decides everything**: risk, primary action, steps, decisive questions, which
account signals to ask consent for, and the handoff. The phone demo (`frontend/`) only renders
that decision. No language model is called anywhere in the app.

## Run it

```sh
cd frontend
cp .env.example .env      # ELEVENLABS_API_KEY only (voice); never commit .env
npm install
npm run dev               # http://localhost:8080 (or the next free port)
npm test                  # vitest
```

`/api/classify` spawns `../.venv/bin/python tools/classify_message.py` (set `PYTHON_BIN` to change
it), so the dev server must run inside the repo with the Python environment set up.

Presenter keys (press <kbd>`</kbd> to show the panel): `1` incoming call (live), `A` answer,
`D` decline or hang up, `2` random dataset SMS, `4` DNA Assistant chat, `R` reset.

## The one seam: `POST /api/classify`

`src/routes/api/classify.ts` → `tools/classify_message.py` → `dsa.pipeline.assess(case)`.
Text goes to Python as JSON on stdin (no shell). The child gets only `PATH` and
`PYTHONDONTWRITEBYTECODE`, never the API keys. 8 s server timeout; 502 `pipeline unavailable` on error.

Request:

```ts
{ mode?: "sms" | "chat",   // default "sms"
  sender?: string,         // sms only
  body: string,            // the text message, or the user's own description (all chat turns joined)
  lang: "en" | "fi" | "sv",
  granted?: string[] }     // consent-gated signal paths the user said "Yes, check" to
```

- `sms`: a `suspicious_message` case with the text as an `sms` artifact (unchanged from before).
- `chat`: a `clicked_link` case, entry point `operator_app_chat`, the text as `opening_message` and no
  artifact (like dev case `DSA-D-0013`, where the user describes what they did).
- Both merge the **synthetic** demo account `tools/demo_profile.json` (`user_identified: true`).
  Paths marked `requires_consent` in `signal_dictionary.json` are listed in `consent.requires_consent`
  and hold `"available_with_consent"` (as in `sim/PROTOCOL.md`) until granted; a granted path gets its
  value and goes in `consent.pre_granted`.

Response: the original five fields (`risk_level, urgency, primary_action, advice_text, situation_id`)
plus `steps, questions_asked, question_topics, consent_requested_for, escalation_required,
escalation_target, citations, signals_used, confidence, trace` (names from
`contracts/decision.schema.json`) and `facts` (`contracts/facts.schema.json` records, with evidence,
for `trace.facts_used`). Typed as `Decision` in `src/lib/decision.ts`.

## How the UI renders it

| Pipeline field | Screen |
|---|---|
| `risk_level` | none → "no signs of a scam" (green), low → "check it yourself" (neutral), medium → "be careful", high / critical → "scam" (`stageOf`) |
| `primary_action` | SMS main button label (`i18n.pipe.actions`). "Delete and report" only for `do_not_interact_and_delete` |
| `advice_text` | SMS advice box; chat headline = its first sentence |
| `steps` | numbered list, all of them (never cut) |
| `questions_asked` | chat: shown as text ("one thing I don't know yet"); the answer is already given from the riskier branch. The user can type more, which is joined with the earlier turns and checked again |
| `consent_requested_for` | chat: "Yes, check" / "No". Yes re-runs with `granted` = exactly those paths and marks the answer "Checked your DNA account (demo data)"; No keeps the answer and calls nothing |
| `escalation_required`, `primary_action` | chat "Talk to DNA support" only when there is a handoff or a contact-DNA action (static demo note) |
| `trace`, `facts`, `signals_used`, `citations` | "Why this advice" panel |

**Fail closed.** If `/api/classify` fails or times out, the SMS and the chat show "Couldn't check this
right now. Don't act on it; check it in the official app." Never "safe". The browser keyword copy
(`src/generated/dangerPatterns.json`) only underlines phrases; it never clears a message.

## Underlined danger phrases

Not hand-written. `tools/export_frontend_patterns.py` exports the `SENDER`, `LURE`, `THREAT` and
`FEE` patterns from `dsa/facts_keyword.py` to `src/generated/dangerPatterns.json`;
`src/lib/dangerPhrases.ts` applies them with the same accent folding. After editing those
patterns, re-run the exporter; `tests/test_frontend_patterns.py` fails while the copy is stale.

## Voice

- Speech to text (chat mic button): before the first use, a one-line notice asks to allow the
  microphone. Until the user taps Allow, nothing is recorded, no ElevenLabs token is fetched and the
  browser recogniser is not started. It fills the text box; the user presses Send.
- Read aloud: off until tapped. A note says the answer text (ours, not the user's) is sent to
  ElevenLabs. Falls back to the browser voice.

## Live calls

Answering a call asks for microphone consent, then transcribes the caller live
(`src/lib/useLiveCall.ts`): ElevenLabs realtime STT first, the browser's own speech recognition when
ElevenLabs cannot start or drops during the call (quota, network). Nothing is scripted. After every
finished sentence, `/api/classify` with `mode: "call"` judges everything said so far: the transcript
becomes a `call` artifact in a `suspicious_call` case (`tools/classify_message.py`, like DSA-D-0003).
The call screen maps `risk_level` to Listening / Be careful / Scam, never lowers it during a call, and
the scam warning shows the first sentence of `advice_text`. If the pipeline is unreachable the stage
stays where it was; the call is never shown as safe without a decision.

## Demo-only (not wired to anything real)

- `tools/demo_profile.json`: synthetic account data, never a real customer.
- SMS examples come from the dev set (`tools/export_sms_examples.py` → `src/generated/smsExamples.json`,
  CC BY 4.0, Since AI ry). Inputs only, no answers.
- "Block and report", "Talk to DNA support", the SMS action buttons other than delete, "Call Anna" only
  change the screen.
- Outgoing third-party calls: ElevenLabs STT (`sttTokenFn` + browser WebSocket) and TTS (`/api/tts`)
  only. Both are unauthenticated proxies; put them behind auth or rate limits before any public deployment.
