import { Outlet, createFileRoute, redirect } from "@tanstack/react-router";
import { getUser } from "@/lib/auth";
import { LiveStreamProvider } from "@/lib/live";
import { Shell } from "@/components/sg/Shell";

export const Route = createFileRoute("/_authenticated")({
  ssr: false,
  beforeLoad: ({ location }) => {
    if (!getUser()) throw redirect({ to: "/login", search: { redirect: location.href } });
  },
  component: AppLayout,
});

function AppLayout() {
  return (
    <LiveStreamProvider>
      <Shell>
        <Outlet />
      </Shell>
    </LiveStreamProvider>
  );
}
