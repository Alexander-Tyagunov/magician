# nextjs — Data fetching & Server Actions

Version-adaptive. Facts verified against Next.js 16.2.x docs. App Router stable since **13.4**; Route Handlers since **13.2**; Server Actions stable since **14.0**. Actions/`use`/`useActionState`/`useOptimistic` require **React 19**. If on Pages Router or React 18, see fallbacks below.

Detect first: App Router = `app/` dir; Pages Router = `pages/`. Check `package.json` for `next` and `react` versions before choosing APIs.

## Fetch data in Server Components

Server Components (default in `app/`) run only on the server. Fetch directly with `async`/`await` — no `getServerSideProps`.

DO
- Make the component `async`; `await fetch(...)` or query a DB/ORM directly (credentials never reach the client bundle).
- Start independent requests together, then `await Promise.all([...])`.
- Wrap slow/uncached subtrees in `<Suspense fallback={...}>`, or add `loading.js` to stream a whole segment.
- Dedupe cross-tree calls with `import { cache } from 'react'` (per-request memo). Identical `fetch` calls auto-memoize within a render.
- Await dynamic request APIs: `params`, `searchParams`, `cookies()`, `headers()` are **Promises since Next 15** — `const { id } = await params`.

DON'T
- Don't chain `await` sequentially when requests are independent (waterfall).
- Don't assume `fetch` is cached. **Since Next 15 `fetch` defaults to uncached** (no-store) and blocks render. Opt in: `fetch(url, { next: { revalidate: 60 } })`, `{ cache: 'force-cache' }`, or the `'use cache'` directive (stable Cache Components in 16).
- Don't call `cookies()`/`headers()`/uncached fetches in `layout.js` expecting sibling `loading.js` to cover it — it blocks navigation. Wrap in its own `<Suspense>`.

```tsx
// app/blog/page.tsx — parallel + streaming
export default async function Page() {
  const [artist, albums] = await Promise.all([getArtist(id), getAlbums(id)]) // start together
  return <>{artist.name}<Suspense fallback={<Skel/>}><Albums list={albums}/></Suspense></>
}
```

## Fetch data in Client Components

DO
- Fetch a promise in a Server Component, pass it down **unawaited**, resolve with `use(promise)` inside a `'use client'` child wrapped in `<Suspense>` (React 19). Or use SWR / TanStack Query.

DON'T
- Don't put secrets or DB clients in `'use client'` files — they ship to the browser.
- Don't `await` the promise in the Server parent if you want it to stream.

## Mutations — Server Actions (`'use server'`)

A Server Action is a server function invoked via `<form action>`, `<button formAction>`, or a client transition. Stable since **14.0**; requires React 19 form/action features for `useActionState`/`useOptimistic`.

DO
- Add `'use server'` at the top of an async function (inline) or top of a file (all exports become actions).
- Read form fields from the auto-passed `FormData`: `formData.get('name')`. Pass extra args with `.bind(null, id)`.
- Keep a separate `actions.ts` (`'use server'`) so Client Components can `import` and call actions.
- Re-check auth AND authorization (ownership) **inside every action** — it's a public POST endpoint.
- Validate all input (zod). Return only minimal DTOs, never raw DB rows. Revalidate, then `redirect`.

DON'T
- Don't rely on page-level auth gating; render gating is not a security boundary.
- Don't trust a full object from the client (IDOR) — send an ID, re-read the row by owner from the session.
- Don't `Promise.all` actions from the client — Next dispatches them sequentially per client. Parallelize inside one action instead.
- Don't mutate (set cookies / revalidate) during render — only inside actions/route handlers.

```ts
// app/posts/actions.ts
'use server'
import { revalidatePath } from 'next/cache'
import { redirect } from 'next/navigation'
import { auth } from '@/lib/auth'

export async function createPost(formData: FormData) {
  const session = await auth()
  if (!session?.user) throw new Error('Unauthorized') // authn + authz here
  await db.post.create({ data: { title: String(formData.get('title')), authorId: session.user.id } })
  revalidatePath('/posts') // revalidate BEFORE redirect
  redirect('/posts')        // throws — code after never runs
}
```

