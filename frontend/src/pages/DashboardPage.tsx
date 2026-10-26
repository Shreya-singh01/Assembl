import { Link } from "react-router-dom";
import { api } from "../api/client";
import type { Dashboard } from "../api/types";
import { useAuth } from "../app/AuthContext";
import { ButtonLink } from "../components/ui/Button";
import { Alert, EmptyState, LoadState } from "../components/ui/Feedback";
import { Badge, Card, Meter, PageHeader, timeAgo } from "../components/ui/Display";
import { useAsync } from "../hooks/useAsync";
import { InvitationRow } from "../features/teams/InvitationRow";
import { OPPORTUNITY_LABELS } from "../features/projects/labels";

export function DashboardPage() {
  const { user } = useAuth();
  const { data, error, loading, reload } = useAsync(() => api.get<Dashboard>("/dashboard"), []);

  return (
    <div>
      <PageHeader
        title={`Hello, ${user?.display_name ?? ""}`}
        actions={
          <>
            <ButtonLink to="/projects" variant="secondary">
              Browse projects
            </ButtonLink>
            <ButtonLink to="/projects/new">Start a team</ButtonLink>
          </>
        }
      />
      <LoadState loading={loading} error={error} onRetry={reload} />
      {data && (
        <div className="grid gap-6 lg:grid-cols-[2fr_1fr]">
          <div className="space-y-6">
            {!data.profile_completion.ready_for_matching || !data.profile_visible ? (
              <Alert tone="warning" title={data.profile_completion.ready_for_matching ? "Your profile is hidden" : "Add your skills to be found"}>
                {data.profile_completion.ready_for_matching
                  ? "Teams cannot find you until you turn on “Show my profile to teams”."
                  : "Teams are matched with students through their stated skills, roles and availability."}{" "}
                <Link to="/profile" className="font-medium underline">
                  Open your profile
                </Link>
              </Alert>
            ) : null}

            <Card className="p-5">
              <h2 className="font-semibold">Invitations waiting for you</h2>
              {data.pending_received.length === 0 ? (
                <p className="mt-2 text-sm text-ink-soft">Nothing pending.</p>
              ) : (
                <ul className="mt-3 divide-y divide-line">
                  {data.pending_received.map((i) => (
                    <InvitationRow key={i.id} inv={i} box="received" onChange={reload} />
                  ))}
                </ul>
              )}
            </Card>

            <Card className="p-5">
              <h2 className="font-semibold">Your teams</h2>
              {data.my_projects.length === 0 ? (
                <EmptyState title="You are not on a team yet" action={<ButtonLink to="/projects/new">Start a team</ButtonLink>}>
                  Start one and get ranked suggestions for the members you still need, or browse open projects.
                </EmptyState>
              ) : (
                <ul className="mt-3 divide-y divide-line">
                  {data.my_projects.map((p) => (
                    <li key={p.id} className="flex flex-wrap items-center justify-between gap-3 py-3">
                      <div>
                        <Link to={`/projects/${p.id}`} className="font-medium hover:underline">
                          {p.title}
                        </Link>
                        <p className="text-xs text-ink-soft">
                          {p.members.length}/{p.target_size} members · {p.open_positions} open · {p.viewer.is_owner ? "you created this" : "member"}
                        </p>
                      </div>
                      {p.viewer.is_owner && p.open_positions > 0 && p.status === "open" && (
                        <ButtonLink to={`/projects/${p.id}/recommendations`} size="sm" variant="secondary">
                          Find members
                        </ButtonLink>
                      )}
                    </li>
                  ))}
                </ul>
              )}
            </Card>

            <Card className="p-5">
              <h2 className="font-semibold">Projects related to your profile</h2>
              <p className="text-xs text-ink-soft">Ordered by semantic relevance to your profile text only. Teams rank candidates with their full team context.</p>
              {data.suggested_projects.length === 0 ? (
                <p className="mt-2 text-sm text-ink-soft">No open projects to suggest right now.</p>
              ) : (
                <ul className="mt-3 divide-y divide-line">
                  {data.suggested_projects.map((p) => (
                    <li key={p.id} className="flex items-center justify-between gap-3 py-2.5 text-sm">
                      <Link to={`/projects/${p.id}`} className="font-medium hover:underline">
                        {p.title}
                      </Link>
                      <span className="flex items-center gap-2">
                        <Badge tone="muted">{OPPORTUNITY_LABELS[p.opportunity_type]}</Badge>
                        <span className="num text-xs text-ink-soft" title="Semantic relevance (0–1)">
                          {p.semantic_relevance.toFixed(2)}
                        </span>
                      </span>
                    </li>
                  ))}
                </ul>
              )}
            </Card>
          </div>

          <div className="space-y-6">
            <Card className="p-5">
              <h2 className="font-semibold">Profile</h2>
              <div className="mt-3 flex items-center gap-3">
                <Meter value={data.profile_completion.percent / 100} label="Profile completion" />
                <span className="num text-sm">{data.profile_completion.percent}%</span>
              </div>
              {data.profile_completion.missing.length > 0 && (
                <p className="mt-2 text-xs text-ink-soft">Missing: {data.profile_completion.missing.join(", ")}</p>
              )}
              <Link to="/profile" className="mt-3 inline-block text-sm text-brand-700 underline">
                Edit profile
              </Link>
            </Card>
            <Card className="p-5">
              <h2 className="font-semibold">Recent messages</h2>
              {data.recent_conversations.length === 0 ? (
                <p className="mt-2 text-sm text-ink-soft">No conversations yet.</p>
              ) : (
                <ul className="mt-2 space-y-2">
                  {data.recent_conversations.map((c) => (
                    <li key={c.id}>
                      <Link to={`/messages/${c.id}`} className="block rounded p-1.5 hover:bg-paper-sunk">
                        <span className="flex justify-between text-sm font-medium">
                          {c.title}
                          {c.unread > 0 && <Badge tone="brand">{c.unread}</Badge>}
                        </span>
                        <span className="block truncate text-xs text-ink-soft">
                          {c.last_message_preview ?? "No messages"} · {timeAgo(c.last_message_at)}
                        </span>
                      </Link>
                    </li>
                  ))}
                </ul>
              )}
            </Card>
            <Card className="p-5">
              <h2 className="font-semibold">Requests you sent</h2>
              {data.recent_sent.length === 0 ? (
                <p className="mt-2 text-sm text-ink-soft">None.</p>
              ) : (
                <ul className="mt-2 space-y-1.5 text-sm">
                  {data.recent_sent.slice(0, 6).map((i) => (
                    <li key={i.id} className="flex justify-between gap-2">
                      <span className="truncate">
                        {i.kind === "invite" ? `Invited ${i.candidate.display_name}` : `Asked to join ${i.project_title}`}
                      </span>
                      <Badge tone={i.status === "accepted" ? "brand" : i.status === "pending" ? "neutral" : "muted"}>{i.status}</Badge>
                    </li>
                  ))}
                </ul>
              )}
            </Card>
          </div>
        </div>
      )}
    </div>
  );
}
