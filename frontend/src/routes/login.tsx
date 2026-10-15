import { Link, createFileRoute, useNavigate } from "@tanstack/react-router";
import { useState } from "react";
import { ChevronRight, ShieldAlert } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { DEMO_USERS, homeFor, signIn } from "@/lib/auth";

export const Route = createFileRoute("/login")({
  validateSearch: (s: Record<string, unknown>): { redirect?: string | undefined } => ({ redirect: typeof s["redirect"] === "string" ? (s["redirect"] as string) : undefined }),
  head: () => ({
    meta: [
      { title: "Sign in — SiteGuard" },
      { name: "description", content: "Sign in to the SiteGuard safety dashboard or use a one-click demo account." },
      { property: "og:title", content: "Sign in — SiteGuard" },
      { property: "og:description", content: "Sign in or use a one-click demo account." },
    ],
  }),
  component: LoginPage,
});

function LoginPage() {
  const { redirect } = Route.useSearch();
  const navigate = useNavigate();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);

  const go = (e: string, p: string) => {
    try {
      const u = signIn(e, p);
      const target = redirect && redirect.startsWith("/") && !redirect.startsWith("//") ? redirect : homeFor(u.role);
      navigate({ to: target, replace: true });
    } catch (err) {
      setError((err as Error).message);
    }
  };

  return (
    <div className="min-h-screen">
      <div className="hazard-stripe h-1.5" aria-hidden />
      <div className="mx-auto flex max-w-md flex-col gap-6 px-5 py-12">
        <Link to="/" className="flex items-center gap-2 text-xl font-bold">
          <ShieldAlert className="size-6 text-primary" aria-hidden /> SiteGuard
        </Link>

        <section className="panel p-5">
          <h1 className="text-2xl font-bold">Quick demo login</h1>
          <p className="mt-1 text-sm text-muted-foreground">One click, no password needed.</p>
          <div className="mt-4 grid gap-2">
            {DEMO_USERS.map((u) => (
              <button
                key={u.email}
                onClick={() => go(u.email, u.password)}
                className="flex items-center gap-3 rounded-sm border bg-background p-3 text-left transition-colors hover:border-primary focus-visible:border-primary focus-visible:outline-none"
              >
                <span className="grid size-10 place-items-center rounded-sm bg-primary font-mono font-bold text-primary-foreground">
                  {u.role[0]}
                </span>
                <span className="flex-1">
                  <span className="block font-semibold">{u.name}</span>
                  <span className="block text-sm text-muted-foreground">{u.blurb}</span>
                </span>
                <ChevronRight className="size-5 text-muted-foreground" aria-hidden />
              </button>
            ))}
          </div>
        </section>

        <form
          className="panel space-y-4 p-5"
          onSubmit={(e) => {
            e.preventDefault();
            go(email, password);
          }}
        >
          <h2 className="label-caps">Or sign in with email</h2>
          <div className="space-y-1.5">
            <Label htmlFor="email">Email</Label>
            <Input id="email" type="email" autoComplete="email" value={email} onChange={(e) => setEmail(e.target.value)} required />
          </div>
          <div className="space-y-1.5">
            <Label htmlFor="password">Password</Label>
            <Input id="password" type="password" autoComplete="current-password" value={password} onChange={(e) => setPassword(e.target.value)} required />
          </div>
          {error && <p role="alert" className="text-sm font-semibold text-destructive">{error}</p>}
          <Button type="submit" className="w-full font-bold">Sign in</Button>
          <p className="font-mono text-xs text-muted-foreground">Demo password for all accounts: demo1234</p>
        </form>
      </div>
    </div>
  );
}
