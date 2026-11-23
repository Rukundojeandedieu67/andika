import type { ReactNode } from "react"
import { isRouteErrorResponse, useRouteError } from "react-router"
import { Link } from "react-router"

export function RouteError() {
  const error = useRouteError()
  const message = isRouteErrorResponse(error)
    ? error.statusText || "This page could not be opened."
    : "This page could not be opened."
  return (
    <main className="mx-auto grid min-h-[70vh] max-w-xl place-items-center px-6 text-center">
      <div>
        <p className="text-sm tracking-[0.2em] text-accent uppercase">ANDIKA</p>
        <h1 className="mt-3 font-display text-4xl">Something interrupted this page</h1>
        <p className="mt-3 text-ink-soft">{message}</p>
        <Link to="/" className="mt-6 inline-flex rounded-full bg-brand px-4 py-2 text-paper-raised">
          Return home
        </Link>
      </div>
    </main>
  )
}

export function NotFoundPage() {
  return (
    <main className="mx-auto grid min-h-[70vh] max-w-xl place-items-center px-6 text-center">
      <div>
        <p className="text-sm tracking-[0.2em] text-accent uppercase">404</p>
        <h1 className="mt-3 font-display text-4xl">This page is not on ANDIKA</h1>
        <p className="mt-3 text-ink-soft">The address may have changed, or the page was never published.</p>
        <Link to="/" className="mt-6 inline-flex rounded-full bg-brand px-4 py-2 text-paper-raised">
          Read the latest
        </Link>
      </div>
    </main>
  )
}

export function QueryView({
  isLoading,
  error,
  isEmpty,
  empty,
  onRetry,
  children,
}: {
  isLoading: boolean
  error: unknown
  isEmpty?: boolean
  empty?: ReactNode
  onRetry?: () => void
  children: ReactNode
}) {
  if (isLoading) {
    return (
      <div className="grid gap-4" aria-busy="true" aria-live="polite">
        <div className="h-8 w-48 animate-pulse rounded-xl bg-line" />
        <div className="h-40 animate-pulse rounded-3xl bg-line/80" />
      </div>
    )
  }
  if (error) {
    return (
      <div role="alert" className="rounded-3xl border border-danger/30 bg-paper-raised p-6">
        <p>{error instanceof Error ? error.message : "This could not be loaded."}</p>
        {onRetry ? (
          <button type="button" className="mt-4 underline" onClick={onRetry}>
            Try again
          </button>
        ) : null}
      </div>
    )
  }
  if (isEmpty) return <>{empty}</>
  return <>{children}</>
}
