import { useEffect, useId, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { api, errorMessage } from "../../api/client";
import type { Project, ProjectInput, Requirement, Vocabulary, WorkMode } from "../../api/types";
import { Button } from "../../components/ui/Button";
import { Alert, LoadState } from "../../components/ui/Feedback";
import { Field, TagInput, Toggle } from "../../components/ui/Form";
import { Card, PageHeader } from "../../components/ui/Display";
import { useAsync } from "../../hooks/useAsync";
import { IMPORTANCE_LABELS, OPPORTUNITY_LABELS, PROFICIENCY_SHORT } from "./labels";

const STEPS = ["Project", "Required skills", "Team", "Working together", "Rules & review"] as const;

const EMPTY: ProjectInput = {
  title: "",
  description: "",
  opportunity_type: "hackathon",
  event_key: null,
  requirements: [{ skill: "", importance: 2, desired_proficiency: 2, mandatory: false }],
  target_size: 4,
  creator_role: null,
  vacant_roles: [],
  allowed_years: null,
  role_mandatory: false,
  synchronous: false,
  min_shared_slots: 0,
  availability_policy: "all",
  availability_mandatory: false,
  weekly_hours: null,
  work_mode: null,
  unverifiable_policy: "exclude",
  visibility: "public",
};

function validate(step: number, d: ProjectInput): string | null {
  if (step === 0) {
    if (d.title.trim().length < 3) return "Give the project a title (at least 3 characters).";
    if (d.description.trim().length < 20) return "Describe the project in at least 20 characters — it is used for semantic matching.";
  }
  if (step === 1) {
    const reqs = d.requirements.filter((r) => r.skill.trim());
    if (!reqs.length) return "List at least one required skill.";
    const keys = reqs.map((r) => r.skill.trim().toLowerCase());
    if (new Set(keys).size !== keys.length) return "Each skill can be listed once.";
  }
  if (step === 2 && (d.target_size < 2 || d.target_size > 12)) return "Target team size must be between 2 and 12.";
  if (step === 3 && d.synchronous && d.min_shared_slots < 1) return "Synchronous teams must ask for at least one shared weekly slot.";
  if (step === 4 && d.role_mandatory && !d.vacant_roles.length) return "A mandatory role rule needs at least one vacant role.";
  return null;
}

export function ProjectWizardPage() {
  const { projectId } = useParams();
  const editing = !!projectId;
  const navigate = useNavigate();
  const vocab = useAsync(() => api.get<Vocabulary>("/profiles/vocabulary"), []);
  const existing = useAsync(() => (editing ? api.get<Project>(`/projects/${projectId}`) : Promise.resolve(null)), [projectId]);
  const [d, setD] = useState<ProjectInput>(EMPTY);
  const [status, setStatus] = useState<"open" | "closed">("open");
  const [step, setStep] = useState(0);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const listId = useId();

  useEffect(() => {
    const p = existing.data;
    if (p) {
      const { id: _i, owner_id: _o, open_positions: _op, members: _m, created_at: _c, updated_at: _u, version: _v, viewer: _vw, status: s, ...rest } = p;
      setD({ ...rest, creator_role: null });
      setStatus(s);
    }
  }, [existing.data]);

  if (!vocab.data || (editing && !existing.data)) return <LoadState loading={vocab.loading || existing.loading} error={vocab.error ?? existing.error} />;
  if (editing && existing.data && !existing.data.viewer.is_owner) return <Alert tone="error">Only the project creator can edit it.</Alert>;

  const set = <K extends keyof ProjectInput>(k: K, v: ProjectInput[K]) => setD({ ...d, [k]: v });
  const setReq = (i: number, patch: Partial<Requirement>) => set("requirements", d.requirements.map((r, j) => (j === i ? { ...r, ...patch } : r)));

  const next = () => {
    const err = validate(step, d);
    setError(err);
    if (!err) setStep(step + 1);
  };

  const submit = async () => {
    for (let s = 0; s < STEPS.length; s++) {
      const err = validate(s, d);
      if (err) {
        setStep(s);
        return setError(err);
      }
    }
    setBusy(true);
    setError(null);
    const body = {
      ...d,
      requirements: d.requirements.filter((r) => r.skill.trim()),
      event_key: d.event_key?.trim() || null,
      min_shared_slots: d.synchronous ? d.min_shared_slots : 0,
      availability_mandatory: d.synchronous && d.availability_mandatory,
    };
    try {
      const saved = editing
        ? await api.put<Project>(`/projects/${projectId}`, { ...body, creator_role: undefined, status, version: existing.data!.version })
        : await api.post<Project>("/projects", body);
      navigate(editing ? `/projects/${saved.id}` : `/projects/${saved.id}/recommendations`);
    } catch (e) {
      setError(errorMessage(e));
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="mx-auto max-w-3xl">
      <PageHeader title={editing ? "Edit project" : "Start a team"} subtitle="Describe what the team needs. Assembl uses this to rank candidates against the members you already have." />
      <ol className="mb-6 flex flex-wrap gap-2 text-sm" aria-label="Steps">
        {STEPS.map((s, i) => (
          <li key={s}>
            <button
              type="button"
              aria-current={i === step ? "step" : undefined}
              onClick={() => (i < step || !validate(step, d)) && setStep(i)}
              className={`rounded-full px-3 py-1 ${i === step ? "bg-brand-700 text-white" : i < step ? "bg-brand-50 text-brand-800" : "bg-paper-sunk text-ink-soft"}`}
            >
              {i + 1}. {s}
            </button>
          </li>
        ))}
      </ol>

      <Card className="space-y-5 p-6">
        {step === 0 && (
          <>
            <Field label="Title">{(id) => <input id={id} className="input" maxLength={120} value={d.title} onChange={(e) => set("title", e.target.value)} />}</Field>
            <Field label="Description" hint="What you are building and for which event or course. This text is used for semantic matching.">
              {(id) => <textarea id={id} className="input" rows={6} maxLength={4000} value={d.description} onChange={(e) => set("description", e.target.value)} />}
            </Field>
            <div className="grid gap-4 sm:grid-cols-2">
              <Field label="Type">
                {(id) => (
                  <select id={id} className="input" value={d.opportunity_type} onChange={(e) => set("opportunity_type", e.target.value as ProjectInput["opportunity_type"])}>
                    {Object.entries(OPPORTUNITY_LABELS).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
                  </select>
                )}
              </Field>
              <Field label="Event key (optional)" hint="e.g. sih-2026. A student can be on only one team per event.">
                {(id) => <input id={id} className="input" maxLength={80} value={d.event_key ?? ""} onChange={(e) => set("event_key", e.target.value || null)} />}
              </Field>
            </div>
            <Toggle checked={d.visibility === "public"} onChange={(v) => set("visibility", v ? "public" : "private")} label="List this project publicly" description="Private projects are visible only to members and invited students." />
            {editing && <Toggle checked={status === "open"} onChange={(v) => setStatus(v ? "open" : "closed")} label="Recruiting" description="Closing a project stops recommendations and join requests." />}
          </>
        )}

        {step === 1 && (
          <>
            <p className="text-sm text-ink-soft">
              <strong>Importance</strong> weights a skill in the coverage calculation. <strong>Mandatory</strong> is separate: it removes every candidate who does not state
              at least the desired level. Use it sparingly.
            </p>
            <datalist id={listId}>{vocab.data.skills.map((s) => <option key={s} value={s} />)}</datalist>
            <ul className="space-y-3">
              {d.requirements.map((r, i) => (
                <li key={i} className="grid gap-2 rounded-md border border-line p-3 sm:grid-cols-[1fr_8rem_10rem_auto_auto] sm:items-center">
                  <input className="input" list={listId} aria-label={`Skill ${i + 1}`} placeholder="Skill" value={r.skill} maxLength={60} onChange={(e) => setReq(i, { skill: e.target.value })} />
                  <select className="input" aria-label={`Importance of skill ${i + 1}`} value={r.importance} onChange={(e) => setReq(i, { importance: Number(e.target.value) as 1 | 2 | 3 })}>
                    {[1, 2, 3].map((v) => <option key={v} value={v}>{IMPORTANCE_LABELS[v]}</option>)}
                  </select>
                  <select className="input" aria-label={`Desired level for skill ${i + 1}`} value={r.desired_proficiency} onChange={(e) => setReq(i, { desired_proficiency: Number(e.target.value) })}>
                    {[1, 2, 3, 4].map((v) => <option key={v} value={v}>{PROFICIENCY_SHORT[v]}</option>)}
                  </select>
                  <label className="flex items-center gap-1.5 text-sm">
                    <input type="checkbox" checked={r.mandatory} onChange={(e) => setReq(i, { mandatory: e.target.checked })} /> Mandatory
                  </label>
                  <button type="button" className="rounded p-2 text-ink-faint hover:text-ink" aria-label={`Remove skill ${i + 1}`} onClick={() => set("requirements", d.requirements.filter((_, j) => j !== i))}>
                    ✕
                  </button>
                </li>
              ))}
            </ul>
            <Button variant="secondary" size="sm" disabled={d.requirements.length >= 20} onClick={() => set("requirements", [...d.requirements, { skill: "", importance: 2, desired_proficiency: 2, mandatory: false }])}>
              + Add skill
            </Button>
          </>
        )}

        {step === 2 && (
          <>
            <Field label="Target team size" hint={editing ? "Cannot be below the current number of members." : "Including you."}>
              {(id) => <input id={id} type="number" min={2} max={12} className="input w-32" value={d.target_size} onChange={(e) => set("target_size", Number(e.target.value))} />}
            </Field>
            {!editing && (
              <Field label="Your role in the team (optional)">
                {(id) => <input id={id} className="input" list={`${listId}-roles`} maxLength={40} value={d.creator_role ?? ""} onChange={(e) => set("creator_role", e.target.value || null)} />}
              </Field>
            )}
            <datalist id={`${listId}-roles`}>{vocab.data.roles.map((r) => <option key={r} value={r} />)}</datalist>
            <TagInput label="Vacant roles" value={d.vacant_roles} onChange={(v) => set("vacant_roles", v)} suggestions={vocab.data.roles} max={8} placeholder="e.g. Backend, Designer" />
            {!editing && <p className="text-sm text-ink-soft">Already have teammates? After creating the project, invite them by handle from the project page.</p>}
          </>
        )}

        {step === 3 && (
          <>
            <Toggle checked={d.synchronous} onChange={(v) => setD({ ...d, synchronous: v, min_shared_slots: v ? Math.max(1, d.min_shared_slots) : 0 })} label="We meet at fixed times each week" description="Turns on the shared-availability signal, computed from current members' weekly slots." />
            {d.synchronous && (
              <div className="grid gap-4 sm:grid-cols-2">
                <Field label="Minimum shared weekly slots">
                  {(id) => <input id={id} type="number" min={1} max={21} className="input" value={d.min_shared_slots} onChange={(e) => set("min_shared_slots", Number(e.target.value))} />}
                </Field>
                <Field label="Team slots are those shared by" hint="Larger teams may prefer a majority.">
                  {(id) => (
                    <select id={id} className="input" value={d.availability_policy} onChange={(e) => set("availability_policy", e.target.value as "all" | "majority")}>
                      <option value="all">All current members</option>
                      <option value="majority">A majority of members</option>
                    </select>
                  )}
                </Field>
                <div className="sm:col-span-2">
                  <Toggle checked={d.availability_mandatory} onChange={(v) => set("availability_mandatory", v)} label="Make the minimum mandatory" description="Otherwise it only affects ranking." />
                </div>
              </div>
            )}
            <div className="grid gap-4 sm:grid-cols-2">
              <Field label="Expected hours per week">
                {(id) => <input id={id} type="number" min={1} max={40} className="input" placeholder="Not stated" value={d.weekly_hours ?? ""} onChange={(e) => set("weekly_hours", e.target.value ? Math.max(1, Math.min(40, Number(e.target.value))) : null)} />}
              </Field>
              <Field label="Working mode">
                {(id) => (
                  <select id={id} className="input" value={d.work_mode ?? ""} onChange={(e) => set("work_mode", (e.target.value || null) as WorkMode | null)}>
                    <option value="">Not stated</option>
                    <option value="online">Online</option>
                    <option value="offline">In person</option>
                    <option value="hybrid">Hybrid</option>
                  </select>
                )}
              </Field>
            </div>
          </>
        )}

        {step === 4 && (
          <>
            <fieldset>
              <legend className="label">Allowed years of study (leave all unchecked for no rule)</legend>
              <div className="flex flex-wrap gap-3">
                {[1, 2, 3, 4, 5, 6].map((y) => (
                  <label key={y} className="flex items-center gap-1.5 text-sm">
                    <input
                      type="checkbox"
                      checked={d.allowed_years?.includes(y) ?? false}
                      onChange={(e) => {
                        const cur = new Set(d.allowed_years ?? []);
                        if (e.target.checked) cur.add(y);
                        else cur.delete(y);
                        set("allowed_years", cur.size ? [...cur].sort() : null);
                      }}
                    />
                    Year {y}
                  </label>
                ))}
              </div>
            </fieldset>
            <Toggle checked={d.role_mandatory} onChange={(v) => set("role_mandatory", v)} label="Candidates must prefer one of the vacant roles" />
            <Field label="If a candidate leaves a checked field blank" hint="Unknown information is never treated as failing a rule — you decide whether to see those students.">
              {(id) => (
                <select id={id} className="input" value={d.unverifiable_policy} onChange={(e) => set("unverifiable_policy", e.target.value as "exclude" | "include")}>
                  <option value="exclude">Don't show them</option>
                  <option value="include">Show them, flagged as unverified</option>
                </select>
              )}
            </Field>
            <div className="rounded-md bg-paper-sunk p-4 text-sm">
              <p className="font-medium">{d.title || "Untitled project"}</p>
              <p className="text-ink-soft">
                {d.requirements.filter((r) => r.skill.trim()).length} required skills · team of {d.target_size} · {d.vacant_roles.length ? `vacant: ${d.vacant_roles.join(", ")}` : "no vacant roles listed"}
                {d.synchronous ? ` · ${d.min_shared_slots}+ shared slots` : " · asynchronous"}
              </p>
            </div>
          </>
        )}

        {error && <Alert tone="error">{error}</Alert>}
        <div className="flex justify-between border-t border-line pt-4">
          <Button variant="ghost" disabled={step === 0} onClick={() => { setError(null); setStep(step - 1); }}>
            Back
          </Button>
          {step < STEPS.length - 1 ? (
            <Button onClick={next}>Continue</Button>
          ) : (
            <Button onClick={submit} busy={busy}>
              {editing ? "Save changes" : "Create and see candidates"}
            </Button>
          )}
        </div>
      </Card>
    </div>
  );
}
