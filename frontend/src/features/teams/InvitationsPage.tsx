import { useCallback, useState } from "react";
import { api } from "../../api/client";
import type { Invitation } from "../../api/types";
import { useSocketEvent } from "../../app/SocketContext";
import { EmptyState, LoadState } from "../../components/ui/Feedback";
import { Card, PageHeader } from "../../components/ui/Display";
import { useAsync } from "../../hooks/useAsync";
import { InvitationRow } from "./InvitationRow";

export function InvitationsPage() {
  const [box, setBox] = useState<"received" | "sent">("received");
  const { data, error, loading, reload } = useAsync(() => api.get<Invitation[]>("/invitations", { box }), [box]);
  const refresh = useCallback(() => reload(), [reload]);
  useSocketEvent("invitation:new", refresh);
  useSocketEvent("invitation:update", refresh);

  return (
    <div>
      <PageHeader title="Invitations" subtitle="Invitations to you and requests to join teams you created arrive here. Accepting adds you to the team immediately if a place is still open." />
      <div role="tablist" aria-label="Invitation box" className="mb-4 inline-flex rounded-md border border-line bg-paper-raised p-0.5">
        {(["received", "sent"] as const).map((b) => (
          <button
            key={b}
            role="tab"
            aria-selected={box === b}
            className={`rounded px-3 py-1.5 text-sm ${box === b ? "bg-paper-sunk font-medium" : "text-ink-soft"}`}
            onClick={() => setBox(b)}
          >
            {b === "received" ? "Received" : "Sent"}
          </button>
        ))}
      </div>
      <LoadState loading={loading && !data} error={error} onRetry={reload} />
      {data && (
        <Card className="px-5">
          {data.length === 0 ? (
            <div className="py-5">
              <EmptyState title={box === "received" ? "No invitations yet" : "You have not sent anything yet"}>
                {box === "received" ? "Keep your profile visible and complete so teams can find you." : "Invite candidates from a team's recommendations page."}
              </EmptyState>
            </div>
          ) : (
            <ul className="divide-y divide-line">
              {data.map((i) => (
                <InvitationRow key={i.id} inv={i} box={box} onChange={reload} />
              ))}
            </ul>
          )}
        </Card>
      )}
    </div>
  );
}
