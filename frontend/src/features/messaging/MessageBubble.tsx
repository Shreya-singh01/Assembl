import { useState } from "react";
import type { Message } from "../../api/types";
import { Button } from "../../components/ui/Button";

interface Props {
  m: Message;
  mine: boolean;
  senderName?: string;
  onEdit: (body: string) => Promise<void>;
  onDelete: () => Promise<void>;
}

/** One chat message. Your own messages can be edited or deleted. */
export function MessageBubble({ m, mine, senderName, onEdit, onDelete }: Props) {
  const [mode, setMode] = useState<"view" | "edit" | "confirm-delete">("view");
  const [draft, setDraft] = useState(m.body);
  const [busy, setBusy] = useState(false);
  const canChange = mine && !m.pending && !m.failed && !m.deleted;
  const time = new Date(m.created_at).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });

  const run = async (fn: () => Promise<void>) => {
    setBusy(true);
    try {
      await fn();
      setMode("view");
    } finally {
      setBusy(false);
    }
  };

  if (m.deleted) {
    return (
      <div className={`flex ${mine ? "justify-end" : "justify-start"}`}>
        <p className="rounded-lg border border-dashed border-line px-3 py-1.5 text-xs italic text-ink-faint">Message deleted</p>
      </div>
    );
  }

  return (
    <div className={`group flex ${mine ? "justify-end" : "justify-start"}`}>
      <div className={`max-w-[80%] rounded-lg px-3 py-2 text-sm ${mine ? "bg-brand-700 text-white" : "bg-paper-sunk"} ${m.failed ? "ring-2 ring-red-400" : ""}`}>
        {senderName && <p className="text-xs font-medium text-ink-soft">{senderName}</p>}
        {mode === "edit" ? (
          <form
            onSubmit={(e) => {
              e.preventDefault();
              if (draft.trim() && draft.trim() !== m.body) run(() => onEdit(draft.trim()));
              else setMode("view");
            }}
            className="space-y-2"
          >
            <label htmlFor={`edit-${m.id}`} className="sr-only">Edit message</label>
            <textarea id={`edit-${m.id}`} className="input text-ink" rows={2} maxLength={4000} value={draft} onChange={(e) => setDraft(e.target.value)} autoFocus />
            <div className="flex justify-end gap-2">
              <Button size="sm" variant="secondary" onClick={() => { setDraft(m.body); setMode("view"); }}>Cancel</Button>
              <Button size="sm" type="submit" busy={busy}>Save</Button>
            </div>
          </form>
        ) : (
          <p className="whitespace-pre-wrap break-words">{m.body}</p>
        )}
        <div className={`mt-0.5 flex items-center gap-2 text-[10px] ${mine ? "text-white/70" : "text-ink-faint"}`}>
          <span>{m.pending ? "sending…" : m.failed ? "not sent" : time}</span>
          {m.edited_at && <span>· edited</span>}
          {canChange && mode === "view" && (
            <span className="ml-auto flex gap-2 opacity-0 transition-opacity focus-within:opacity-100 group-hover:opacity-100">
              <button className="underline" onClick={() => { setDraft(m.body); setMode("edit"); }} aria-label="Edit message">Edit</button>
              <button className="underline" onClick={() => setMode("confirm-delete")} aria-label="Delete message">Delete</button>
            </span>
          )}
        </div>
        {mode === "confirm-delete" && (
          <div className="mt-1 flex items-center gap-2 text-xs" role="alertdialog" aria-label="Confirm delete">
            <span>Delete this message for everyone?</span>
            <button className="font-medium underline" disabled={busy} onClick={() => run(onDelete)}>Delete</button>
            <button className="underline" onClick={() => setMode("view")}>Keep</button>
          </div>
        )}
      </div>
    </div>
  );
}
