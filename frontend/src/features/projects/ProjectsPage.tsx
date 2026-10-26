import { useState, type FormEvent } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { api } from "../../api/client";
import type { Page, Project, Vocabulary } from "../../api/types";
import { Button, ButtonLink } from "../../components/ui/Button";
import { EmptyState, LoadState } from "../../components/ui/Feedback";
import { Badge, Card, PageHeader } from "../../components/ui/Display";
import { useAsync } from "../../hooks/useAsync";
import { IMPORTANCE_LABELS, OPPORTUNITY_LABELS } from "./labels";

const PAGE = 12;

export function ProjectCard({ p }: { p: Project }) {
  return (
    <Card as="article" className="flex flex-col p-5">
      <div className="flex items-start justify-between gap-3">
        <h2 className="font-semibold leading-snug">
          <Link to={`/projects/${p.id}`} className="hover:underline">
            {p.title}
          </Link>
        </h2>
        <Badge tone="muted">{OPPORTUNITY_LABELS[p.opportunity_type]}</Badge>
      </div>
      <p className="mt-2 line-clamp-3 text-sm text-ink-soft">{p.description}</p>
      <div className="mt-3 flex flex-wrap gap-1.5">
        {p.requirements.slice(0, 6).map((r) => (
          <Badge key={r.skill} tone={r.importance === 3 ? "gap" : "neutral"} title={`${IMPORTANCE_LABELS[r.importance]} · desired level ${r.desired_proficiency}`}>
            {r.skill}
          </Badge>
        ))}
      </div>
      <p className="mt-auto pt-4 text-xs text-ink-soft">
        {p.members.length}/{p.target_size} members · {p.status === "open" ? `${p.open_positions} open` : "closed"}
        {p.vacant_roles.length > 0 && ` · looking for ${p.vacant_roles.join(", ")}`}
      </p>
    </Card>
  );
}

export function ProjectsPage() {
  const [params, setParams] = useSearchParams();
  const q = params.get("q") ?? "";
  const type = params.get("type") ?? "";
  const skill = params.get("skill") ?? "";
  const offset = Number(params.get("offset") ?? 0);
  const [form, setForm] = useState({ q, type, skill });
  const vocab = useAsync(() => api.get<Vocabulary>("/profiles/vocabulary"), []);
  const { data, error, loading, reload } = useAsync(
    () => api.get<Page<Project>>("/projects", { q, opportunity_type: type, skill, limit: PAGE, offset }),
    [q, type, skill, offset],
  );

  const apply = (e: FormEvent) => {
    e.preventDefault();
    const next = new URLSearchParams();
    if (form.q) next.set("q", form.q);
    if (form.type) next.set("type", form.type);
    if (form.skill) next.set("skill", form.skill);
    setParams(next);
  };
  const go = (o: number) => {
    const next = new URLSearchParams(params);
    next.set("offset", String(o));
    setParams(next);
  };

  return (
    <div>
      <PageHeader title="Discover projects" subtitle="Open teams looking for members. Ask to join a team, or start your own and get ranked suggestions." actions={<ButtonLink to="/projects/new">Start a team</ButtonLink>} />
      <form onSubmit={apply} className="mb-6 grid gap-3 sm:grid-cols-[1fr_12rem_12rem_auto]" role="search">
        <label className="sr-only" htmlFor="q">Search</label>
        <input id="q" className="input" placeholder="Search titles and descriptions" value={form.q} onChange={(e) => setForm({ ...form, q: e.target.value })} />
        <label className="sr-only" htmlFor="type">Type</label>
        <select id="type" className="input" value={form.type} onChange={(e) => setForm({ ...form, type: e.target.value })}>
          <option value="">All types</option>
          {Object.entries(OPPORTUNITY_LABELS).map(([k, v]) => (
            <option key={k} value={k}>
              {v}
            </option>
          ))}
        </select>
        <label className="sr-only" htmlFor="skill">Skill</label>
        <input id="skill" className="input" list="skill-list" placeholder="Needs skill…" value={form.skill} onChange={(e) => setForm({ ...form, skill: e.target.value })} />
        <datalist id="skill-list">{vocab.data?.skills.map((s) => <option key={s} value={s} />)}</datalist>
        <Button type="submit" variant="secondary">
          Filter
        </Button>
      </form>
      <LoadState loading={loading} error={error} onRetry={reload} />
      {data && data.items.length === 0 && (
        <EmptyState title={q || type || skill ? "No projects match these filters" : "No open projects yet"} action={<ButtonLink to="/projects/new">Start the first one</ButtonLink>}>
          {q || type || skill ? "Try removing a filter." : "Projects appear here as soon as students create them."}
        </EmptyState>
      )}
      {data && data.items.length > 0 && (
        <>
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
            {data.items.map((p) => (
              <ProjectCard key={p.id} p={p} />
            ))}
          </div>
          <nav className="mt-6 flex items-center justify-between text-sm" aria-label="Pagination">
            <span className="text-ink-soft">
              {offset + 1}–{Math.min(offset + PAGE, data.total)} of {data.total}
            </span>
            <span className="flex gap-2">
              <Button variant="secondary" size="sm" disabled={offset === 0} onClick={() => go(Math.max(0, offset - PAGE))}>
                Previous
              </Button>
              <Button variant="secondary" size="sm" disabled={offset + PAGE >= data.total} onClick={() => go(offset + PAGE)}>
                Next
              </Button>
            </span>
          </nav>
        </>
      )}
    </div>
  );
}
