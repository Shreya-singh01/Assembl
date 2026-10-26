import { useCallback, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { api, errorMessage } from "../../api/client";
import type { FeatureKey, Project, RankedCandidate, Recommendations } from "../../api/types";
import { useSocketEvent } from "../../app/SocketContext";
import { Button, ButtonLink } from "../../components/ui/Button";
import { Alert, EmptyState, LoadState } from "../../components/ui/Feedback";
import { Card, Dialog, PageHeader, pct } from "../../components/ui/Display";
import { useAsync } from "../../hooks/useAsync";
import { OMIT_LABELS, REASON_LABELS } from "../projects/labels";
import { CandidateCard } from "./CandidateCard";
import { compareCandidates, coverageAfter, FEATURE_COLORS, FEATURE_ORDER } from "./compare";
import { CoverageChart } from "./CoverageChart";

const PAGE = 20;

function WeightsPanel({ r }: { r: Recommendations }) {
  return (
    <div className="text-sm">
      <ul className="space-y-1.5">
        {FEATURE_ORDER.map((f) => {
          const w = r.active_weights[f];
          return (
            <li key={f} className="flex items-center justify-between gap-2">
              <span className="flex items-center gap-2">
                <span className="inline-block h-2.5 w-2.5 rounded-sm" style={{ background: FEATURE_COLORS[f] }} aria-hidden />
                {r.feature_labels[f]}
              </span>
              <span className="num text-ink-soft">{w !== undefined ? w.toFixed(3) : "not used"}</span>
            </li>
          );
        })}
      </ul>
      {r.weights_renormalized && (
        <p className="mt-3 text-xs text-ink-soft">
          Not used for this request:{" "}
          {Object.entries(r.omitted_features)
            .map(([f, why]) => `${r.feature_labels[f as FeatureKey]} (${OMIT_LABELS[why as string] ?? why})`)
            .join("; ")}
          . Their weight was shared proportionally among the others.
        </p>
      )}
      <p className="mt-2 text-xs text-ink-faint">Initial design weights from the paper; not yet calibrated on student judgments.</p>
    </div>
  );
}

export function RecommendationsPage() {
  const { projectId } = useParams();
  const [offset, setOffset] = useState(0);
  const project = useAsync(() => api.get<Project>(`/projects/${projectId}`), [projectId]);
  const recs = useAsync(() => api.get<Recommendations>(`/projects/${projectId}/recommendations`, { limit: PAGE, offset }), [projectId, offset]);
  const [hover, setHover] = useState<RankedCandidate | null>(null);
  const [selected, setSelected] = useState<RankedCandidate[]>([]);
  const [compareOpen, setCompareOpen] = useState(false);
  const [notice, setNotice] = useState<{ tone: "success" | "error"; text: string } | null>(null);

  const { reload } = recs;
  useSocketEvent<{ project_id: string }>("team:update", useCallback((e) => e.project_id === projectId && reload(), [projectId, reload]));

  if (project.error) return <Alert tone="error">{project.error}</Alert>;
  const r = recs.data;
  const p = project.data;

  const invite = async (c: RankedCandidate, role: string | null) => {
    setNotice(null);
    try {
      await api.post(`/projects/${projectId}/invitations`, { candidate_id: c.profile.user_id, role, message: "" });
      setNotice({ tone: "success", text: `Invitation sent to ${c.profile.display_name}. The ranking updates when someone joins.` });
      reload();
    } catch (e) {
      setNotice({ tone: "error", text: errorMessage(e) });
    }
  };

  const toggleSelect = (c: RankedCandidate, v: boolean) =>
    setSelected((cur) => (v ? [...cur.filter((x) => x.profile.user_id !== c.profile.user_id), c].slice(-2) : cur.filter((x) => x.profile.user_id !== c.profile.user_id)));

  return (
    <div>
      <PageHeader
        title={p ? `Find members for ${p.title}` : "Find members"}
        subtitle="Candidates are ranked for your team as it stands now. When someone joins or leaves, coverage is recomputed and the list refreshes."
        actions={
          <>
            {selected.length === 2 && <Button variant="secondary" onClick={() => setCompareOpen(true)}>Compare selected</Button>}
            <ButtonLink to={`/projects/${projectId}`} variant="secondary">Back to project</ButtonLink>
          </>
        }
      />
      {notice && <div className="mb-4"><Alert tone={notice.tone}>{notice.text}</Alert></div>}
      <LoadState loading={recs.loading && !r} error={recs.error} onRetry={reload} />
      {r && (
        <div className="grid gap-6 lg:grid-cols-[1fr_20rem]">
          <div className="order-2 space-y-4 lg:order-1">
            {r.warnings.map((w) => <Alert key={w} tone="warning">{w}</Alert>)}
            {r.status === "team_full" && (
              <EmptyState title="Your team is complete">The team has reached its target size, so no further recommendations are produced. Raise the target size to keep recruiting.</EmptyState>
            )}
            {r.status === "closed" && <EmptyState title="This project is closed">Reopen it from the edit page to see recommendations.</EmptyState>}
            {r.status === "no_eligible_candidates" && (
              <EmptyState title="No eligible candidates right now" action={<ButtonLink to={`/projects/${projectId}/edit`} variant="secondary">Review rules</ButtonLink>}>
                {r.pool.considered === 0
                  ? "No other student has a visible profile yet."
                  : `${r.pool.excluded} visible student${r.pool.excluded === 1 ? "" : "s"} did not meet your mandatory conditions.`}
              </EmptyState>
            )}
            {r.candidates.map((c) => (
              <CandidateCard
                key={c.profile.user_id}
                c={c}
                labels={r.feature_labels}
                vacantRoles={p?.vacant_roles ?? []}
                canInvite={r.status === "ok"}
                selected={selected.some((s) => s.profile.user_id === c.profile.user_id)}
                onSelect={(v) => toggleSelect(c, v)}
                onInvite={(role) => invite(c, role)}
                onHover={setHover}
              />
            ))}
            {r.total > PAGE && (
              <nav className="flex items-center justify-between text-sm" aria-label="Pagination">
                <span className="text-ink-soft">{offset + 1}–{Math.min(offset + PAGE, r.total)} of {r.total}</span>
                <span className="flex gap-2">
                  <Button size="sm" variant="secondary" disabled={offset === 0} onClick={() => setOffset(Math.max(0, offset - PAGE))}>Previous</Button>
                  <Button size="sm" variant="secondary" disabled={offset + PAGE >= r.total} onClick={() => setOffset(offset + PAGE)}>Next</Button>
                </span>
              </nav>
            )}
          </div>
          <aside className="order-1 space-y-4 lg:order-2" aria-label="Team context">
            <Card className="p-4">
              <h2 className="mb-1 font-semibold">Team coverage</h2>
              <p className="mb-3 text-xs text-ink-soft">{hover ? `Showing what ${hover.profile.display_name} would add.` : "Hover a candidate to preview what they would add."}</p>
              <CoverageChart coverage={r.team_coverage} highlight={hover ? coverageAfter(hover) : undefined} />
            </Card>
            <Card className="p-4">
              <h2 className="mb-3 font-semibold">How this list is scored</h2>
              <WeightsPanel r={r} />
            </Card>
            <Card className="p-4 text-sm">
              <h2 className="mb-2 font-semibold">Candidate pool</h2>
              <p className="num">
                {r.pool.considered} visible · {r.pool.eligible} eligible · {r.pool.excluded} excluded by mandatory conditions
              </p>
              {Object.keys(r.pool.excluded_by_reason).length > 0 && (
                <ul className="mt-2 space-y-0.5 text-xs text-ink-soft">
                  {Object.entries(r.pool.excluded_by_reason).map(([code, n]) => (
                    <li key={code} className="flex justify-between"><span>{REASON_LABELS[code] ?? code}</span><span className="num">{n}</span></li>
                  ))}
                </ul>
              )}
              <p className="mt-3 text-xs text-ink-faint">Encoder: {r.encoder}. {r.notice}</p>
              <Link to="/how-it-works" className="mt-2 inline-block text-xs text-brand-700 underline">How ranking works</Link>
            </Card>
          </aside>
        </div>
      )}
      {selected.length === 2 && r && (
        <Dialog open={compareOpen} onClose={() => setCompareOpen(false)} title="Why one candidate ranks above the other" wide>
          <CompareView a={selected[0]} b={selected[1]} labels={r.feature_labels} />
        </Dialog>
      )}
    </div>
  );
}

function CompareView({ a, b, labels }: { a: RankedCandidate; b: RankedCandidate; labels: Record<FeatureKey, string> }) {
  const [hi, lo] = a.score >= b.score ? [a, b] : [b, a];
  const { total, diffs } = compareCandidates(hi, lo);
  const main = diffs.find((d) => d.diff > 0);
  return (
    <div className="space-y-4 text-sm">
      <p>
        <strong>{hi.profile.display_name}</strong> (#{hi.rank}) scores <span className="num">{total.toFixed(3)}</span> higher than <strong>{lo.profile.display_name}</strong> (#{lo.rank})
        {main ? <>, mostly because of <strong>{labels[main.feature].toLowerCase()}</strong>.</> : "."}
      </p>
      <div className="overflow-x-auto">
        <table className="w-full text-left">
          <thead className="text-xs text-ink-soft">
            <tr className="border-b border-line">
              <th className="py-1.5 pr-3 font-medium">Signal</th>
              <th className="py-1.5 pr-3 font-medium">{hi.profile.display_name}</th>
              <th className="py-1.5 pr-3 font-medium">{lo.profile.display_name}</th>
              <th className="py-1.5 font-medium">Difference</th>
            </tr>
          </thead>
          <tbody className="num">
            {diffs.map((d) => (
              <tr key={d.feature} className="border-b border-line">
                <td className="py-1.5 pr-3">{labels[d.feature]}</td>
                <td className="py-1.5 pr-3">{d.a.toFixed(3)}</td>
                <td className="py-1.5 pr-3">{d.b.toFixed(3)}</td>
                <td className={`py-1.5 ${d.diff > 0 ? "text-brand-700" : d.diff < 0 ? "text-gap" : "text-ink-faint"}`}>{d.diff > 0 ? "+" : ""}{d.diff.toFixed(3)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <div className="grid gap-4 sm:grid-cols-2">
        {[hi, lo].map((c) => (
          <div key={c.profile.user_id} className="rounded-md bg-paper-sunk p-3">
            <p className="font-medium">{c.profile.display_name}</p>
            <p className="mt-1 text-ink-soft">{c.explanation_text}</p>
            <p className="num mt-2 text-xs">Adds {pct(c.added_coverage, 1)} coverage</p>
          </div>
        ))}
      </div>
    </div>
  );
}
