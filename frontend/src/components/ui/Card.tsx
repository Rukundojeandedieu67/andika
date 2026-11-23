import type { ReactNode } from "react"

export function Card({
  children,
  className = "",
}: {
  children: ReactNode
  className?: string
}) {
  return (
    <article className={`rounded-3xl border border-line bg-paper-raised p-5 shadow-lift ${className}`}>
      {children}
    </article>
  )
}
