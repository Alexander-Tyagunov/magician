Common AI mistakes: mixing App Router and Pages Router patterns; forgetting "use client" on components using hooks; fetching in useEffect when a Server Component fetch suffices; using next/head instead of the Metadata API in App Router.
Commands: dev: `npm run dev`, build: `npm run build`, lint: `npm run lint`.
Gotchas: App Router is default since Next.js 13; `fetch` in Server Components is extended with `cache` option; route handlers live in `app/api/[route]/route.ts`.
