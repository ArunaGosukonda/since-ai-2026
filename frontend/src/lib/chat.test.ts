import { describe, expect, it } from "vitest";
import {
  getTurvaReply,
  answerTurn,
  storyText,
  type ChatStory,
  type ChatTurn,
  type TurvaReply,
  type UserTurn,
} from "./chat";
import { i18n } from "./i18n";
import signalDictionary from "../../../instructions/DNA_Digital_Security_Assistant_SimSet_v2.0.1/data/reference/signal_dictionary.json";

const first: ChatTurn = { role: "user", text: "A caller wanted a SIM code" };

describe("getTurvaReply scripted exchange", () => {
  it("asks a question first", () => {
    expect(getTurvaReply([first], "en").type).toBe("question");
  });
  it("asks for consent after any chip", () => {
    const h: ChatTurn[] = [
      first,
      getTurvaReply([first], "en"),
      { role: "user", text: "I'm not sure", value: "unsure" },
    ];
    expect(getTurvaReply(h, "en").type).toBe("consent_request");
  });
  it("gives a scam final with 4 steps, checked only after consent yes", () => {
    const q = getTurvaReply([first], "en");
    const base: ChatTurn[] = [first, q, { role: "user", text: "Yes", value: "yes" }];
    const c = getTurvaReply(base, "en");
    const yes = getTurvaReply(
      [...base, c, { role: "user", text: "Yes, check", value: "consent_yes" }],
      "en",
    );
    const no = getTurvaReply([...base, c, { role: "user", text: "No", value: "consent_no" }], "en");
    expect(yes).toMatchObject({ type: "final", stage: "scam", checked: true });
    expect(no).toMatchObject({ type: "final", stage: "scam", checked: false });
    if (yes.type === "final") expect(yes.steps).toHaveLength(4);
  });
});

describe("typed or dictated answers", () => {
  const consent: TurvaReply = {
    role: "turva",
    type: "consent_request",
    text: "May I check?",
    fields: [],
  };
  const question: TurvaReply = { role: "turva", type: "question", text: "Did you read the code?" };
  it("treats a clear yes / no to the consent request as the consent buttons, keeping the words", () => {
    expect(answerTurn("Yes, go ahead", consent).text).toBe("Yes, go ahead");
    expect(answerTurn("Yes, go ahead", consent).value).toBe("consent_yes");
    expect(answerTurn("Kyllä", consent).value).toBe("consent_yes");
    expect(answerTurn("Nej", consent).value).toBe("consent_no");
  });
  it("never gives consent on an unsure answer", () => {
    expect(answerTurn("Yes, I mean, I'm not sure", consent).value).toBeUndefined();
  });
  it("maps yes / no / not sure to the question chips, else free text", () => {
    expect(answerTurn("Yeah I did", question).value).toBe("yes");
    expect(answerTurn("En tiedä", question).value).toBe("unsure");
    expect(answerTurn("He called me about my bank", question).value).toBeUndefined();
  });
});

describe("chat story follows where it was opened from", () => {
  const SIGNALS = Object.keys(signalDictionary.signals);
  const run = (story: ChatStory) => {
    const u = (text: string, value?: NonNullable<UserTurn["value"]>): UserTurn => ({
      role: "user",
      text,
      ...(value ? { value } : {}),
    });
    const q = getTurvaReply([u("x")], "en", story);
    const c = getTurvaReply([u("x"), q, u("No", "no")], "en", story);
    const f = getTurvaReply(
      [u("x"), q, u("No", "no"), c, u("Yes, check", "consent_yes")],
      "en",
      story,
    );
    return { q, c, f };
  };
  it("asks about codes after the bank call and about the link after the parcel text", () => {
    expect(run("call").q).toMatchObject({ type: "question", text: i18n.en.chat.stories.call.q1 });
    expect(run("sms").q).toMatchObject({ type: "question", text: i18n.en.chat.stories.sms.q1 });
    expect(run("call").f).toMatchObject({
      type: "final",
      headline: i18n.en.chat.stories.call.headline,
    });
  });
  it("only asks consent for signals that exist in the dataset", () => {
    for (const story of ["call", "sms", "sim"] as const) {
      const c = run(story).c;
      expect(c.type).toBe("consent_request");
      if (c.type === "consent_request") for (const f of c.fields) expect(SIGNALS).toContain(f);
    }
  });
  it("has every story in every language", () => {
    for (const lang of ["en", "fi", "sv"] as const)
      for (const story of ["call", "sms", "sim"] as const)
        expect(storyText(lang, story).steps).toHaveLength(4);
  });
});
