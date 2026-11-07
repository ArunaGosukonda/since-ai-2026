# Frontend ↔ backend integration

The phone demo (`frontend/`) currently gets its risk judgements from a Gemini prompt (Interactions API, `gemini-3.1-flash-lite`) in
`src/lib/live.server.ts`. The real decisions should come from the Python pipeline (`dsa/`).
This note lists the two seams to replace, the shapes the UI expects, and what is still
demo-only.

## Run it

```sh
cd frontend
cp .env.example .env      # fill in GEMINI_API_KEY, ELEVENLABS_API_KEY (never commit .env)
npm install
npm run dev               # http://localhost:8080 (or the next free port)
npm test                  # vitest
```

Presenter keys (press <kbd>`</kbd> to show the panel): `1` incoming call, `A` answer, `D` decline or
hang up, `2` / `3` scam / genuine SMS, `4` DNA Assistant chat, `L` live / scripted, `R` reset.

## Seam 1: risk analysis (calls and SMS)

`analyzeFn` in `src/lib/live.functions.ts` is called once per transcribed call sentence and once
per SMS.

Request (validated with zod):

```ts
{ kind: "call" | "sms", text: string, transcript_so_far: string,
  caller_signals: Record<string, unknown>, lang: "en" | "fi" | "sv" }
```

Response the UI reads (`src/lib/liveAgents.ts`, type `Analysis`):

```ts
{ stage: "listening" | "careful" | "scam" | "safe",
  flagged_phrases?: string[],            // exact substrings of `text`; underlined in the call
  reason?: { en?: string, fi?: string, sv?: string },   // shown in the scam warning
  action?: string }                      // action_vocabulary.json id
```

Suggested mapping from `contracts/decision.schema.json`:

| UI field | from the pipeline decision |
|---|---|
| `stage` | `risk_level`: none/low → `safe`, medium → `careful`, high/critical → `scam` (call: `listening` until the first judgement) |
| `reason[lang]` | `advice_text` (or its first sentence) in the user's language |
| `action` | `primary_action` |
| `flagged_phrases` | evidence quotes of the keyword facts, if exposed |

The UI never lowers risk below a client-side floor (`safetyFloor` in `src/lib/live.ts`: any request
to read or give a code is `scam`), and it falls back to the scripted result if the call fails or
takes longer than 6 s (`LIVE_TIMEOUT_MS`).

## Seam 2: DNA Assistant chat

`chatFn` in `src/lib/live.functions.ts`. Request: `{ history: {role, content}[], lang, consent: boolean }`.
Account data is only sent after the user granted consent (`ACCOUNT_DATA` in `live.server.ts` is a
fake placeholder; replace it with the real consent-gated signals).

The UI renders exactly one of (`ChatJson` in `src/lib/liveAgents.ts`):

```ts
{ type: "question", text }                                   // shows Yes / No / Not sure chips
{ type: "consent_request", text, fields: string[] }          // shows "Yes, check" / "No"
{ type: "final", text?, answer: { stage, headline, steps: string[] /* max 4 */ } }
```

These map onto the pipeline's `questions_asked`, `consent_requested_for` and
`advice_text` / `steps`. Anything else falls back to the scripted chat (`getTurvaReply` in
`src/lib/chat.ts`).

Voice in the chat: the mic button is speech to text only (it fills the text box; the user
presses Send). Each reply has a read-aloud button; once used, every later reply is read out too,
until "Stop reading". A typed or dictated "yes / no / not sure" answers a pending question like the
buttons (`answerTurn` in `src/lib/chat.ts`; consent is only given on a clear yes).

## Underlined danger phrases

Not hand-written. `tools/export_frontend_patterns.py` exports the `SENDER`, `LURE`, `THREAT` and
`FEE` patterns from `dsa/facts_keyword.py` to `src/generated/dangerPatterns.json`;
`src/lib/dangerPhrases.ts` applies them with the same accent folding. After editing those
patterns, re-run the exporter; `tests/test_frontend_patterns.py` fails while the copy is stale.

## Demo-only (not wired to anything real)

- Scripted call: caller lines in `src/lib/i18n.ts` (`call.lines`), risk steps in
  `src/lib/callScript.ts` (`scriptedResults`), one recording of the whole call
  (`CALL_AUDIO` = `public/audio/call_1.mp3`, English; the text is timed to it).
- Scripted chat: one story per entry point (`ChatStory`: `call`, `sms`, or `sim` from the app
  icon) in `src/lib/i18n.ts` (`chat.stories`); consent fields use `signal_dictionary.json` ids.
- Text messages already use the real pipeline: `POST /api/classify` (`src/routes/api/classify.ts`) runs
  `tools/classify_message.py`, which wraps the message in a minimal `suspicious_message` case and calls
  `dsa.pipeline.assess`. Risk `medium`/`high`/`critical` shows the warning with the pipeline's
  `advice_text`. Examples come from the dev set (`tools/export_sms_examples.py` →
  `src/generated/smsExamples.json`, CC BY 4.0, Since AI ry); the inbox also has a box to type a
  message from "Unknown". Without Python, the browser falls back to the exported keyword patterns.
- "Block and report", "Talk to DNA support", "Call Anna" only change the screen.
- `/api/tts` and `sttTokenFn` are unauthenticated proxies to ElevenLabs. Fine locally; put them
  behind auth or rate limits before any public deployment.
