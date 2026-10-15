<!-- LOVABLE:BEGIN -->
> [!IMPORTANT]
> This project is connected to [Lovable](https://lovable.dev). Avoid rewriting
> published git history — force pushing, or rebasing/amending/squashing commits
> that are already pushed — as it rewrites history on Lovable's side and the
> user will likely lose their project history.
>
> Commits you push to the connected branch sync back to Lovable and show up in
> the editor, so keep the branch in a working state.
<!-- LOVABLE:END -->

## Project rules
- SiteGuard is a frontend-only dashboard over an external FastAPI backend (VITE_API_URL); all data comes from it, no mock data — the plan forbids demo data.
- Live updates flow through `src/lib/live.tsx` (SSE) writing into the TanStack Query cache; no global state library.
- Sign-in is a demo-only browser session (`src/lib/auth.ts`); dashboard pages live under `src/routes/_authenticated/` (ssr: false) — no real auth provider was requested.
