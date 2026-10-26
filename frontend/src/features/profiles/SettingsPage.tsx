import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { api, errorMessage } from "../../api/client";
import type { User } from "../../api/types";
import { useAuth } from "../../app/AuthContext";
import { Button } from "../../components/ui/Button";
import { Alert } from "../../components/ui/Feedback";
import { Field, Toggle } from "../../components/ui/Form";
import { Card, Dialog, PageHeader } from "../../components/ui/Display";

export function SettingsPage() {
  const { user, setUser, logout } = useAuth();
  const navigate = useNavigate();
  const [error, setError] = useState<string | null>(null);
  const [open, setOpen] = useState(false);
  const [password, setPassword] = useState("");
  const [confirm, setConfirm] = useState("");
  const [busy, setBusy] = useState(false);

  const setResearch = async (v: boolean) => {
    try {
      setUser(await api.put<User>("/auth/consent", { research_participation: v }));
    } catch (e) {
      setError(errorMessage(e));
    }
  };

  const remove = async () => {
    setBusy(true);
    setError(null);
    try {
      await api.post("/auth/delete-account", { password, confirm });
      await logout().catch(() => undefined);
      navigate("/", { replace: true });
    } catch (e) {
      setError(errorMessage(e));
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="max-w-2xl space-y-6">
      <PageHeader title="Privacy & account" subtitle={`Signed in as ${user?.email}. Your e-mail is never shown to other students.`} />
      {error && <Alert tone="error">{error}</Alert>}
      <Card className="p-5">
        <h2 className="font-semibold">Research participation</h2>
        <p className="mb-4 mt-1 text-sm text-ink-soft">
          Optional. If on, an anonymised version of your profile may appear in evaluation scenarios rated by student raters. It never changes how you are ranked.
        </p>
        <Toggle checked={!!user?.consent.research_participation} onChange={setResearch} label="I agree to anonymised research use of my profile" />
      </Card>
      <Card className="p-5">
        <h2 className="font-semibold">Profile visibility</h2>
        <p className="mt-1 text-sm text-ink-soft">Hide or show your profile from the “Visibility” section of your profile page.</p>
      </Card>
      <Card className="border-red-200 p-5">
        <h2 className="font-semibold text-red-800">Delete account</h2>
        <p className="mb-4 mt-1 text-sm text-ink-soft">
          Permanently removes your account, profile, stored embeddings, invitations, teams you created, your messages and direct conversations. Your place on
          other teams reopens. This cannot be undone.
        </p>
        <Button variant="danger" onClick={() => setOpen(true)}>
          Delete my account…
        </Button>
      </Card>
      <Dialog open={open} onClose={() => setOpen(false)} title="Delete your account?">
        <div className="space-y-4">
          <Field label="Your password">{(id) => <input id={id} type="password" className="input" value={password} onChange={(e) => setPassword(e.target.value)} autoComplete="current-password" />}</Field>
          <Field label="Type DELETE to confirm">{(id) => <input id={id} className="input" value={confirm} onChange={(e) => setConfirm(e.target.value)} />}</Field>
          <div className="flex justify-end gap-2">
            <Button variant="secondary" onClick={() => setOpen(false)}>
              Keep my account
            </Button>
            <Button variant="danger" disabled={confirm !== "DELETE" || !password} busy={busy} onClick={remove}>
              Delete permanently
            </Button>
          </div>
        </div>
      </Dialog>
    </div>
  );
}
