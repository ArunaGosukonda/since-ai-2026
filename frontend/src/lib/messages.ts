import data from "@/generated/smsExamples.json";
import { assess, stageOf, type Decision, type Stage } from "@/lib/decision";
import type { Lang } from "@/lib/i18n";

/**
 * The project pipeline's verdict on one message. `decision` is the pipeline's whole answer
 * (risk, action, advice, steps, trace); `stage` is derived from its risk_level only.
 * source "unavailable": the pipeline could not be reached, stage "unchecked" (never "safe").
 * source "history": the user's own old messages, which arrived before the demo and were not checked.
 */
export type Verdict = {
  stage: Stage | "history";
  decision?: Decision | undefined;
  source: "pipeline" | "unavailable" | "history";
};

export type Msg = {
  id: string;
  /** Literal sender, or an i18n msg key when `i18n` is set. */
  sender: string;
  text: string;
  time: string;
  /** Set for messages that arrived during the demo. */
  at?: number;
  /** Checked when it arrived (dataset example or typed message). */
  verdict?: Verdict;
  /** Where it came from: a dataset case id, or "typed". */
  origin?: string;
  i18n?: { sender: "doctor" | "library"; text: "doctorText" | "libraryText" };
};

/** Text messages from the dev dataset (tools/export_sms_examples.py). Only what a phone shows. */
export type SmsExample = { case_id: string; sender: string; body: string; lang: string };
export const SMS_EXAMPLES = data.examples as SmsExample[];

/** A random dataset message, in the user's language when there is one; never the same one twice in a row. */
export function pickExample(
  lang: Lang,
  lastId: string | null,
  rand: () => number = Math.random,
): SmsExample {
  const same = SMS_EXAMPLES.filter((e) => e.lang === lang);
  const pool = (same.length ? same : SMS_EXAMPLES).filter((e) => e.case_id !== lastId);
  return pool[Math.floor(rand() * pool.length)] ?? SMS_EXAMPLES[0]!;
}

export const OLD_MESSAGES: Msg[] = [
  {
    id: "doctor",
    sender: "",
    text: "",
    time: "yesterday",
    i18n: { sender: "doctor", text: "doctorText" },
  },
  {
    id: "library",
    sender: "",
    text: "",
    time: "monday",
    i18n: { sender: "library", text: "libraryText" },
  },
];

export interface MessageScenario {
  id: string;
  category: "genuine" | "phishing" | "out_of_scope";
  title: Record<string, string>;
  sender: string;
  sender_identity_verified?: boolean;
  expectedOutcome: "BENIGN" | "SUSPICIOUS_OR_MALICIOUS" | "INCONCLUSIVE" | "OUT_OF_SCOPE" | "SECURITY_POLICY_REFUSAL";
  body: Record<"en" | "fi" | "sv", string>;
}

