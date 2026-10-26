import { useEffect, useRef, type ReactNode } from "react";

export function Badge({ children, tone = "neutral", title }: { children: ReactNode; tone?: "neutral" | "brand" | "gap" | "warn" | "muted"; title?: string }) {
  const tones = {
    neutral: "bg-paper-sunk text-ink",
    brand: "bg-brand-50 text-brand-800 ring-1 ring-brand-100",
    gap: "bg-gap-soft text-gap",
    warn: "bg-amber-50 text-amber-900 ring-1 ring-amber-200",
    muted: "bg-transparent text-ink-soft ring-1 ring-line",
  };
  return (
    <span title={title} className={`inline-flex items-center rounded px-1.5 py-0.5 text-xs font-medium ${tones[tone]}`}>
      {children}
    </span>
  );
}

export function Card({ children, className = "", as: Tag = "section" }: { children: ReactNode; className?: string; as?: "section" | "article" | "div" }) {
  return <Tag className={`card ${className}`}>{children}</Tag>;
}

/** Horizontal meter for a value in [0, 1]. Always paired with a printed number. */
export function Meter({ value, label, tone = "brand" }: { value: number; label: string; tone?: "brand" | "gap" }) {
  const pct = Math.max(0, Math.min(1, value)) * 100;
  return (
    <div className="h-2 w-full overflow-hidden rounded-full bg-paper-sunk" role="meter" aria-valuemin={0} aria-valuemax={1} aria-valuenow={Number(value.toFixed(3))} aria-label={label}>
      <div className={`h-full rounded-full ${tone === "brand" ? "bg-brand-600" : "bg-gap"}`} style={{ width: `${pct}%` }} />
    </div>
  );
}

export function Dialog({ open, onClose, title, children, wide }: { open: boolean; onClose: () => void; title: string; children: ReactNode; wide?: boolean }) {
  const ref = useRef<HTMLDialogElement>(null);
  useEffect(() => {
    const d = ref.current;
    if (!d) return;
    if (open && !d.open) d.showModal?.();
    if (!open && d.open) d.close?.();
  }, [open]);
  return (
    <dialog
      ref={ref}
      onClose={onClose}
      onCancel={onClose}
      aria-labelledby="dialog-title"
      className={`w-[calc(100%-2rem)] ${wide ? "max-w-4xl" : "max-w-lg"} rounded-lg border border-line bg-paper-raised p-0 text-ink shadow-xl backdrop:bg-ink/30`}
    >
      {open && (
        <div className="p-5">
          <div className="mb-4 flex items-start justify-between gap-4">
            <h2 id="dialog-title" className="text-lg font-semibold">
              {title}
            </h2>
            <button className="rounded p-1 text-ink-soft hover:bg-paper-sunk" onClick={onClose} aria-label="Close dialog">
              ✕
            </button>
          </div>
          {children}
        </div>
      )}
    </dialog>
  );
}

export function PageHeader({ title, subtitle, actions }: { title: string; subtitle?: ReactNode; actions?: ReactNode }) {
  return (
    <header className="mb-6 flex flex-wrap items-end justify-between gap-4">
      <div>
        <h1 className="text-2xl font-semibold">{title}</h1>
        {subtitle && <p className="mt-1 max-w-2xl text-sm text-ink-soft">{subtitle}</p>}
      </div>
      {actions && <div className="flex flex-wrap gap-2">{actions}</div>}
    </header>
  );
}

export const pct = (v: number, digits = 0) => `${(v * 100).toFixed(digits)}%`;

export function timeAgo(iso: string | null): string {
  if (!iso) return "";
  const d = new Date(iso);
  const s = (Date.now() - d.getTime()) / 1000;
  if (s < 60) return "just now";
  if (s < 3600) return `${Math.floor(s / 60)} min ago`;
  if (s < 86400) return `${Math.floor(s / 3600)} h ago`;
  return d.toLocaleDateString(undefined, { day: "numeric", month: "short", year: d.getFullYear() === new Date().getFullYear() ? undefined : "numeric" });
}
