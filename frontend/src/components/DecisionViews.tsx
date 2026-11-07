import {
  ChevronDown,
  CircleHelp,
  Info,
  OctagonAlert,
  ShieldCheck,
  TriangleAlert,
} from "lucide-react";
import { i18n, type Lang } from "@/lib/i18n";
import type { Decision, Stage } from "@/lib/decision";

/** Look and icon per stage. "neutral" and "unchecked" are deliberately not green. */
export const stageStyle: Record<Stage, { Icon: typeof ShieldCheck; cls: string }> = {
  safe: { Icon: ShieldCheck, cls: "bg-safe text-safe-foreground" },
  neutral: { Icon: Info, cls: "bg-bubble text-ink" },
  careful: { Icon: TriangleAlert, cls: "bg-careful text-careful-foreground" },
  scam: { Icon: OctagonAlert, cls: "bg-scam text-on-dark" },
  unchecked: { Icon: CircleHelp, cls: "bg-bubble text-ink" },
};

export function StageBanner({ stage, lang }: { stage: Stage; lang: Lang }) {
  const { Icon, cls } = stageStyle[stage];
  return (
    <div
      role={stage === "scam" || stage === "careful" ? "alert" : "status"}
      data-stage={stage}
      className={`flex items-center gap-3 rounded-2xl px-5 py-4 text-[20px] font-bold leading-snug ${cls}`}
    >
      <Icon size={30} className="shrink-0" aria-hidden /> {i18n[lang].pipe.banner[stage]}
    </div>
  );
}

export function StageBadge({ stage, lang }: { stage: Stage; lang: Lang }) {
  const { Icon, cls } = stageStyle[stage];
  return (
    <span
      data-stage={stage}
      className={`inline-flex w-fit items-center gap-2 rounded-full px-4 py-1.5 text-[20px] font-bold ${cls}`}
    >
      <Icon size={24} aria-hidden /> {i18n[lang].pipe.stage[stage]}
    </span>
  );
}

/** The pipeline's steps, all of them (a required step is never cut). */
export function StepsList({ steps }: { steps: string[] }) {
  return (
    <ol className="flex flex-col gap-3">
      {steps.map((s, i) => (
        <li key={i} className="flex gap-3">
          <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-dna text-base font-bold text-on-dark">
            {i + 1}
          </span>
          <span className="leading-snug">{s}</span>
        </li>
      ))}
    </ol>
  );
}

/** The pipeline's main action, labelled in the UI language. */
export function actionLabel(action: string, lang: Lang): string {
  const a = i18n[lang].pipe.actions as Record<string, string>;
  return a[action] ?? action;
}

/** Consent text for the signal paths the pipeline asked for (the pipeline carries only the paths). */
export function consentText(paths: string[], lang: Lang): string {
  const c = i18n[lang].pipe.consentText as Record<string, string>;
  const known = paths.map((p) => c[p]).filter(Boolean);
  return known.length ? known.join(" ") : c["other"]!;
}

/** "Why this advice": built only from the pipeline's trace, fact records and citations. */
export function WhyPanel({ decision, lang }: { decision: Decision; lang: Lang }) {
  const w = i18n[lang].pipe.why;
  const tr = decision.trace;
  const match = tr.rule_ids.find((r) => r.startsWith("MATCH:"))?.slice(6) ?? tr.rule_ids[0] ?? "";
  const facts = Object.entries(decision.facts ?? {});
  return (
    <details className="group rounded-xl border-2 border-border px-4 py-3 text-[16px]" data-why>
      <summary className="flex cursor-pointer list-none items-center justify-between gap-2 font-bold text-navy">
        {w.title}
        <ChevronDown size={22} className="transition group-open:rotate-180" aria-hidden />
      </summary>
      <dl className="mt-3 flex flex-col gap-2 leading-snug">
        <div>
          <dt className="font-bold">{w.situation}</dt>
          <dd>
            {tr.situation_id} · {w.rule} <code>{match}</code>
          </dd>
        </div>
        <div>
          <dt className="font-bold">{w.facts}</dt>
          <dd>
            {facts.length ? (
              <ul className="list-disc pl-5">
                {facts.map(([name, f]) => (
                  <li key={name}>
                    <code>
                      {name} = {JSON.stringify(f.value)}
                    </code>{" "}
                    <span className="text-ink-secondary">“{f.evidence}”</span>
                  </li>
                ))}
              </ul>
            ) : (
              w.none
            )}
          </dd>
        </div>
        <div>
          <dt className="font-bold">{w.signals}</dt>
          <dd>{decision.signals_used.length ? decision.signals_used.join(", ") : w.none}</dd>
        </div>
        <div>
          <dt className="font-bold">{w.citations}</dt>
          <dd>{decision.citations.length ? decision.citations.join(", ") : w.none}</dd>
        </div>
      </dl>
    </details>
  );
}
