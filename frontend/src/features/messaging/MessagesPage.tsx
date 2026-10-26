import { useCallback, useEffect, useRef, useState, type FormEvent } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { api, errorMessage } from "../../api/client";
import type { Conversation, Message } from "../../api/types";
import { useAuth } from "../../app/AuthContext";
import { useSocket, useSocketEvent } from "../../app/SocketContext";
import { Button } from "../../components/ui/Button";
import { Alert, EmptyState, LoadState } from "../../components/ui/Feedback";
import { Badge, Card, PageHeader, timeAgo } from "../../components/ui/Display";
import { useAsync } from "../../hooks/useAsync";

const newClientId = () => (crypto.randomUUID?.() ?? `${Date.now()}-${Math.random().toString(36).slice(2)}`).replace(/[^A-Za-z0-9_-]/g, "").slice(0, 40);

export function MessagesPage() {
  const { conversationId } = useParams();
  const navigate = useNavigate();
  const convs = useAsync(() => api.get<Conversation[]>("/conversations"), []);
  const { reload } = convs;
  useSocketEvent("message:new", useCallback(() => reload(), [reload]));

  return (
    <div>
      <PageHeader title="Messages" subtitle="Only the people in a conversation can read it. You never need to share contact details to coordinate." />
      <LoadState loading={convs.loading && !convs.data} error={convs.error} onRetry={reload} />
      {convs.data && (
        <div className="grid min-h-[28rem] gap-4 md:grid-cols-[18rem_1fr]">
          <Card className={`overflow-hidden ${conversationId ? "hidden md:block" : ""}`}>
            {convs.data.length === 0 ? (
              <div className="p-4">
                <EmptyState title="No conversations yet">Message a student from their profile, or talk with your team in its team chat.</EmptyState>
              </div>
            ) : (
              <ul className="divide-y divide-line" aria-label="Conversations">
                {convs.data.map((c) => (
                  <li key={c.id}>
                    <Link
                      to={`/messages/${c.id}`}
                      aria-current={c.id === conversationId ? "page" : undefined}
                      className={`block px-4 py-3 hover:bg-paper-sunk ${c.id === conversationId ? "bg-paper-sunk" : ""}`}
                    >
                      <span className="flex items-center justify-between gap-2 text-sm font-medium">
                        <span className="truncate">{c.title}</span>
                        {c.unread > 0 && <Badge tone="brand">{c.unread}</Badge>}
                      </span>
                      <span className="block truncate text-xs text-ink-soft">
                        {c.last_message_preview ?? "No messages yet"} {c.last_message_at && `· ${timeAgo(c.last_message_at)}`}
                      </span>
                    </Link>
                  </li>
                ))}
              </ul>
            )}
          </Card>
          {conversationId ? (
            <Thread key={conversationId} conversation={convs.data.find((c) => c.id === conversationId) ?? null} id={conversationId} onBack={() => navigate("/messages")} onActivity={reload} />
          ) : (
            <Card className="hidden items-center justify-center p-8 text-sm text-ink-soft md:flex">Select a conversation.</Card>
          )}
        </div>
      )}
    </div>
  );
}

