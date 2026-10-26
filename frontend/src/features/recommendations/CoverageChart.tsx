import type { TeamCoverage } from "../../api/types";
import { Badge, Meter, pct } from "../../components/ui/Display";

/** Per-requirement coverage of the current team (paper Eq. 2) and the
 *  importance-weighted overall value (Eq. 3). Values come straight from the API. */
export function CoverageChart({ coverage, highlight }: { coverage: TeamCoverage; highlight?: Record<string, number> }) {
  return (
    <div>
      <div className="mb-4 flex items-baseline justify-between">
        <span className="text-sm text-ink-soft">Importance-weighted coverage</span>
        <span className="num text-2xl font-semibold">{pct(coverage.overall)}</span>
      </div>
      <ul className="space-y-3">
        {coverage.per_skill.map((s) => {
          const after = highlight?.[s.skill];
          return (
            <li key={s.skill}>
              <div className="mb-1 flex flex-wrap items-center justify-between gap-2 text-sm">
                <span className="flex items-center gap-1.5">
                  <span className="font-medium">{s.skill}</span>
                  <Badge tone={s.importance === 3 ? "gap" : "muted"}>{s.importance_label}</Badge>
                  {s.mandatory && <Badge tone="warn">mandatory</Badge>}
                </span>
                <span className="num text-xs text-ink-soft">
                  best {s.best_proficiency || "—"} / desired {s.desired_proficiency} · {pct(s.coverage)}
                  {after !== undefined && after > s.coverage && <span className="ml-1 font-medium text-brand-700">→ {pct(after)}</span>}
                </span>
              </div>
              <div className="relative">
                <Meter value={after !== undefined ? Math.max(after, s.coverage) : s.coverage} label={`${s.skill} coverage`} tone={s.coverage >= 1 || (after ?? 0) >= 1 ? "brand" : "gap"} />
                {after !== undefined && after > s.coverage && (
                  <div className="pointer-events-none absolute inset-y-0 left-0 rounded-l-full bg-ink/25" style={{ width: `${s.coverage * 100}%` }} aria-hidden />
                )}
              </div>
            </li>
          );
        })}
      </ul>
      <p className="mt-3 text-xs text-ink-faint">Each requirement counts the strongest member's self-reported level. Workload and the need for several specialists are not modelled.</p>
    </div>
  );
}
