import { useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { api, errorMessage } from "../../api/client";
import { Button } from "../../components/ui/Button";
import { Alert, LoadState } from "../../components/ui/Feedback";
import { Card, PageHeader } from "../../components/ui/Display";
import { useAsync } from "../../hooks/useAsync";

interface AnonProfile {
  label: string;
  year: number | null;
  branch: string | null;
  skills: { skill: string; proficiency: number }[];
  primary_roles: string[];
  secondary_roles: string[];
  interests: string[];
  project_summaries: string[];
  availability: string[] | null;
  weekly_hours: number | null;
  work_mode: string | null;
}
interface Packet {
  scenario_id: string;
  project: { title: string; description: string; requirements: { skill: string; importance: string; desired_proficiency: number }[]; vacant_roles: string[]; weekly_hours: number | null; work_mode: string | null; synchronous: boolean };
  team: AnonProfile[];
  candidates: AnonProfile[];
  rating_scale: Record<string, string>;
}

function Anon({ p }: { p: AnonProfile }) {
  return (
    <div className="text-sm">
      <p>{p.skills.map((s) => `${s.skill} ${s.proficiency}/4`).join(", ") || "No skills stated"}</p>
      <p className="text-xs text-ink-soft">
        Roles: {[...p.primary_roles, ...p.secondary_roles.map((r) => `${r} (2nd)`)].join(", ") || "not stated"} · Year {p.year ?? "?"} · {p.weekly_hours ?? "?"} h/wk · {p.work_mode ?? "mode not stated"} ·{" "}
        {p.availability ? `${p.availability.length} weekly slots` : "availability not stated"}
      </p>
      {p.project_summaries.length > 0 && <p className="text-xs text-ink-soft">Projects: {p.project_summaries.join("; ")}</p>}
    </div>
  );
}

export function JudgingPage() {
  const { scenarioId } = useParams();
  const navigate = useNavigate();
  const packet = useAsync(() => api.get<Packet>(`/research/judging/${scenarioId}`), [scenarioId]);
  const [ratings, setRatings] = useState<Record<string, number>>({});
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  if (!packet.data) return <LoadState loading={packet.loading} error={packet.error} />;
  const pk = packet.data;
  const done = pk.candidates.every((c) => ratings[c.label] !== undefined);

  const submit = async () => {
    setBusy(true);
    setError(null);
    try {
      await api.post(`/research/judging/${scenarioId}`, { ratings });
      navigate("/research");
    } catch (e) {
      setError(errorMessage(e));
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="space-y-5">
      <PageHeader title={`Rate candidates: ${pk.project.title}`} subtitle="Judge how suitable each candidate would be as the next member of this team. Candidates are anonymised and shown in random order; you do not see any method or score." />
      <Card className="p-5 text-sm">
        <p>{pk.project.description}</p>
        <p className="mt-2 text-ink-soft">Requires: {pk.project.requirements.map((r) => `${r.skill} (${r.importance}, level ${r.desired_proficiency})`).join(", ")}</p>
        <p className="text-ink-soft">Vacant roles: {pk.project.vacant_roles.join(", ") || "none"} · {pk.project.synchronous ? "meets synchronously" : "asynchronous"}</p>
        <h3 className="mt-4 font-medium">Current team</h3>
        <ul className="mt-1 space-y-2">{pk.team.map((m) => <li key={m.label}><span className="font-medium">{m.label}: </span><Anon p={m} /></li>)}</ul>
      </Card>
      <ol className="space-y-3">
        {pk.candidates.map((c) => (
          <li key={c.label}>
            <Card className="p-4">
              <fieldset>
                <legend className="font-medium">{c.label}</legend>
                <Anon p={c} />
                <div className="mt-3 flex flex-wrap gap-2">
                  {Object.entries(pk.rating_scale).map(([v, label]) => (
                    <label key={v} className={`cursor-pointer rounded-md border px-3 py-1.5 text-sm ${ratings[c.label] === Number(v) ? "border-brand-600 bg-brand-50" : "border-line"}`}>
                      <input type="radio" className="sr-only" name={c.label} value={v} checked={ratings[c.label] === Number(v)} onChange={() => setRatings({ ...ratings, [c.label]: Number(v) })} />
                      {v} · {label}
                    </label>
                  ))}
                </div>
              </fieldset>
            </Card>
          </li>
        ))}
      </ol>
      {error && <Alert tone="error">{error}</Alert>}
      <div className="flex justify-end">
        <Button onClick={submit} busy={busy} disabled={!done}>Submit {Object.keys(ratings).length}/{pk.candidates.length} ratings</Button>
      </div>
    </div>
  );
}