function Thread({ id, conversation, onBack, onActivity }: { id: string; conversation: Conversation | null; onBack: () => void; onActivity: () => void }) {
  const { user } = useAuth();
  const { socket, connected } = useSocket();
  const [messages, setMessages] = useState<Message[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [body, setBody] = useState("");
  const [hasMore, setHasMore] = useState(false);
  const bottom = useRef<HTMLDivElement>(null);

  const markRead = useCallback(() => {
    api.post(`/conversations/${id}/read`).then(onActivity).catch(() => undefined);
  }, [id, onActivity]);

  useEffect(() => {
    setLoading(true);
    api
      .get<Message[]>(`/conversations/${id}/messages`, { limit: 50 })
      .then((m) => {
        setMessages(m);
        setHasMore(m.length === 50);
        markRead();
      })
      .catch((e) => setError(errorMessage(e)))
      .finally(() => setLoading(false));
  }, [id, markRead]);

  useEffect(() => {
    bottom.current?.scrollIntoView?.({ block: "end" });
  }, [messages.length]);

  useSocketEvent<Message>(
    "message:new",
    useCallback(
      (m) => {
        if (m.conversation_id !== id) return;
        setMessages((cur) => (cur.some((x) => x.id === m.id || x.client_id === m.client_id) ? cur.map((x) => (x.client_id === m.client_id ? m : x)) : [...cur, m]));
        if (m.sender_id !== user?.id) markRead();
      },
      [id, user?.id, markRead],
    ),
  );

  const older = async () => {
    const first = messages.find((m) => !m.pending);
    if (!first) return;
    const m = await api.get<Message[]>(`/conversations/${id}/messages`, { before: first.id, limit: 50 });
    setMessages((cur) => [...m, ...cur]);
    setHasMore(m.length === 50);
  };

  const send = async (e: FormEvent) => {
    e.preventDefault();
    const text = body.trim();
    if (!text) return;
    const client_id = newClientId();
    const optimistic: Message = { id: client_id, conversation_id: id, sender_id: user!.id, body: text, created_at: new Date().toISOString(), client_id, pending: true };
    setMessages((cur) => [...cur, optimistic]);
    setBody("");
    const settle = (m: Message | null, err?: string) => {
      setMessages((cur) => cur.map((x) => (x.client_id === client_id ? (m ? m : { ...x, pending: false, failed: true }) : x)));
      if (err) setError(err);
      onActivity();
    };
    if (socket && connected) {
      socket.timeout(8000).emit("message:send", { conversation_id: id, body: text, client_id }, (err: Error | null, ack: { ok: boolean; message?: Message; error?: string }) => {
        if (err) return settle(null, "Message not confirmed; it will appear once delivered, or try again.");
        if (ack?.ok && ack.message) settle(ack.message);
        else settle(null, ack?.error ?? "Could not send");
      });
    } else {
      try {
        settle(await api.post<Message>(`/conversations/${id}/messages`, { body: text, client_id }));
      } catch (err) {
        settle(null, errorMessage(err));
      }
    }
  };

  return (
    <Card className="flex min-h-[28rem] flex-col">
      <div className="flex items-center gap-3 border-b border-line px-4 py-3">
        <button className="text-sm text-ink-soft md:hidden" onClick={onBack}>← Back</button>
        <div className="min-w-0">
          <h2 className="truncate font-semibold">{conversation?.title ?? "Conversation"}</h2>
          {conversation && <p className="truncate text-xs text-ink-soft">{conversation.participants.map((p) => p.display_name).join(", ")}</p>}
        </div>
        {!connected && <span className="ml-auto text-xs text-ink-faint">live updates offline — messages still send</span>}
      </div>
      <div className="flex-1 space-y-2 overflow-y-auto px-4 py-3" aria-live="polite" aria-label="Messages">
        {loading && <p className="text-sm text-ink-soft">Loading…</p>}
        {hasMore && <Button size="sm" variant="ghost" onClick={older}>Load older messages</Button>}
        {!loading && messages.length === 0 && <p className="text-sm text-ink-soft">No messages yet. Say hello.</p>}
        {messages.map((m) => {
          const mine = m.sender_id === user?.id;
          const sender = conversation?.participants.find((p) => p.id === m.sender_id);
          return (
            <div key={m.client_id} className={`flex ${mine ? "justify-end" : "justify-start"}`}>
              <div className={`max-w-[80%] rounded-lg px-3 py-2 text-sm ${mine ? "bg-brand-700 text-white" : "bg-paper-sunk"} ${m.failed ? "ring-2 ring-red-400" : ""}`}>
                {!mine && conversation?.kind === "team" && <p className="text-xs font-medium text-ink-soft">{sender?.display_name ?? "Former member"}</p>}
                <p className="whitespace-pre-wrap break-words">{m.body}</p>
                <p className={`mt-0.5 text-[10px] ${mine ? "text-white/70" : "text-ink-faint"}`}>
                  {m.pending ? "sending…" : m.failed ? "not sent" : new Date(m.created_at).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}
                </p>
              </div>
            </div>
          );
        })}
        <div ref={bottom} />
      </div>
      {error && <div className="px-4"><Alert tone="error">{error}</Alert></div>}
      <form onSubmit={send} className="flex gap-2 border-t border-line p-3">
        <label htmlFor="msg" className="sr-only">Message</label>
        <textarea
          id="msg"
          className="input min-h-[2.5rem] resize-none"
          rows={1}
          maxLength={4000}
          value={body}
          onChange={(e) => setBody(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter" && !e.shiftKey) {
              e.preventDefault();
              (e.currentTarget.form as HTMLFormElement).requestSubmit();
            }
          }}
          placeholder="Write a message"
        />
        <Button type="submit" disabled={!body.trim()}>Send</Button>
      </form>
    </Card>
  );
}
