import { useEffect, useState, type FormEvent, type ReactNode } from "react";
import { useSearchParams, useNavigate } from "react-router-dom";
import { api, errorMessage } from "../../api/client";
import type { Profile, ProjectSummary, Skill, Vocabulary, WorkMode } from "../../api/types";
import { useAuth } from "../../app/AuthContext";
import { Button } from "../../components/ui/Button";
import { Alert, LoadState } from "../../components/ui/Feedback";
import { Field, TagInput, Toggle } from "../../components/ui/Form";
import { Card, Meter, PageHeader } from "../../components/ui/Display";
import { useAsync } from "../../hooks/useAsync";
import { AvailabilityGrid } from "./AvailabilityGrid";
import { SkillEditor } from "./SkillEditor";

type Draft = Omit<Profile, "user_id" | "completion" | "updated_at" | "normalization">;

function Section({ title, why, children }: { title: string; why: string; children: ReactNode }) {
  return (
    <Card className="p-5">
      <h2 className="font-semibold">{title}</h2>
      <p className="mb-4 mt-0.5 text-xs text-ink-soft">{why}</p>
      <div className="space-y-4">{children}</div>
    </Card>
  );
}

export function ProfilePage() {
  const [params] = useSearchParams();
  const onboarding = params.get("onboarding") === "1";
  const navigate = useNavigate();
  const { refresh } = useAuth();
  const profile = useAsync(() => api.get<Profile>("/profiles/me"), []);
  const vocab = useAsync(() => api.get<Vocabulary>("/profiles/vocabulary"), []);
  const [draft, setDraft] = useState<Draft | null>(null);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [saved, setSaved] = useState<Profile | null>(null);

  useEffect(() => {
    if (profile.data && !draft) {
      const { user_id: _u, completion: _c, updated_at: _t, normalization: _n, ...rest } = profile.data;
      setDraft(rest);
    }
  }, [profile.data, draft]);

  if (!draft || !vocab.data) return <LoadState loading={profile.loading || vocab.loading} error={profile.error ?? vocab.error} onRetry={profile.reload} />;

  const set = <K extends keyof Draft>(k: K, v: Draft[K]) => setDraft({ ...draft, [k]: v });

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    setSaving(true);
    setError(null);
    try {
      const body = {
        ...draft,
        skills: draft.skills.filter((s) => s.label.trim()).map(({ label, proficiency, kind }: Skill) => ({ label, proficiency, kind })),
        projects: draft.projects.filter((p) => p.title.trim()).map((p) => ({ ...p, link: p.link || null })),
        branch: draft.branch || null,
      };
      const res = await api.put<Profile>("/profiles/me", body);
      setSaved(res);
      const { user_id: _u, completion: _c, updated_at: _t, normalization: _n, ...rest } = res;
      setDraft(rest);
      await refresh();
      if (onboarding && res.completion.ready_for_matching) navigate("/dashboard");
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setSaving(false);
    }
  };

  const completion = (saved ?? profile.data)!.completion;

  return (
    <form onSubmit={submit} className="space-y-6" noValidate>
      <PageHeader
        title={onboarding ? "Set up your profile" : "Your profile"}
        subtitle="Teams are matched with you through this information. Everything here is self-reported and shown to teams as such. Add what you are comfortable sharing — blank fields are marked “not stated”, never guessed."
      />
      <div className="flex items-center gap-3">
        <Meter value={completion.percent / 100} label="Profile completion" />
        <span className="num w-12 text-sm">{completion.percent}%</span>
      </div>

      <Section title="Skills" why="The core of matching: teams compare your stated skills and levels with the requirements their current members do not cover yet.">
        <SkillEditor value={draft.skills} onChange={(v) => set("skills", v)} vocabulary={vocab.data.skills} />
        <TagInput
          label="Skills I explicitly do not have (optional)"
          value={draft.declared_absent}
          onChange={(v) => set("declared_absent", v)}
          suggestions={vocab.data.skills}
          placeholder="e.g. iOS Development"
          max={40}
        />
      </Section>

      <Section title="Roles and interests" why="Teams list vacant roles; your preferred roles decide role fit. Interests and project summaries feed the semantic-relevance signal.">
        <TagInput label="Primary roles" value={draft.primary_roles} onChange={(v) => set("primary_roles", v)} suggestions={vocab.data.roles} max={3} placeholder="e.g. Backend" />
        <TagInput label="Secondary roles" value={draft.secondary_roles} onChange={(v) => set("secondary_roles", v)} suggestions={vocab.data.roles} max={5} placeholder="e.g. Presenter" />
        <TagInput label="Domain interests" value={draft.interests} onChange={(v) => set("interests", v)} max={15} placeholder="e.g. fintech, accessibility" />
        <ProjectsEditor value={draft.projects} onChange={(v) => set("projects", v)} />
      </Section>

      <Section title="About you" why="Some teams can only accept certain years of study (for example, competition rules).">
        <div className="grid gap-4 sm:grid-cols-2">
          <Field label="Year of study">
            {(id) => (
              <select id={id} className="input" value={draft.year ?? ""} onChange={(e) => set("year", e.target.value ? Number(e.target.value) : null)}>
                <option value="">Not stated</option>
                {[1, 2, 3, 4, 5, 6].map((y) => (
                  <option key={y} value={y}>
                    Year {y}
                  </option>
                ))}
              </select>
            )}
          </Field>
          <Field label="Branch / department">
            {(id) => <input id={id} className="input" maxLength={60} value={draft.branch ?? ""} onChange={(e) => set("branch", e.target.value)} placeholder="e.g. AI-DS" />}
          </Field>
        </div>
      </Section>

      <Section title="Working together" why="Shared weekly slots, similar expected hours and compatible working modes decide whether a team can actually meet.">
        <AvailabilityGrid value={draft.availability} onChange={(v) => set("availability", v)} />
        <div className="grid gap-4 sm:grid-cols-2">
          <Field label="Expected hours per week" hint="1–40">
            {(id) => (
              <input
                id={id}
                className="input"
                type="number"
                min={1}
                max={40}
                value={draft.weekly_hours ?? ""}
                onChange={(e) => set("weekly_hours", e.target.value ? Math.max(1, Math.min(40, Number(e.target.value))) : null)}
                placeholder="Not stated"
              />
            )}
          </Field>
          <Field label="Preferred working mode">
            {(id) => (
              <select id={id} className="input" value={draft.work_mode ?? ""} onChange={(e) => set("work_mode", (e.target.value || null) as WorkMode | null)}>
                <option value="">Not stated</option>
                <option value="online">Online</option>
                <option value="offline">In person</option>
                <option value="hybrid">Hybrid (either)</option>
              </select>
            )}
          </Field>
        </div>
      </Section>

      <Section title="Visibility" why="Your choice. While hidden you can still create teams, join by invitation and message people you work with.">
        <Toggle
          checked={draft.visible}
          onChange={(v) => set("visible", v)}
          label="Show my profile to teams looking for members"
          description="Teams see your skills, roles, interests, projects, hours and mode — never your e-mail or your exact weekly slots."
        />
      </Section>

      {error && <Alert tone="error">{error}</Alert>}
      {saved && (
        <Alert tone="success" title="Profile saved">
          {saved.normalization.length > 0 && (
            <span>
              Recognised:{" "}
              {saved.normalization
                .filter((n) => n.rule !== "unrecognized")
                .map((n) => `“${n.original}” → ${n.canonical}`)
                .join(", ") || "—"}
              {saved.normalization.some((n) => n.rule === "unrecognized") &&
                `. Kept as written: ${saved.normalization.filter((n) => n.rule === "unrecognized").map((n) => n.original).join(", ")}`}
            </span>
          )}
        </Alert>
      )}
      <div className="sticky bottom-0 -mx-4 flex justify-end gap-2 border-t border-line bg-paper/95 px-4 py-3 backdrop-blur">
        <Button type="submit" busy={saving}>
          {onboarding ? "Save and continue" : "Save profile"}
        </Button>
      </div>
    </form>
  );
}

