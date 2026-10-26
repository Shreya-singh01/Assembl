import type { FeatureKey, RankedCandidate } from "../../api/types";
import { Badge, pct } from "../../components/ui/Display";
import { FEATURE_COLORS, FEATURE_ORDER } from "./compare";

export function ContributionBar({ c, labels }: { c: RankedCandidate; labels: Record<FeatureKey, string> }) {
  const parts = FEATURE_ORDER.filter((f) => c.explanation.contributions[f]);
  return (
    <div>
      <div className="flex h-2.5 w-full overflow-hidden rounded-full bg-paper-sunk" aria-hidden>
        {parts.map((f) => (
          <div key={f} style={{ width: `${c.explanation.contributions[f]!.contribution * 100}%`, background: FEATURE_COLORS[f] }} title={labels[f]} />
        ))}
      </div>
      <ul className="sr-only">
        {parts.map((f) => (
          <li key={f}>
            {labels[f]} contributes {c.explanation.contributions[f]!.contribution.toFixed(3)}
          </li>
        ))}
      </ul>
    </div>
  );
}

function statusNote(status: string) {
  if (status === "neutral_unknown") return <Badge tone="warn">neutral — not stated</Badge>;
  return null;
}

export function ExplanationPanel({ c, labels }: { c: RankedCandidate; labels: Record<FeatureKey, string> }) {
  const e = c.explanation;
  return (
    <div className="space-y-5 text-sm">
      <div className="overflow-x-auto">
        <table className="w-full text-left">
          <caption className="mb-2 text-left text-xs text-ink-soft">How the ranking score is built: value × weight = contribution.</caption>
          <thead className="text-xs text-ink-soft">
            <tr className="border-b border-line">
              <th className="py-1.5 pr-3 font-medium">Signal</th>
              <th className="py-1.5 pr-3 font-medium">Value</th>
              <th className="py-1.5 pr-3 font-medium">Weight</th>
              <th className="py-1.5 font-medium">Contribution</th>
            </tr>
          </thead>
          <tbody className="num">
            {FEATURE_ORDER.map((f) => {
              const k = e.contributions[f];
              const fv = c.features[f];
              return (
                <tr key={f} className="border-b border-line">
                  <td className="py-1.5 pr-3">
                    <span className="mr-2 inline-block h-2.5 w-2.5 rounded-sm align-middle" style={{ background: FEATURE_COLORS[f] }} aria-hidden />
                    {labels[f]} {fv && statusNote(fv.status)}
                  </td>
                  {k ? (
                    <>
                      <td className="py-1.5 pr-3">{k.value.toFixed(2)}</td>
                      <td className="py-1.5 pr-3">{k.weight.toFixed(3)}</td>
                      <td className="py-1.5">{k.contribution.toFixed(3)}</td>
                    </>
                  ) : (
                    <td colSpan={3} className="py-1.5 text-ink-faint">
                      not used for this request
                    </td>
                  )}
                </tr>
              );
            })}
            <tr>
              <td className="py-1.5 pr-3 font-medium">Ranking score</td>
              <td />
              <td />
              <td className="py-1.5 font-medium">{c.score.toFixed(3)}</td>
            </tr>
          </tbody>
        </table>
      </div>

      <div className="grid gap-4 sm:grid-cols-3">
        <div>
          <h4 className="mb-1 text-xs font-medium uppercase tracking-wide text-brand-700">Would add</h4>
          {e.adds.length === 0 ? (
            <p className="text-ink-soft">{e.all_requirements_covered_before ? "All requirements already covered." : "No listed requirement."}</p>
          ) : (
            <ul className="space-y-1">
              {e.adds.map((s) => (
                <li key={s.skill}>
                  <span className="font-medium">{s.skill}</span>{" "}
                  <span className="text-ink-soft">
                    ({s.importance_label}) stated {s.candidate_proficiency}/4, desired {s.desired_proficiency}: {pct(s.coverage_before)} → {pct(s.coverage_after)}
                  </span>
                </li>
              ))}
            </ul>
          )}
        </div>
        <div>
          <h4 className="mb-1 text-xs font-medium uppercase tracking-wide text-ink-soft">Already covered by team</h4>
          {e.duplicates.length === 0 ? <p className="text-ink-soft">—</p> : (
            <ul className="space-y-1">
              {e.duplicates.map((s) => (
                <li key={s.skill}>
                  {s.skill} <span className="text-ink-soft">(stated {s.candidate_proficiency}, team best {s.team_best_before})</span>
                </li>
              ))}
            </ul>
          )}
        </div>
        <div>
          <h4 className="mb-1 text-xs font-medium uppercase tracking-wide text-gap">Still open after joining</h4>
          {e.remaining_gaps.length === 0 ? <p className="text-ink-soft">Nothing — every requirement would be met.</p> : (
            <ul className="space-y-1">
              {e.remaining_gaps.map((s) => (
                <li key={s.skill}>
                  {s.skill} <span className="text-ink-soft">({pct(s.coverage_after)})</span>
                </li>
              ))}
            </ul>
          )}
        </div>
      </div>

      <dl className="grid grid-cols-[9rem_1fr] gap-x-3 gap-y-1">
        <dt className="text-ink-soft">Team coverage</dt>
        <dd className="num">
          {pct(e.team_coverage_before)} → {pct(e.team_coverage_after)} (+{pct(e.added_coverage, 1)})
        </dd>
        <dt className="text-ink-soft">Semantic relevance</dt>
        <dd className="num">{e.semantic_relevance.toFixed(2)} <span className="text-xs text-ink-faint">topical similarity only</span></dd>
        {e.availability && (
          <>
            <dt className="text-ink-soft">Shared slots</dt>
            <dd>{e.availability.stated ? `${e.availability.overlap} of the team's ${e.availability.team_slots} (asked for ${e.availability.required})` : "Not stated"}</dd>
          </>
        )}
        {e.work?.hours && (
          <>
            <dt className="text-ink-soft">Weekly hours</dt>
            <dd>{e.work.hours.candidate} h vs team {e.work.hours.team} h</dd>
          </>
        )}
        {e.work?.modes && (
          <>
            <dt className="text-ink-soft">Working mode</dt>
            <dd>{e.work.modes.candidate} vs team {e.work.modes.team}</dd>
          </>
        )}
      </dl>

      {(e.unknowns.length > 0 || e.unverified_rules.length > 0 || e.required_skills_not_stated.length > 0) && (
        <div className="rounded-md bg-amber-50 p-3 text-amber-900">
          <p className="font-medium">Missing information</p>
          <ul className="mt-1 list-disc pl-5">
            {e.unknowns.map((u) => <li key={u}>{u}</li>)}
            {e.required_skills_not_stated.length > 0 && <li>Does not mention: {e.required_skills_not_stated.join(", ")} (not stated ≠ does not have)</li>}
            {e.unverified_rules.map((u) => <li key={u.code}>Unverified mandatory rule: {u.message}</li>)}
          </ul>
        </div>
      )}
      <p className="text-xs text-ink-faint">{e.caveats.join(" ")}</p>
    </div>
  );
}
