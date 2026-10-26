import { useState } from "react";
import { Link } from "react-router-dom";
import type { FeatureKey, RankedCandidate } from "../../api/types";
import { Button } from "../../components/ui/Button";
import { Badge, Card } from "../../components/ui/Display";
import { ContributionBar, ExplanationPanel } from "./ExplanationPanel";

interface Props {
  c: RankedCandidate;
  labels: Record<FeatureKey, string>;
  vacantRoles: string[];
  canInvite: boolean;
  selected: boolean;
  onSelect: (v: boolean) => void;
  onInvite: (role: string | null) => Promise<void>;
  onHover?: (c: RankedCandidate | null) => void;
}

export function CandidateCard({ c, labels, vacantRoles, canInvite, selected, onSelect, onInvite, onHover }: Props) {
  const [open, setOpen] = useState(false);
  const [role, setRole] = useState<string>(c.explanation.role?.role ?? "");
  const [busy, setBusy] = useState(false);
  const p = c.profile;
  const panelId = `explain-${p.user_id}`;

  return (
    <Card as="article" className="p-4">
      <div onMouseEnter={() => onHover?.(c)} onMouseLeave={() => onHover?.(null)} onFocus={() => onHover?.(c)}>
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div className="flex items-start gap-3">
            <span className="num mt-0.5 w-7 text-right text-lg font-semibold text-ink-faint" aria-label={`Rank ${c.rank}`}>
              {c.rank}
            </span>
            <div>
              <h3 className="font-semibold">
                <Link to={`/students/${p.user_id}`} className="hover:underline">
                  {p.display_name}
                </Link>
                {p.handle && <span className="ml-1.5 text-sm font-normal text-ink-faint">@{p.handle}</span>}
              </h3>
              <p className="text-xs text-ink-soft">
                {[p.year ? `Year ${p.year}` : null, p.branch, p.primary_roles.join(" / ") || "roles not stated"].filter(Boolean).join(" · ")}
              </p>
            </div>
          </div>
          <div className="text-right">
            <p className="num text-lg font-semibold" title="Relative ranking value for this team's request — not a probability of success">
              {c.score.toFixed(2)}
            </p>
            <p className="text-[11px] text-ink-faint">ranking score</p>
          </div>
        </div>

        <div className="mt-3">
          <ContributionBar c={c} labels={labels} />
        </div>

        <div className="mt-3 flex flex-wrap gap-1.5">
          {c.explanation.adds.map((s) => (
            <Badge key={s.skill} tone="brand" title={`Coverage ${Math.round(s.coverage_before * 100)}% → ${Math.round(s.coverage_after * 100)}%`}>
              + {s.skill} {s.candidate_proficiency}/4
            </Badge>
          ))}
          {c.explanation.duplicates.map((s) => (
            <Badge key={s.skill} tone="muted" title="Already covered by the team">
              {s.skill} {s.candidate_proficiency}/4
            </Badge>
          ))}
          {c.explanation.unverified_rules.length > 0 && <Badge tone="warn">unverified rule</Badge>}
        </div>

        <p className="mt-3 text-sm text-ink-soft">{c.explanation_text}</p>
      </div>

      <div className="mt-3 flex flex-wrap items-center justify-between gap-2 border-t border-line pt-3">
        <div className="flex items-center gap-3">
          <button className="text-sm text-brand-700 underline" aria-expanded={open} aria-controls={panelId} onClick={() => setOpen(!open)}>
            {open ? "Hide details" : "Why this rank?"}
          </button>
          <label className="flex items-center gap-1.5 text-sm text-ink-soft">
            <input type="checkbox" checked={selected} onChange={(e) => onSelect(e.target.checked)} /> Compare
          </label>
        </div>
        {c.invitation_status === "pending" ? (
          <Badge tone="brand">Invitation pending</Badge>
        ) : canInvite ? (
          <div className="flex items-center gap-2">
            {vacantRoles.length > 0 && (
              <select className="input w-auto py-1.5" aria-label={`Role to offer ${p.display_name}`} value={role} onChange={(e) => setRole(e.target.value)}>
                <option value="">No specific role</option>
                {vacantRoles.map((r) => <option key={r}>{r}</option>)}
              </select>
            )}
            <Button
              size="sm"
              busy={busy}
              onClick={async () => {
                setBusy(true);
                try {
                  await onInvite(role || null);
                } finally {
                  setBusy(false);
                }
              }}
            >
              Invite
            </Button>
          </div>
        ) : null}
      </div>

      {open && (
        <div id={panelId} className="mt-4 border-t border-line pt-4">
          <ExplanationPanel c={c} labels={labels} />
        </div>
      )}
    </Card>
  );
}