function ProjectsEditor({ value, onChange }: { value: ProjectSummary[]; onChange: (v: ProjectSummary[]) => void }) {
  const update = (i: number, patch: Partial<ProjectSummary>) => onChange(value.map((p, j) => (j === i ? { ...p, ...patch } : p)));
  return (
    <div>
      <p className="label">Previous projects</p>
      <ul className="space-y-3">
        {value.map((p, i) => (
          <li key={i} className="space-y-2 rounded-md border border-line p-3">
            <div className="flex gap-2">
              <input className="input" aria-label={`Project ${i + 1} title`} placeholder="Title" maxLength={120} value={p.title} onChange={(e) => update(i, { title: e.target.value })} />
              <button type="button" className="rounded px-2 text-ink-faint hover:text-ink" aria-label={`Remove project ${i + 1}`} onClick={() => onChange(value.filter((_, j) => j !== i))}>
                ✕
              </button>
            </div>
            <textarea className="input" rows={2} aria-label={`Project ${i + 1} summary`} placeholder="What it was" maxLength={600} value={p.summary} onChange={(e) => update(i, { summary: e.target.value })} />
            <input className="input" aria-label={`Project ${i + 1} contribution`} placeholder="Your own contribution" maxLength={400} value={p.contribution} onChange={(e) => update(i, { contribution: e.target.value })} />
            <input className="input" type="url" aria-label={`Project ${i + 1} link`} placeholder="Repository or demo link (optional, not scored)" value={p.link ?? ""} onChange={(e) => update(i, { link: e.target.value })} />
          </li>
        ))}
      </ul>
      <Button variant="secondary" size="sm" className="mt-2" disabled={value.length >= 8} onClick={() => onChange([...value, { title: "", summary: "", contribution: "", link: null }])}>
        + Add project
      </Button>
    </div>
  );
}