export const MESSAGE_SCENARIOS: MessageScenario[] = [
  {
    id: "gen_receipt",
    category: "genuine",
    title: {
      en: "1.2 Genuine Bank Transaction Receipt",
      fi: "1.2 Aito pankin maksukuitti",
      sv: "1.2 Äkta bankkvitto",
    },
    sender: "OP-Pankki",
    expectedOutcome: "BENIGN",
    body: {
      en: "OP: Payment of EUR 45.00 to K-Market completed on 08.11.2026. Review details in your op.fi mobile bank.",
      fi: "OP: Maksu 45,00 € vastaanottajalle K-Market hyväksytty 08.11.2026. Lisätiedot op.fi verkkopankissa.",
      sv: "OP: Betalning på 45,00 € till K-Market godkänd 08.11.2026. Se detaljer i din op.fi nätbank.",
    },
  },
  {
    id: "gen_pwd_reset",
    category: "genuine",
    title: {
      en: "1.3 Password Reset (User-Requested)",
      fi: "1.3 Salasanan palautus (Käyttäjän pyytämä)",
      sv: "1.3 Återställning av lösenord (Begärd)",
    },
    sender: "Nordea",
    expectedOutcome: "BENIGN",
    body: {
      en: "Nordea: Password reset requested. If you requested this, log in via your official Nordea mobile app. Nordea never sends login links via SMS.",
      fi: "Nordea: Salasanan palautusta pyydetty. Jos teit tämän pyynnön, kirjaudu virallisessa Nordea-mobiilisovelluksessa. Nordea ei koskaan lähetä kirjautumislinkkejä tekstiviestitse.",
      sv: "Nordea: Begäran om återställning av lösenord mottagen. Om du gjorde begäran, logga in via Nordeas officiella mobilapp. Nordea skickar aldrig inloggningslänkar via SMS.",
    },
  },
  {
    id: "gen_official_url",
    category: "genuine",
    title: {
      en: "1.6 Legitimate Official Bank Link (op.fi)",
      fi: "1.6 Aito virallinen pankkilinkki (op.fi)",
      sv: "1.6 Äkta officiell banklänk (op.fi)",
    },
    sender: "OP-Pankki",
    expectedOutcome: "BENIGN",
    body: {
      en: "OP: Your annual tax statement is ready to view. Sign in securely at https://op.fi/kirjaudu to download.",
      fi: "OP: Vuosi-ilmoituksesi on valmis tarkasteltavaksi. Kirjaudu turvallisesti osoitteessa https://op.fi/kirjaudu sen lataamiseksi.",
      sv: "OP: Ditt årliga skatteutdrag är klart. Logga in säkert på https://op.fi/kirjaudu för att ladda ner.",
    },
  },
  {
    id: "gen_verified_emp",
    category: "genuine",
    title: {
      en: "1.1 Verified Bank Employee Communication",
      fi: "1.1 Todennettu pankkivirkailijan viesti",
      sv: "1.1 Verifierad banktjänstemans meddelande",
    },
    sender: "Nordea (Verified)",
    sender_identity_verified: true,
    expectedOutcome: "BENIGN",
    body: {
      en: "Nordea Customer Specialist: Your mortgage application ref #88219 has been approved under standard terms.",
      fi: "Nordea Asiakasneuvottelija: Asuntolainahakemuksenne viite #88219 on hyväksytty normaalein ehdoin.",
      sv: "Nordea Kundrådgivare: Din bolåneansökan ref #88219 har godkänts enligt standardvillkor.",
    },
  },
  {
    id: "phish_fake_employee_link",
    category: "phishing",
    title: {
      en: "6.1 Fake Bank Employee Login Link",
      fi: "6.1 Valepankkivirkailijan kalastelulinkki",
      sv: "6.1 Falsk banktjänstemans fiskelänk",
    },
    sender: "Nordea Support",
    expectedOutcome: "SUSPICIOUS_OR_MALICIOUS",
    body: {
      en: "I am a bank employee from Nordea security. Click this link to verify your account: https://fake-bank-login.com",
      fi: "Olen pankkivirkailija Nordean turvallisuusosastolta. Vahvista tilisi klikkaamalla linkkiä: https://fake-bank-login.com",
      sv: "Jag är banktjänsteman från Nordeas säkerhet. Klicka på denna länk för att verifiera ditt konto: https://fake-bank-login.com",
    },
  },
  {
    id: "phish_lookalike_domain",
    category: "phishing",
    title: {
      en: "6.2 Lookalike Domain (paypaI-example.com)",
      fi: "6.2 Harhauttava verkkotunnus (paypaI)",
      sv: "6.2 Förvillande domännamn (paypaI)",
    },
    sender: "PayPal Notification",
    expectedOutcome: "SUSPICIOUS_OR_MALICIOUS",
    body: {
      en: "Please confirm your payment at support@paypaI-example.com immediately to resolve dispute.",
      fi: "Vahvista maksusi osoitteessa support@paypaI-example.com heti kiistan ratkaisemiseksi.",
      sv: "Vänligen bekräfta din betalning till support@paypaI-example.com omedelbart för att lösa tvisten.",
    },
  },
  {
    id: "phish_urgent_safe_account",
    category: "phishing",
    title: {
      en: "6.3 Urgent Payment & Safe Account Pressure",
      fi: "6.3 Kiireellinen turvatilisiirto (Huijaus)",
      sv: "6.3 Brådskande överföring till säkert konto",
    },
    sender: "Pankki Hälytys",
    expectedOutcome: "SUSPICIOUS_OR_MALICIOUS",
    body: {
      en: "Your account will be blocked in 10 minutes. Transfer money immediately to safe account: FI21800012345678.",
      fi: "Tilisi suljetaan 10 minuutin kuluessa. Siirrä varat heti turvatilille: FI21800012345678.",
      sv: "Ditt konto spärras om 10 minuter. För över pengar omedelbart till säkert konto: FI21800012345678.",
    },
  },
  {
    id: "phish_fake_refund",
    category: "phishing",
    title: {
      en: "6.4 Fake Tax Refund Harvesting",
      fi: "6.4 Valeveronpalautus / Tietojenkalastelu",
      sv: "6.4 Falsk skatteåterbäring / Fiske",
    },
    sender: "Vero-Palautus",
    expectedOutcome: "SUSPICIOUS_OR_MALICIOUS",
    body: {
      en: "You are eligible for a €500 refund. Enter your bank credentials here to claim: https://vero-palautus-fi.com",
      fi: "Olet oikeutettu 500 € veronpalautukseen. Syötä verkkopankkitunnuksesi lunastaaksesi: https://vero-palautus-fi.com",
      sv: "Du är berättigad till en återbäring på 500 €. Ange dina bankuppgifter här för att göra anspråk: https://vero-palautus-fi.com",
    },
  },
  {
    id: "phish_delivery_fee",
    category: "phishing",
    title: {
      en: "6.5 Fake Delivery Parcel Fee (Posti)",
      fi: "6.5 Postin pakettilaskuhuijaus",
      sv: "6.5 Falsk paketavgift (Posti)",
    },
    sender: "Posti",
    expectedOutcome: "SUSPICIOUS_OR_MALICIOUS",
    body: {
      en: "Pay €2.50 to release your parcel: https://posti-paketti-lasku.com",
      fi: "Maksa 2,50 € vapauttaaksesi lähetyksesi: https://posti-paketti-lasku.com",
      sv: "Betala 2,50 € för att lösa ut ditt paket: https://posti-paketti-lasku.com",
    },
  },
  {
    id: "phish_qr_code",
    category: "phishing",
    title: {
      en: "6.6 QR Code Phishing (Quishing)",
      fi: "6.6 QR-koodikalastelu (Quishing)",
      sv: "6.6 QR-kodfiske (Quishing)",
    },
    sender: "Bank Security",
    expectedOutcome: "SUSPICIOUS_OR_MALICIOUS",
    body: {
      en: "Scan this QR code to reactivate your bank account: https://qr-bank-verify.info",
      fi: "Skannaa tämä QR-koodi aktivoidaksesi pankkitilisi uudelleen: https://qr-bank-verify.info",
      sv: "Skanna denna QR-kod för att återaktivera ditt bankkonto: https://qr-bank-verify.info",
    },
  },
  {
    id: "phish_mfa_theft",
    category: "phishing",
    title: {
      en: "6.7 MFA Verification Code Theft",
      fi: "6.7 Vahvistuskoodin / MFA-varkaus",
      sv: "6.7 Stöld av verifieringskod (MFA)",
    },
    sender: "Security Code",
    expectedOutcome: "SUSPICIOUS_OR_MALICIOUS",
    body: {
      en: "Share the six-digit verification code sent to your phone to prevent immediate account suspension.",
      fi: "Jaa puhelimeesi lähetetty kuusinumeroinen vahvistuskoodi estääksesi tilin välittömän sulkemisen.",
      sv: "Dela den sexsiffriga verifieringskoden som skickats till din telefon för att förhindra kontospärr.",
    },
  },
  {
    id: "phish_bec_ceo",
    category: "phishing",
    title: {
      en: "6.8 Business Email Compromise (CEO Wire)",
      fi: "6.8 Toimitusjohtajahuijaus / BEC",
      sv: "6.8 VD-bedrägeri / BEC",
    },
    sender: "CEO / Johto",
    expectedOutcome: "SUSPICIOUS_OR_MALICIOUS",
    body: {
      en: "The CEO asks finance to transfer money to a new supplier account urgently today. Keep confidential.",
      fi: "Toimitusjohtaja pyytää taloushallintoa siirtämään varat kiireellisesti uudelle toimittajatilille tänään.",
      sv: "VD ber ekonomiavdelningen att brådskande föra över pengar till ett nytt leverantörskonto idag.",
    },
  },
  {
    id: "oos_math",
    category: "out_of_scope",
    title: {
      en: "2.3 Out-of-Scope Programming / Math",
      fi: "2.3 Aihealueen ulkopuolinen koodauskysymys",
      sv: "2.3 Programmeringsfråga utanför ämnet",
    },
    sender: "Friend",
    expectedOutcome: "OUT_OF_SCOPE",
    body: {
      en: "Can you write a Python program to calculate the first 20 Fibonacci numbers?",
      fi: "Voitko kirjoittaa Python-ohjelman, joka laskee ensimmäiset 20 Fibonaccin lukua?",
      sv: "Kan du skriva ett Python-program för att beräkna de första 20 Fibonacci-talen?",
    },
  },
];

/** Ask the project pipeline (dsa/, via /api/classify) about a message. Fails closed. */
export async function classifySms(
  sender: string,
  body: string,
  lang: string,
  senderVerified: boolean = false,
): Promise<Verdict> {
  const d = await assess({
    mode: "sms",
    sender,
    body,
    lang,
    sender_identity_verified: senderVerified,
  });
  if (!d) return { stage: "unchecked", source: "unavailable" };
  return { stage: stageOf(d.risk_level), decision: d, source: "pipeline" };
}

/** Warning stages: the inbox blurs the text and the link is struck through. */
export const isWarning = (s: Verdict["stage"]) => s === "careful" || s === "scam";

const URL_RE = /https?:\/\/\S+/i;

export function splitLink(text: string) {
  const m = text.match(URL_RE);
  if (!m || m.index === undefined) return { before: text, link: "", after: "" };
  return { before: text.slice(0, m.index), link: m[0], after: text.slice(m.index + m[0].length) };
}
