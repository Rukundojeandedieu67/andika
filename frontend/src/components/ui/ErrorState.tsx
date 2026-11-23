import { toApiError } from "@/lib/errors"
import { Button } from "@/components/ui/Button"

export function ErrorState({
  error,
  onRetry,
}: {
  error: unknown
  onRetry?: () => void
}) {
  const apiError = toApiError(error)
  return (
    <div role="alert" className="rounded-3xl border border-danger/30 bg-paper-raised px-6 py-10">
      <h2 className="font-display text-2xl">This could not be loaded</h2>
      <p className="mt-2 text-ink-soft">{apiError.message}</p>
      {onRetry ? (
        <Button className="mt-5" variant="secondary" onClick={onRetry}>
          Try again
        </Button>
      ) : null}
    </div>
  )
}
