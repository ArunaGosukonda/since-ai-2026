import { OctagonAlert, ShieldCheck, TriangleAlert } from "lucide-react";
import { i18n, type Lang } from "@/lib/i18n";

export type Risk = "safe" | "careful" | "scam";

const styles: Record<Risk, string> = {
  safe: "bg-safe text-safe-foreground",
  careful: "bg-careful text-careful-foreground",
  scam: "bg-scam text-on-dark",
};

export function RiskBadge({ level, lang }: { level: Risk; lang: Lang }) {
  const Icon = level === "safe" ? ShieldCheck : level === "careful" ? TriangleAlert : OctagonAlert;
  return (
    <div
      className={`flex items-center gap-3 rounded-2xl px-5 py-4 text-[22px] font-bold ${styles[level]}`}
    >
      <Icon
        size={32}
        aria-hidden
        className={level === "careful" ? "text-careful-icon" : undefined}
      />
      {i18n[lang][level]}
    </div>
  );
}
