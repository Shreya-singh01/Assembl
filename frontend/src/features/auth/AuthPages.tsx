import { useState, type FormEvent } from "react";
import { Link, useLocation, useNavigate } from "react-router-dom";
import { errorMessage } from "../../api/client";
import { useAuth } from "../../app/AuthContext";
import { Button } from "../../components/ui/Button";
import { Alert } from "../../components/ui/Feedback";
import { Field } from "../../components/ui/Form";

function AuthShell({ title, children, footer }: { title: string; children: React.ReactNode; footer: React.ReactNode }) {
  return (
    <div className="mx-auto max-w-sm px-4 py-14">
      <h1 className="text-2xl font-semibold">{title}</h1>
      <div className="card mt-6 p-6">{children}</div>
      <p className="mt-4 text-center text-sm text-ink-soft">{footer}</p>
    </div>
  );
}

export function LoginPage() {
  const { login } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      const user = await login(email, password);
      const from = (location.state as { from?: string } | null)?.from;
      navigate(from ?? (user.profile_complete ? "/dashboard" : "/profile?onboarding=1"), { replace: true });
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setBusy(false);
    }
  };

  return (
    <AuthShell title="Sign in" footer={<>New here? <Link className="text-brand-700 underline" to="/register">Create an account</Link></>}>
      <form onSubmit={submit} className="space-y-4" noValidate>
        {error && <Alert tone="error">{error}</Alert>}
        <Field label="E-mail">{(id) => <input id={id} className="input" type="email" autoComplete="email" required value={email} onChange={(e) => setEmail(e.target.value)} />}</Field>
        <Field label="Password">
          {(id) => <input id={id} className="input" type="password" autoComplete="current-password" required value={password} onChange={(e) => setPassword(e.target.value)} />}
        </Field>
        <Button type="submit" className="w-full" busy={busy}>
          Sign in
        </Button>
      </form>
    </AuthShell>
  );
}

export function RegisterPage() {
  const { register } = useAuth();
  const navigate = useNavigate();
  const [form, setForm] = useState({ email: "", password: "", display_name: "", handle: "", accept_terms: false });
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const set = (k: keyof typeof form) => (e: React.ChangeEvent<HTMLInputElement>) =>
    setForm({ ...form, [k]: e.target.type === "checkbox" ? e.target.checked : e.target.value });

  const handleOk = /^[a-zA-Z0-9_]{3,24}$/.test(form.handle);
  const submit = async (e: FormEvent) => {
    e.preventDefault();
    if (form.password.length < 10) return setError("Use a password of at least 10 characters.");
    if (!handleOk) return setError("Handles use 3–24 letters, digits or underscores.");
    if (!form.accept_terms) return setError("Please accept the data-use terms to continue.");
    setBusy(true);
    setError(null);
    try {
      await register(form);
      navigate("/profile?onboarding=1", { replace: true });
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setBusy(false);
    }
  };

  return (
    <AuthShell title="Create your account" footer={<>Already registered? <Link className="text-brand-700 underline" to="/login">Sign in</Link></>}>
      <form onSubmit={submit} className="space-y-4" noValidate>
        {error && <Alert tone="error">{error}</Alert>}
        <Field label="Display name" hint="Shown to teams. Never used for ranking.">
          {(id) => <input id={id} className="input" autoComplete="name" required maxLength={60} value={form.display_name} onChange={set("display_name")} />}
        </Field>
        <Field label="Handle" hint="How teammates can find and invite you, e.g. asha_k" error={form.handle && !handleOk ? "3–24 letters, digits or underscores" : undefined}>
          {(id) => <input id={id} className="input" autoComplete="username" required value={form.handle} onChange={set("handle")} />}
        </Field>
        <Field label="E-mail" hint="Used to sign in. Never shown to other students.">
          {(id) => <input id={id} className="input" type="email" autoComplete="email" required value={form.email} onChange={set("email")} />}
        </Field>
        <Field label="Password" hint="At least 10 characters.">
          {(id) => <input id={id} className="input" type="password" autoComplete="new-password" required minLength={10} value={form.password} onChange={set("password")} />}
        </Field>
        <label className="flex items-start gap-2 text-sm">
          <input type="checkbox" className="mt-1" checked={form.accept_terms} onChange={set("accept_terms")} />
          <span>
            I agree that Assembl stores my account and the profile information I choose to add, as described in the{" "}
            <Link to="/privacy" className="text-brand-700 underline">
              privacy notice
            </Link>
            . My profile stays hidden until I choose to show it.
          </span>
        </label>
        <Button type="submit" className="w-full" busy={busy}>
          Create account
        </Button>
      </form>
    </AuthShell>
  );
}
