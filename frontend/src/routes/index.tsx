import { Link, createFileRoute } from "@tanstack/react-router";
import { Activity, BellRing, Cpu, ShieldAlert } from "lucide-react";
import hero from "@/assets/landing-hero.jpg";
import { Button } from "@/components/ui/button";
import { useUser } from "@/lib/auth";

export const Route = createFileRoute("/")({
  head: () => ({
    meta: [
      { title: "SiteGuard — Edge AI safety monitoring" },
      { name: "description", content: "SiteGuard turns PipeGen edge-vision detections into live, actionable safety incidents." },
      { property: "og:title", content: "SiteGuard — Edge AI safety monitoring" },
      { property: "og:description", content: "Live, actionable safety incidents from edge-vision pipelines." },
    ],
  }),
  component: Landing,
});

const FEATURES = [
  { Icon: Activity, title: "Live incident feed", text: "Zone intrusions, PPE violations and loitering stream in within a second." },
  { Icon: BellRing, title: "Critical alerts", text: "Full-width banner for critical events, acknowledged with one click." },
  { Icon: Cpu, title: "Edge evidence", text: "TensorRT speed report and FP32 / FP16 / INT8 trade-offs, side by side." },
];

function Landing() {
  const user = useUser();
  return (
    <div className="min-h-screen">
      <div className="hazard-stripe h-1.5" aria-hidden />
      <header className="mx-auto flex max-w-6xl items-center justify-between px-5 py-4">
        <span className="flex items-center gap-2 text-xl font-bold">
          <ShieldAlert className="size-6 text-primary" aria-hidden /> SiteGuard
        </span>
        <Button asChild variant={user ? "default" : "outline"}>
          {user ? <Link to="/live">Open dashboard</Link> : <Link to="/login" search={{}}>Sign in</Link>}
        </Button>
      </header>

      <section className="mx-auto grid max-w-6xl items-center gap-10 px-5 py-10 lg:grid-cols-2 lg:py-16">
        <div>
          <p className="label-caps text-primary">Safety operations · Edge AI</p>
          <h1 className="mt-3 text-5xl font-bold leading-[1.05] tracking-tight sm:text-6xl">
            See every violation <span className="text-primary">the moment it happens.</span>
          </h1>
          <p className="mt-5 max-w-lg text-lg text-muted-foreground">
            SiteGuard turns the PipeGen vision pipeline into a control-room dashboard your site team can act on.
          </p>
          <div className="mt-8 flex flex-wrap gap-3">
            <Button asChild size="lg" className="font-bold">
              <Link to="/login" search={{}}>Try the demo</Link>
            </Button>
            <Button asChild size="lg" variant="outline">
              <Link to="/pipeline">View pipeline evidence</Link>
            </Button>
          </div>
        </div>
        <div className="panel overflow-hidden">
          <img src={hero} alt="Site camera view with detected workers and restricted zones" width={1600} height={912} className="w-full" />
        </div>
      </section>

      <section className="mx-auto grid max-w-6xl gap-4 px-5 pb-16 sm:grid-cols-3">
        {FEATURES.map(({ Icon, title, text }) => (
          <div key={title} className="panel p-5">
            <Icon className="size-6 text-primary" aria-hidden />
            <h2 className="mt-3 text-lg font-bold">{title}</h2>
            <p className="mt-1 text-muted-foreground">{text}</p>
          </div>
        ))}
      </section>
    </div>
  );
}
