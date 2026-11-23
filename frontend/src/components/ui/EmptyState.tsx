import type { ReactNode } from "react"

export function EmptyState({
  title,
  body,
  action,
}: {
  title: string
  body: string
  action?: ReactNode
}) {
  return (
    <div className="rounded-3xl border border-dashed border-line bg-paper-raised px-6 py-12 text-center">
      <h2 className="font-display text-2xl">{title}</h2>
      <p className="mx-auto mt-2 max-w-lg text-ink-soft">{body}</p>
      {action ? <div className="mt-5">{action}</div> : null}
    </div>
  )
}
