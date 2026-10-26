import { useCallback, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { api, errorMessage } from "../../api/client";
import type { Invitation, Project, TeamCoverage } from "../../api/types";
import { useAuth } from "../../app/AuthContext";
import { useSocketEvent } from "../../app/SocketContext";
import { Button, ButtonLink } from "../../components/ui/Button";
import { Alert, LoadState } from "../../components/ui/Feedback";
import { Field } from "../../components/ui/Form";
import { Badge, Card, Dialog, PageHeader, timeAgo } from "../../components/ui/Display";
import { useAsync } from "../../hooks/useAsync";
import { CoverageChart } from "../recommendations/CoverageChart";
import { InvitationRow } from "../teams/InvitationRow";
import { IMPORTANCE_LABELS, OPPORTUNITY_LABELS } from "./labels";

function Rules({ p }: { p: Project }) {
  const items: string[] = [];
  if (p.allowed_years) items.push(`Year of study: ${p.allowed_years.join(", ")}`);
  p.requirements.filter((r) => r.mandatory).forEach((r) => items.push(`${r.skill} at level ${r.desired_proficiency} or above`));
  if (p.role_mandatory) items.push(`Must prefer one of: ${p.vacant_roles.join(", ")}`);
  if (p.availability_mandatory) items.push(`At least ${p.min_shared_slots} shared weekly slots`);
  if (p.event_key) items.push(`Not already on another team for “${p.event_key}”`);
  return (
    <div>
      <h3 className="text-sm font-medium">Mandatory conditions</h3>
      {items.length ? (
        <ul className="mt-1 list-disc pl-5 text-sm text-ink-soft">
          {items.map((i) => <li key={i}>{i}</li>)}
        </ul>
      ) : (
        <p className="text-sm text-ink-soft">None — every visible student can be considered.</p>
      )}
      {items.length > 0 && (
        <p className="mt-1 text-xs text-ink-faint">
          Students who leave a checked field blank are {p.unverifiable_policy === "exclude" ? "not shown" : "shown with a flag"}.
        </p>
      )}
    </div>
  );
}

export function ProjectDetailPage() {
  const { projectId } = useParams();
  const { user } = useAuth();
  const navigate = useNavigate();
  const project = useAsync(() => api.get<Project>(`/projects/${projectId}`), [projectId]);
  const coverage = useAsync(() => api.get<TeamCoverage>(`/projects/${projectId}/coverage`), [projectId]);
  const isOwner = project.data?.viewer.is_owner;
  const invitations = useAsync(
    () => (isOwner ? api.get<Invitation[]>(`/projects/${projectId}/invitations`) : Promise.resolve([] as Invitation[])),
    [projectId, isOwner],
  );
  const [joinOpen, setJoinOpen] = useState(false);
  const [inviteOpen, setInviteOpen] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const { reload: reloadProject } = project;
  const { reload: reloadCoverage } = coverage;
  const { reload: reloadInvitations } = invitations;
  const reloadAll = useCallback(() => {
    reloadProject();
    reloadCoverage();
    reloadInvitations();
  }, [reloadProject, reloadCoverage, reloadInvitations]);
  useSocketEvent<{ project_id: string }>(
    "team:update",
    useCallback((e) => e.project_id === projectId && reloadAll(), [projectId, reloadAll]),
  );

  if (!project.data) return <LoadState loading={project.loading} error={project.error} onRetry={project.reload} />;
  const p = project.data;
  const me = p.members.find((m) => m.user_id === user?.id);

  const remove = async (memberId: string, self: boolean) => {
    setError(null);
    try {
      await api.del(`/projects/${p.id}/members/${memberId}`);
      if (self) navigate("/dashboard");
      else reloadAll();
    } catch (e) {
      setError(errorMessage(e));
    }
  };

  return (
    <div>
      <PageHeader
        title={p.title}
        subtitle={
          <>
            {OPPORTUNITY_LABELS[p.opportunity_type]}
            {p.event_key && ` · ${p.event_key}`} · {p.status === "open" ? `${p.open_positions} of ${p.target_size} places open` : "closed"}
            {p.visibility === "private" && " · private"}
          </>
        }
        actions={
          isOwner ? (
            <>
              <ButtonLink to={`/projects/${p.id}/edit`} variant="secondary">
                Edit
              </ButtonLink>
              {p.open_positions > 0 && p.status === "open" && <ButtonLink to={`/projects/${p.id}/recommendations`}>Find members</ButtonLink>}
            </>
          ) : !me && p.status === "open" && p.open_positions > 0 ? (
            p.viewer.pending_invitation ? (
              <Badge tone="brand">{p.viewer.pending_invitation.kind === "invite" ? "You have an invitation" : "Request sent"}</Badge>
            ) : (
              <Button onClick={() => setJoinOpen(true)}>Ask to join</Button>
            )
          ) : null
        }
      />
      {error && <div className="mb-4"><Alert tone="error">{error}</Alert></div>}
      <div className="grid gap-6 lg:grid-cols-[3fr_2fr]">
        <div className="space-y-6">
          <Card className="p-5">
            <p className="whitespace-pre-line text-sm">{p.description}</p>
            <h3 className="mt-5 text-sm font-medium">Required skills</h3>
            <ul className="mt-2 grid gap-1.5 text-sm sm:grid-cols-2">
              {p.requirements.map((r) => (
                <li key={r.skill} className="flex items-center justify-between rounded bg-paper-sunk px-3 py-1.5">
                  <span>{r.skill}</span>
                  <span className="text-xs text-ink-soft">
                    {IMPORTANCE_LABELS[r.importance]} · level {r.desired_proficiency}
                  </span>
                </li>
              ))}
            </ul>
            <dl className="mt-5 grid grid-cols-[10rem_1fr] gap-y-1 text-sm">
              <dt className="text-ink-soft">Vacant roles</dt>
              <dd>{p.vacant_roles.join(", ") || "None listed"}</dd>
              <dt className="text-ink-soft">Weekly hours</dt>
              <dd>{p.weekly_hours ? `${p.weekly_hours} h` : "Not stated"}</dd>
              <dt className="text-ink-soft">Working mode</dt>
              <dd>{p.work_mode ?? "Not stated"}</dd>
              <dt className="text-ink-soft">Meets synchronously</dt>
              <dd>{p.synchronous ? `Yes, needs ${p.min_shared_slots}+ shared weekly slots` : "No"}</dd>
            </dl>
            <div className="mt-5">
              <Rules p={p} />
            </div>
          </Card>
          {isOwner && (
            <Card className="px-5 py-4">
              <div className="flex items-center justify-between">
                <h2 className="font-semibold">Invitations and requests</h2>
                {p.open_positions > 0 && (
                  <Button size="sm" variant="secondary" onClick={() => setInviteOpen(true)}>
                    Invite by handle
                  </Button>
                )}
              </div>
              {invitations.data && invitations.data.length > 0 ? (
                <ul className="divide-y divide-line">
                  {invitations.data.map((i) => (
                    <InvitationRow key={i.id} inv={i} box={i.kind === "request" ? "received" : "sent"} onChange={reloadAll} />
                  ))}
                </ul>
              ) : (
                <p className="py-2 text-sm text-ink-soft">None yet. Invite existing teammates by handle or from the ranked suggestions.</p>
              )}
            </Card>
          )}
        </div>
        <div className="space-y-6">
          <Card className="p-5">
            <h2 className="mb-3 font-semibold">Team ({p.members.length}/{p.target_size})</h2>
            <ul className="divide-y divide-line">
              {p.members.map((m) => (
                <li key={m.user_id} className="flex items-center justify-between gap-2 py-2 text-sm">
                  <span>
                    <Link to={`/students/${m.user_id}`} className="font-medium hover:underline">
                      {m.display_name}
                    </Link>
                    <span className="text-ink-soft"> {m.role ? `· ${m.role}` : ""} {m.is_owner ? "· creator" : ""}</span>
                    <span className="block text-xs text-ink-faint">joined {timeAgo(m.joined_at)}</span>
                  </span>
                  {!m.is_owner && (isOwner || m.user_id === user?.id) && (
                    <Button size="sm" variant="ghost" onClick={() => remove(m.user_id, m.user_id === user?.id)}>
                      {m.user_id === user?.id ? "Leave" : "Remove"}
                    </Button>
                  )}
                </li>
              ))}
            </ul>
          </Card>
          <Card className="p-5">
            <h2 className="mb-3 font-semibold">Requirement coverage</h2>
            {coverage.data ? <CoverageChart coverage={coverage.data} /> : <LoadState loading={coverage.loading} error={coverage.error} />}
          </Card>
        </div>
      </div>
      <JoinDialog open={joinOpen} onClose={() => setJoinOpen(false)} project={p} onDone={reloadAll} />
      <InviteHandleDialog open={inviteOpen} onClose={() => setInviteOpen(false)} project={p} onDone={reloadAll} />
    </div>
  );
}

function JoinDialog({ open, onClose, project, onDone }: { open: boolean; onClose: () => void; project: Project; onDone: () => void }) {
  const [role, setRole] = useState("");
  const [message, setMessage] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const send = async () => {
    setBusy(true);
    setError(null);
    try {
      await api.post(`/projects/${project.id}/join-requests`, { role: role || null, message });
      onClose();
      onDone();
    } catch (e) {
      setError(errorMessage(e));
    } finally {
      setBusy(false);
    }
  };
  return (
    <Dialog open={open} onClose={onClose} title={`Ask to join ${project.title}`}>
      <div className="space-y-4">
        {error && <Alert tone="error">{error}</Alert>}
        {project.vacant_roles.length > 0 && (
          <Field label="Role (optional)">
            {(id) => (
              <select id={id} className="input" value={role} onChange={(e) => setRole(e.target.value)}>
                <option value="">No specific role</option>
                {project.vacant_roles.map((r) => <option key={r}>{r}</option>)}
              </select>
            )}
          </Field>
        )}
        <Field label="Message to the creator (optional)">{(id) => <textarea id={id} className="input" rows={3} maxLength={500} value={message} onChange={(e) => setMessage(e.target.value)} />}</Field>
        <div className="flex justify-end gap-2">
          <Button variant="secondary" onClick={onClose}>Cancel</Button>
          <Button onClick={send} busy={busy}>Send request</Button>
        </div>
      </div>
    </Dialog>
  );
}

export function InviteHandleDialog({ open, onClose, project, onDone }: { open: boolean; onClose: () => void; project: Project; onDone: () => void }) {
  const [handle, setHandle] = useState("");
  const [role, setRole] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const send = async () => {
    setBusy(true);
    setError(null);
    try {
      await api.post(`/projects/${project.id}/invitations/by-handle`, { handle: handle.replace(/^@/, ""), role: role || null, message: "" });
      setHandle("");
      onClose();
      onDone();
    } catch (e) {
      setError(errorMessage(e));
    } finally {
      setBusy(false);
    }
  };
  return (
    <Dialog open={open} onClose={onClose} title="Invite a teammate by handle">
      <div className="space-y-4">
        <p className="text-sm text-ink-soft">Use this for people you already work with. They must have a visible profile.</p>
        {error && <Alert tone="error">{error}</Alert>}
        <Field label="Handle">{(id) => <input id={id} className="input" placeholder="@asha_k" value={handle} onChange={(e) => setHandle(e.target.value)} />}</Field>
        {project.vacant_roles.length > 0 && (
          <Field label="Role (optional)">
            {(id) => (
              <select id={id} className="input" value={role} onChange={(e) => setRole(e.target.value)}>
                <option value="">No specific role</option>
                {project.vacant_roles.map((r) => <option key={r}>{r}</option>)}
              </select>
            )}
          </Field>
        )}
        <div className="flex justify-end gap-2">
          <Button variant="secondary" onClick={onClose}>Cancel</Button>
          <Button onClick={send} busy={busy} disabled={handle.trim().length < 3}>Send invitation</Button>
        </div>
      </div>
    </Dialog>
  );
}
