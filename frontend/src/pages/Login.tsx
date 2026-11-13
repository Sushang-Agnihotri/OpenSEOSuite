import { useQuery } from "@tanstack/react-query";
import { Share2 } from "lucide-react";
import { type FormEvent, useState } from "react";
import { Button, ErrorBox, Field, Input, Spinner } from "../components/ui";
import { api, errorMessage } from "../lib/api";
import { useAuth } from "../lib/context";

export default function Login() {
  const { login, register } = useAuth();
  const { data: status, isLoading, error: statusError } = useQuery({ queryKey: ["auth-status"], queryFn: () => api.get("/auth/status"), retry: false });
  const [mode, setMode] = useState<"login" | "register" | null>(null);
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  if (isLoading) return <Spinner label="Connecting…" />;
  const firstRun = status && !status.has_users;
  const active = mode ?? (firstRun ? "register" : "login");

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      await (active === "register" ? register(email, password) : login(email, password));
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="flex min-h-screen items-center justify-center bg-slate-50 p-4 dark:bg-slate-950">
      <div className="w-full max-w-sm">
        <div className="mb-6 flex flex-col items-center text-center">
          <span className="mb-3 flex h-11 w-11 items-center justify-center rounded-xl bg-brand-600 text-white"><Share2 className="h-5 w-5" /></span>
          <h1 className="text-lg font-semibold text-slate-900 dark:text-slate-50">OpenSEOSuite</h1>
          <p className="mt-1 text-sm text-slate-500 dark:text-slate-400">
            {firstRun ? "Welcome. Create the administrator account for this installation." : active === "register" ? "Create an account" : "Sign in to your workspace"}
          </p>
        </div>
        <form onSubmit={submit} className="space-y-4 rounded-xl border border-slate-200 bg-white p-5 shadow-sm dark:border-slate-800 dark:bg-slate-900">
          {statusError ? <ErrorBox error={statusError} /> : null}
          {error && <ErrorBox error={error} />}
          <Field label="Email">
            <Input type="email" autoComplete="email" required value={email} onChange={(e) => setEmail(e.target.value)} placeholder="you@example.com" />
          </Field>
          <Field label="Password" hint={active === "register" ? "At least 8 characters. Stored as an Argon2id hash." : undefined}>
            <Input type="password" autoComplete={active === "register" ? "new-password" : "current-password"} required
              minLength={active === "register" ? 8 : 1} value={password} onChange={(e) => setPassword(e.target.value)} />
          </Field>
          <Button type="submit" variant="primary" loading={busy} className="w-full">{active === "register" ? "Create account" : "Sign in"}</Button>
          {!firstRun && status?.registration_open && (
            <button type="button" className="block w-full text-center text-xs text-brand-700 hover:underline dark:text-brand-300"
              onClick={() => { setMode(active === "login" ? "register" : "login"); setError(null); }}>
              {active === "login" ? "Need an account? Register" : "Already registered? Sign in"}
            </button>
          )}
        </form>
        <p className="mt-4 text-center text-xs text-slate-500 dark:text-slate-400">Free and open source. Your data stays on this machine.</p>
      </div>
    </div>
  );
}
