import { useState } from "react";
import { Link } from "react-router-dom";
import { api, errorMessage } from "../../api/client";
import { useAuth } from "../../app/AuthContext";
import { Button } from "../../components/ui/Button";
import { Alert, EmptyState, LoadState } from "../../components/ui/Feedback";
import { Badge, Card, Dialog, PageHeader, timeAgo } from "../../components/ui/Display";
import { useAsync } from "../../hooks/useAsync";

interface Metric {
  value: number | null;
  n: number;
  status: "measured" | "not measured";
}
interface MethodRow {
  "ndcg@5": Metric;
  "precision@5": Metric;
  "added_coverage@5": Metric;
  "constraint_violations@5": Metric;
  mandatory_violations: number;
}
interface RunSummary {
  id: string;
  state: "running" | "complete" | "failed";
  run_id?: string;
  status?: string;
  is_research_evidence?: boolean;
  warnings?: string[];
  created_at: string;
  dataset?: { scenarios: number; provenance: Record<string, number>; judgment_provenance: Record<string, number> };
  error?: string;
}
interface RunDetail extends RunSummary {
  report?: {
    results: Record<string, MethodRow>;
    ablations: Record<string, MethodRow>;
    method_names: Record<string, string>;
    timing: { median_ms_warm_cache: number | null; median_ms_cold_cache: number | null; hardware: string };
    reliability: { overall: { alpha: number | null; pairable_units: number } };
    comparisons: Record<string, { n: number; mean_difference?: number | null; p_value?: number | null; rank_biserial?: number | null; note?: string | null }>;
  };
}
interface Status {
  methods_implemented: Record<string, string>;
  scenarios: { total: number; real: number; synthetic: number; with_judging_packets: number; with_human_judgments: number; real_with_human_judgments: number; with_simulated_judgments: number };
  target_scenarios: number;
  human_judgments: number;
  runs_completed: number;
  evaluation_status: "pending" | "measured";
  open_tasks: string[];
}
interface Task {
  scenario_id: string;
  provenance: string;
  title: string;
  candidates: number;
  completed: boolean;
}

const cell = (m: Metric, pctMode = false) =>
  m.value === null ? <span className="text-ink-faint">not measured</span> : <span className="num">{pctMode ? `${(m.value * 100).toFixed(1)}%` : m.value.toFixed(3)}</span>;

