import { afterEach, describe, expect, it, vi } from "vitest";
import { answerTurn, storyText, type ChatTurn, type TurvaReply } from "./chat";
import { getTurvaReplyLive, grantedPaths, userDescription } from "./liveAgents";
import { firstSentence, type Decision } from "./decision";
import { i18n } from "./i18n";
import actionVocabulary from "../../../instructions/DNA_Digital_Security_Assistant_SimSet_v2.0.1/data/reference/action_vocabulary.json";
import signalDictionary from "../../../instructions/DNA_Digital_Security_Assistant_SimSet_v2.0.1/data/reference/signal_dictionary.json";

const decision = (over: Partial<Decision> = {}): Decision => ({
  risk_level: "critical",
  urgency: "immediate",
  primary_action: "contact_operator_support",
  advice_text: "Someone may be moving your number. Act now.",
  situation_id: "S09",
  steps: ["a", "b", "c", "d", "e", "f"],
  questions_asked: ["Did you tell anyone a code or PIN?"],
  question_topics: ["code_shared"],
  consent_requested_for: ["subscription.recent_events"],
  escalation_required: false,
  escalation_target: null,
  citations: [],
  signals_used: [],
  confidence: 0.55,
  trace: {
    situation_id: "S09",
    facts_used: [],
    rule_ids: ["MATCH:S09.when[1]"],
    model: null,
    signals_used: [],
    consent_requested: ["subscription.recent_events"],
    consent_granted: ["subscription.recent_events"],
  },
  facts: {},
  ...over,
});

const finalWithConsent: TurvaReply = {
  role: "turva",
  type: "final",
  stage: "scam",
  headline: "x",
  steps: [],
  questions: [],
  consentFor: ["subscription.recent_events"],
  checked: false,
  decision: null,
};

describe("typed or dictated answers", () => {
  it("treats a clear yes / no to a consent request as the consent buttons, keeping the words", () => {
    expect(answerTurn("Yes, go ahead", finalWithConsent)).toEqual({
      role: "user",
      text: "Yes, go ahead",
      value: "consent_yes",
    });
    expect(answerTurn("Kyllä", finalWithConsent).value).toBe("consent_yes");
    expect(answerTurn("Nej", finalWithConsent).value).toBe("consent_no");
  });
  it("never gives consent on an unsure answer, or when nothing was asked", () => {
    expect(answerTurn("Yes, I mean, I'm not sure", finalWithConsent).value).toBeUndefined();
    expect(answerTurn("Yes", { ...finalWithConsent, consentFor: [] }).value).toBeUndefined();
  });
});

describe("chat on the pipeline", () => {
  afterEach(() => vi.unstubAllGlobals());
  const json = (d: Decision) => new Response(JSON.stringify(d), { status: 200 });

  it("sends every free-text turn, joined, as mode chat; consent presses are not text", () => {
    const h: ChatTurn[] = [
      { role: "user", text: "A caller wanted a code." },
      finalWithConsent,
      { role: "user", text: "Yes, check", value: "consent_yes" },
      { role: "user", text: "I read it out." },
    ];
    expect(userDescription(h)).toBe("A caller wanted a code. I read it out.");
    expect(grantedPaths(h)).toEqual(["subscription.recent_events"]);
  });

  it("renders the pipeline decision: headline = first sentence, all steps, questions, consent", async () => {
    const fetch = vi
      .fn()
      .mockResolvedValue(json(decision({ trace: { ...decision().trace, consent_granted: [] } })));
    vi.stubGlobal("fetch", fetch);
    const r = await getTurvaReplyLive([{ role: "user", text: "A caller wanted a code." }], "en");
    const body = JSON.parse(fetch.mock.calls[0]![1].body);
    expect(body).toMatchObject({
      mode: "chat",
      body: "A caller wanted a code.",
      lang: "en",
      granted: [],
    });
    expect(r).toMatchObject({
      type: "final",
      stage: "scam",
      headline: "Someone may be moving your number.",
      questions: ["Did you tell anyone a code or PIN?"],
      consentFor: ["subscription.recent_events"],
      checked: false,
    });
    if (r.type === "final") expect(r.steps).toHaveLength(6); // never cut
  });

  it("re-runs with exactly the granted signals after Yes, and marks the answer as checked", async () => {
    const fetch = vi.fn().mockResolvedValue(json(decision({ consent_requested_for: [] })));
    vi.stubGlobal("fetch", fetch);
    const r = await getTurvaReplyLive(
      [
        { role: "user", text: "A caller wanted a code." },
        finalWithConsent,
        { role: "user", text: "Yes, check", value: "consent_yes" },
      ],
      "en",
    );
    expect(JSON.parse(fetch.mock.calls[0]![1].body).granted).toEqual([
      "subscription.recent_events",
    ]);
    expect(r).toMatchObject({ type: "final", checked: true, consentFor: [] });
  });

  it("keeps the answer after No: no pipeline call, no account data", async () => {
    const fetch = vi.fn();
    vi.stubGlobal("fetch", fetch);
    const r = await getTurvaReplyLive(
      [
        { role: "user", text: "A caller wanted a code." },
        finalWithConsent,
        { role: "user", text: "No", value: "consent_no" },
      ],
      "fi",
    );
    expect(fetch).not.toHaveBeenCalled();
    expect(r).toEqual({ role: "turva", type: "message", text: i18n.fi.pipe.consentDeclined });
  });

  it("fails closed: pipeline down gives the 'couldn't check' card, never safe", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response("down", { status: 502 })));
    const r = await getTurvaReplyLive([{ role: "user", text: "Is my parcel text real?" }], "sv");
    expect(r).toMatchObject({
      type: "final",
      stage: "unchecked",
      headline: i18n.sv.pipe.banner.unchecked,
    });
  });
});

describe("texts", () => {
  it("takes the first sentence of the advice", () => {
    expect(firstSentence("Call your bank now. Then block the card.")).toBe("Call your bank now.");
    expect(firstSentence("No full stop")).toBe("No full stop");
  });
  it("has the pre-filled chat text and every pipeline label in every language", () => {
    for (const lang of ["en", "fi", "sv"] as const) {
      for (const story of ["call", "sms", "sim"] as const)
        expect(storyText(lang, story).prefill).toBeTruthy();
      expect(Object.keys(i18n[lang].pipe.actions).sort()).toEqual(
        Object.keys(actionVocabulary.actions).sort(),
      );
      for (const p of Object.keys(i18n[lang].pipe.consentText))
        if (p !== "other") expect(Object.keys(signalDictionary.signals)).toContain(p);
    }
  });
});
