import type { ReactNode } from "react"

export function Field({
  label,
  hint,
  error,
  children,
  htmlFor,
}: {
  label: string
  hint?: string
  error?: string
  htmlFor?: string
  children: ReactNode
}) {
  return (
    <div className="grid gap-1.5 text-sm">
      <label className="font-medium" htmlFor={htmlFor}>
        {label}
      </label>
      {children}
      {error ? (
        <span className="text-danger" role="alert">
          {error}
        </span>
      ) : null}
      {hint && !error ? (
        <span className="text-ink-soft" id={htmlFor ? `${htmlFor}-hint` : undefined}>
          {hint}
        </span>
      ) : null}
    </div>
  )
}