export function MetricsTable({ rows, names }: { rows: Record<string, MethodRow>; names?: Record<string, string> }) {
  return (
    <div className="overflow-x-auto">
      <table className="w-full min-w-[40rem] text-left text-sm">
        <thead className="text-xs text-ink-soft">
          <tr className="border-b border-line">
            <th className="py-2 pr-3 font-medium">Method</th>
            <th className="py-2 pr-3 font-medium">NDCG@5</th>
            <th className="py-2 pr-3 font-medium">Precision@5</th>
            <th className="py-2 pr-3 font-medium">Added coverage@5</th>
            <th className="py-2 pr-3 font-medium">Soft violations</th>
            <th className="py-2 font-medium">n</th>
          </tr>
        </thead>
        <tbody>
          {Object.entries(rows).map(([k, m]) => (
            <tr key={k} className="border-b border-line">
              <td className="py-2 pr-3">{k} {names?.[k] && <span className="text-ink-soft">· {names[k]}</span>}</td>
              <td className="py-2 pr-3">{cell(m["ndcg@5"])}</td>
              <td className="py-2 pr-3">{cell(m["precision@5"])}</td>
              <td className="py-2 pr-3">{cell(m["added_coverage@5"])}</td>
              <td className="py-2 pr-3">{cell(m["constraint_violations@5"], true)}</td>
              <td className="num py-2">{m["ndcg@5"].n}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function RunView({ id, onClose }: { id: string; onClose: () => void }) {
  const run = useAsync(() => api.get<RunDetail>(`/research/runs/${id}`), [id]);
  return (
    <Dialog open onClose={onClose} title={`Evaluation run ${run.data?.run_id ?? ""}`} wide>
      <LoadState loading={run.loading} error={run.error} />
      {run.data?.report && (
        <div className="space-y-5">
          {!run.data.is_research_evidence && (
            <Alert tone="warning" title="Pipeline demonstration — not research evidence">
              This run uses synthetic scenarios and/or simulated ratings. It shows the pipeline works; it does not show any method is better.
            </Alert>
          )}
          {run.data.warnings?.map((w) => <p key={w} className="text-xs text-ink-soft">• {w}</p>)}
          <section>
            <h3 className="mb-2 font-semibold">Methods on test scenarios</h3>
            <MetricsTable rows={run.data.report.results} names={run.data.report.method_names} />
          </section>
          <section>
            <h3 className="mb-2 font-semibold">Ablations</h3>
            <MetricsTable rows={run.data.report.ablations} />
          </section>
          <section className="text-sm">
            <h3 className="mb-2 font-semibold">Paired comparisons (NDCG@5, Wilcoxon)</h3>
            <ul className="space-y-1">
              {Object.entries(run.data.report.comparisons).map(([k, c]) => (
                <li key={k} className="num">
                  {k}: n={c.n}
                  {c.mean_difference != null && `, mean diff ${c.mean_difference.toFixed(3)}`}
                  {c.p_value != null && `, p=${c.p_value.toFixed(4)}`}
                  {c.rank_biserial != null && `, r=${c.rank_biserial.toFixed(2)}`}
                  {c.note && <span className="text-ink-soft"> — {c.note}</span>}
                </li>
              ))}
            </ul>
            <p className="mt-3">
              Krippendorff's α (ordinal): {run.data.report.reliability.overall.alpha?.toFixed(3) ?? "undefined"} · median ranking time{" "}
              {run.data.report.timing.median_ms_warm_cache?.toFixed(1)} ms (warm), {run.data.report.timing.median_ms_cold_cache?.toFixed(1)} ms (cold) on {run.data.report.timing.hardware}
            </p>
          </section>
        </div>
      )}
      {run.data?.state === "failed" && <Alert tone="error">Run failed ({run.data.error}).</Alert>}
      {run.data?.state === "running" && <p className="text-sm">Still running…</p>}
    </Dialog>
  );
}

export function ResearchPage() {
  const { user } = useAuth();
  const isAdmin = user?.role === "admin";
  const isRater = user?.role === "rater" || isAdmin;
  const status = useAsync(() => api.get<Status>("/research/status"), []);
  const runs = useAsync(() => api.get<RunSummary[]>("/research/runs"), []);
  const tasks = useAsync(() => (isRater ? api.get<Task[]>("/research/judging/tasks") : Promise.resolve([] as Task[])), [isRater]);
  const [open, setOpen] = useState<string | null>(null);
  const [busy, setBusy] = useState<string | null>(null);
  const [msg, setMsg] = useState<{ tone: "success" | "error"; text: string } | null>(null);

  const act = async (key: string, fn: () => Promise<unknown>, ok: string) => {
    setBusy(key);
    setMsg(null);
    try {
      await fn();
      setMsg({ tone: "success", text: ok });
      status.reload();
      runs.reload();
      tasks.reload();
    } catch (e) {
      setMsg({ tone: "error", text: errorMessage(e) });
    } finally {
      setBusy(null);
    }
  };

  const s = status.data;
  return (
    <div className="space-y-6">
      <PageHeader title="Research evaluation" subtitle="Status of the evaluation protocol described in the Assembl paper. Numbers appear here only after they have actually been measured." />
      <LoadState loading={status.loading} error={status.error} onRetry={status.reload} />
      {s && (
        <>
          <Card className="p-5">
            <div className="flex flex-wrap items-center justify-between gap-3">
              <h2 className="font-semibold">Evaluation status</h2>
              <Badge tone={s.evaluation_status === "measured" ? "brand" : "warn"}>{s.evaluation_status === "measured" ? "Measured on real data" : "Evaluation pending"}</Badge>
            </div>
            <dl className="mt-4 grid gap-4 text-sm sm:grid-cols-4">
              <div><dt className="text-ink-soft">Real scenarios</dt><dd className="num text-xl font-semibold">{s.scenarios.real} / {s.target_scenarios}</dd></div>
              <div><dt className="text-ink-soft">Real, human-judged</dt><dd className="num text-xl font-semibold">{s.scenarios.real_with_human_judgments}</dd></div>
              <div><dt className="text-ink-soft">Human ratings</dt><dd className="num text-xl font-semibold">{s.human_judgments}</dd></div>
              <div><dt className="text-ink-soft">Synthetic scenarios</dt><dd className="num text-xl font-semibold">{s.scenarios.synthetic}</dd></div>
            </dl>
            {s.open_tasks.length > 0 && (
              <div className="mt-4">
                <h3 className="text-sm font-medium">Open tasks</h3>
                <ul className="mt-1 list-disc pl-5 text-sm text-ink-soft">{s.open_tasks.map((t) => <li key={t}>{t}</li>)}</ul>
              </div>
            )}
            <h3 className="mt-4 text-sm font-medium">Methods implemented</h3>
            <p className="text-sm text-ink-soft">{Object.entries(s.methods_implemented).map(([k, v]) => `${k} ${v}`).join(" · ")}</p>
          </Card>

          {msg && <Alert tone={msg.tone}>{msg.text}</Alert>}

          {isAdmin && (
            <Card className="p-5">
              <h2 className="font-semibold">Administration</h2>
              <p className="mt-1 text-sm text-ink-soft">Real scenarios are imported as JSON through the API (POST /api/v1/research/scenarios/import). The synthetic set is for demonstrations and is always labelled.</p>
              <div className="mt-4 flex flex-wrap gap-2">
                <Button variant="secondary" busy={busy === "syn"} onClick={() => act("syn", () => api.post("/research/scenarios/synthetic"), "Synthetic scenarios imported (labelled synthetic).")}>
                  Load synthetic scenarios
                </Button>
                <Button busy={busy === "eval"} onClick={() => act("eval", () => api.post("/research/evaluate", { seed: 13, grid_step: 0.1 }), "Evaluation started. Refresh the run list in a minute.")}>
                  Run evaluation
                </Button>
              </div>
            </Card>
          )}

          {isRater && (
            <Card className="p-5">
              <h2 className="font-semibold">Rating tasks</h2>
              {tasks.data && tasks.data.length === 0 && <p className="mt-2 text-sm text-ink-soft">No rating packets have been prepared yet.</p>}
              <ul className="mt-2 divide-y divide-line">
                {tasks.data?.map((t) => (
                  <li key={t.scenario_id} className="flex items-center justify-between gap-3 py-2 text-sm">
                    <span>
                      {t.title} <span className="text-ink-faint">· {t.candidates} candidates · {t.provenance}</span>
                    </span>
                    {t.completed ? <Badge tone="brand">rated</Badge> : <Link className="text-brand-700 underline" to={`/research/judging/${t.scenario_id}`}>Rate</Link>}
                  </li>
                ))}
              </ul>
            </Card>
          )}

          <Card className="p-5">
            <h2 className="font-semibold">Evaluation runs</h2>
            {runs.data && runs.data.length === 0 ? (
              <EmptyState title="No runs yet">Results tables stay empty until an evaluation has been run.</EmptyState>
            ) : (
              <ul className="mt-2 divide-y divide-line">
                {runs.data?.map((r) => (
                  <li key={r.id} className="flex flex-wrap items-center justify-between gap-3 py-2 text-sm">
                    <span>
                      {r.run_id ?? r.id} <span className="text-ink-faint">· {timeAgo(r.created_at)}</span>{" "}
                      {r.state === "complete" && (r.is_research_evidence ? <Badge tone="brand">measured</Badge> : <Badge tone="warn">demonstration</Badge>)}
                      {r.state !== "complete" && <Badge tone="muted">{r.state}</Badge>}
                    </span>
                    {r.state === "complete" && <Button size="sm" variant="secondary" onClick={() => setOpen(r.id)}>View results</Button>}
                  </li>
                ))}
              </ul>
            )}
          </Card>
        </>
      )}
      {open && <RunView id={open} onClose={() => setOpen(null)} />}
    </div>
  );
}
