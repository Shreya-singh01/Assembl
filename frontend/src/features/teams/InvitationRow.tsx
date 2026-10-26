import { useState } from "react";
import { Link } from "react-router-dom";
import { api, errorMessage } from "../../api/client";
import type { Invitation } from "../../api/types";
import { Button } from "../../components/ui/Button";
import { Badge, timeAgo } from "../../components/ui/Display";

const STATUS_TONE: Record<string, "brand" | "neutral" | "muted" | "warn"> = {
  pending: "neutral",
  accepted: "brand",
  declined: "muted",
  cancelled: "muted",
  expired: "warn",
};

const REASONS: Record<string, string> = {
  team_full_or_closed: "the team filled up or closed first",
  team_full: "the team filled up",
  already_on_event_team: "already on another team for this event",
};

export function InvitationRow({ inv, box, onChange }: { inv: Invitation; box: "received" | "sent"; onChange: () => void }) {
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const act = async (action: "accept" | "decline" | "cancel") => {
    setBusy(action);
    setError(null);
    try {
      await api.post(`/invitations/${inv.id}/${action}`);
      onChange();
    } catch (e) {
      setError(errorMessage(e));
      onChange();
    } finally {
      setBusy(null);
    }
  };

  const headline =
    inv.kind === "invite"
      ? box === "received"
        ? <>{inv.from_user.display_name} invited you to join <Link className="font-medium hover:underline" to={`/projects/${inv.project_id}`}>{inv.project_title}</Link></>
        : <>You invited {inv.candidate.display_name} to <Link className="font-medium hover:underline" to={`/projects/${inv.project_id}`}>{inv.project_title}</Link></>
      : box === "received"
        ? <>{inv.from_user.display_name} asked to join <Link className="font-medium hover:underline" to={`/projects/${inv.project_id}`}>{inv.project_title}</Link></>
        : <>You asked to join <Link className="font-medium hover:underline" to={`/projects/${inv.project_id}`}>{inv.project_title}</Link></>;

  return (
    <li className="py-3">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0 text-sm">
          <p>{headline}</p>
          <p className="text-xs text-ink-soft">
            {inv.role ? `Role: ${inv.role} · ` : ""}
            {timeAgo(inv.created_at)}
            {inv.reason ? ` · ${REASONS[inv.reason] ?? inv.reason}` : ""}
          </p>
          {inv.message && <p className="mt-1 rounded bg-paper-sunk px-2 py-1 text-sm">“{inv.message}”</p>}
          {error && <p className="mt-1 text-xs text-red-700" role="alert">{error}</p>}
        </div>
        <div className="flex items-center gap-2">
          <Badge tone={STATUS_TONE[inv.status] ?? "neutral"}>{inv.status}</Badge>
          {inv.status === "pending" && box === "received" && (
            <>
              <Button size="sm" onClick={() => act("accept")} busy={busy === "accept"} disabled={!!busy}>
                Accept
              </Button>
              <Button size="sm" variant="secondary" onClick={() => act("decline")} busy={busy === "decline"} disabled={!!busy}>
                Decline
              </Button>
            </>
          )}
          {inv.status === "pending" && box === "sent" && (
            <Button size="sm" variant="ghost" onClick={() => act("cancel")} busy={busy === "cancel"}>
              Withdraw
            </Button>
          )}
        </div>
      </div>
    </li>
  );
}