## Cache invalidation & redirect (all from framework, not React)

- `revalidatePath(path)` / `revalidateTag(tag)` — from `next/cache`. Tag fetches via `fetch(url, { next: { tags: ['posts'] } })`.
- `redirect(url)` / `permanentRedirect(url)` — from `next/navigation`. Throw control-flow; place after revalidation.
- `revalidateTag` (stale-while-revalidate) does **not** force an immediate re-render in the action response; `revalidatePath` does. (Next 16 adds `updateTag`/`refresh` for read-your-own-writes and RSC refetch.)

## Forms & pending/optimistic UI (React 19)

DO
- `const [state, formAction, pending] = useActionState(action, initialState)` — action signature becomes `(prevState, formData)`. Bind `<form action={formAction}>`.
- Use `pending` to disable submit; or `useFormStatus()` (from `react-dom`) in a nested `SubmitButton`.
- `useOptimistic` for instant UI before the action resolves.
- `aria-live` region for validation messages.

DON'T
- Don't use `useFormState` on React 19 — renamed to `useActionState` (moved to `react`). `useFormState` from `react-dom` is the React 18 fallback and is deprecated.
- On React 18: `useFormStatus` returns only `pending` (no `data`/`method`/`action`).

## Route Handlers (`app/api/.../route.ts`)

For webhooks, non-UI responses, BFF endpoints, and client-fetch targets. Introduced **13.2**.

DO
- Export named async funcs per method: `GET`, `POST`, `PUT`, `PATCH`, `DELETE`, `HEAD`, `OPTIONS`.
- Use Web `Request`/`Response`; `Response.json(...)`. Type `request: NextRequest` (from `next/server`) for `request.nextUrl.searchParams`, `request.cookies`.
- `await params` in the 2nd arg context — `params` is a Promise **since Next 15**. Type with `RouteContext<'/users/[id]'>` (globally available, generated).
- Read body with `await request.json()` / `await request.formData()`.

DON'T
- Don't assume `GET` is cached — **since Next 15 GET handlers default to dynamic (uncached)**. Opt in with `export const revalidate = 60` or `export const dynamic = 'force-static'`.
- Don't hand-parse the body with a `bodyParser` config (Pages-era); not needed.

## Do NOT expose secrets to the client

DO
- Keep secrets in env vars; only a server-only Data Access Layer should read `process.env`.
- Mark server-only modules with `import 'server-only'` (build error if imported client-side).
- Sanitize data at the boundary — return minimal DTOs from Server Components/actions.
- Optional defense-in-depth: `experimental.taint: true` + `experimental_taintObjectReference` / `experimental_taintUniqueValue` (React).

DON'T
- Don't prefix a secret with `NEXT_PUBLIC_` — that env var is inlined into the client bundle.
- Don't pass whole DB records/`user` objects as props into `'use client'` components.
- Don't put personal/secret data in URLs or query strings.

## cookies() / headers() (`next/headers`)

- `const store = await cookies()` — **async since Next 15**. `store.get/set/delete`. Setting/deleting in an action auto-re-renders the page.
- `const h = await headers()` — read-only; set response headers by returning a new `Response`.
- `set`/`delete` cookies only inside a Server Action or Route Handler, never during render.

## Pages Router fallbacks (legacy)

- Data: `getServerSideProps` (per-request), `getStaticProps` + `getStaticPaths` (build/ISR via `revalidate`).
- APIs: `pages/api/*.ts` — `export default function handler(req, res)` (Node `req`/`res`, not Web `Request`).
- No Server Actions; mutate via API routes + client fetch. No `use`/`useActionState`.

## Sources

- https://nextjs.org/docs/app/getting-started/fetching-data
- https://nextjs.org/docs/app/guides/forms
- https://nextjs.org/docs/app/guides/server-actions
- https://nextjs.org/docs/app/guides/data-security
- https://nextjs.org/docs/app/api-reference/file-conventions/route
- https://react.dev/reference/react/use
- https://react.dev/reference/react/useActionState
- https://react.dev/reference/react-dom/hooks/useFormStatus
