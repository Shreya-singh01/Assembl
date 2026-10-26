import { useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { api, errorMessage } from "../../api/client";
import type { Conversation, PublicProfile } from "../../api/types";
import { useAuth } from "../../app/AuthContext";
import { Button } from "../../components/ui/Button";
import { Alert, LoadState } from "../../components/ui/Feedback";
import { Badge, Card, PageHeader } from "../../components/ui/Display";
import { useAsync } from "../../hooks/useAsync";

export function ProfileSummary({ p }: { p: PublicProfile }) {
  return (
    <div className="space-y-3 text-sm">
      <div className="flex flex-wrap gap-1.5">
        {p.skills.length === 0 && <span className="text-ink-soft">No skills stated</span>}
        {p.skills.map((s) => (
          <Badge key={s.label} tone="neutral" title={`Self-reported proficiency ${s.proficiency} of 4`}>
            {s.label} · {s.proficiency}
          </Badge>
        ))}
      </div>
      <dl className="grid grid-cols-[8rem_1fr] gap-x-3 gap-y-1">
        <dt className="text-ink-soft">Roles</dt>
        <dd>{[...p.primary_roles, ...p.secondary_roles.map((r) => `${r} (secondary)`)].join(", ") || "Not stated"}</dd>
        <dt className="text-ink-soft">Year / branch</dt>
        <dd>{[p.year ? `Year ${p.year}` : null, p.branch].filter(Boolean).join(" · ") || "Not stated"}</dd>
        <dt className="text-ink-soft">Interests</dt>
        <dd>{p.interests.join(", ") || "Not stated"}</dd>
        <dt className="text-ink-soft">Hours / mode</dt>
        <dd>{[p.weekly_hours ? `${p.weekly_hours} h/week` : null, p.work_mode].filter(Boolean).join(" · ") || "Not stated"}</dd>
        <dt className="text-ink-soft">Availability</dt>
        <dd>{p.availability_stated ? "Stated (slots are private)" : "Not stated"}</dd>
      </dl>
      {p.projects.length > 0 && (
        <ul className="space-y-1.5">
          {p.projects.map((pr, i) => (
            <li key={i} className="rounded bg-paper-sunk px-3 py-2">
              <p className="font-medium">{pr.title}</p>
              {pr.summary && <p className="text-ink-soft">{pr.summary}</p>}
              {pr.contribution && <p className="text-xs text-ink-soft">Contribution: {pr.contribution}</p>}
              {pr.link && (
                <a className="text-xs text-brand-700 underline" href={pr.link} target="_blank" rel="noreferrer noopener">
                  {pr.link}
                </a>
              )}
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

export function PublicProfilePage() {
  const { userId } = useParams();
  const { user } = useAuth();
  const navigate = useNavigate();
  const { data, error, loading, reload } = useAsync(() => api.get<PublicProfile>(`/profiles/${userId}`), [userId]);
  const [msgError, setMsgError] = useState<string | null>(null);

  const message = async () => {
    try {
      const c = await api.post<Conversation>("/conversations", { user_id: userId });
      navigate(`/messages/${c.id}`);
    } catch (e) {
      setMsgError(errorMessage(e));
    }
  };

  return (
    <div>
      <LoadState loading={loading} error={error} onRetry={reload} />
      {data && (
        <>
          <PageHeader
            title={data.display_name}
            subtitle={data.handle ? `@${data.handle}` : undefined}
            actions={user?.id !== data.user_id && <Button variant="secondary" onClick={message}>Message</Button>}
          />
          {msgError && <Alert tone="error">{msgError}</Alert>}
          <Card className="p-5">
            <ProfileSummary p={data} />
            <p className="mt-4 text-xs text-ink-faint">Proficiency levels are self-reported.</p>
          </Card>
        </>
      )}
    </div>
  );
}
