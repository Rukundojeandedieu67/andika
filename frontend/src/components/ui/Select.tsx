import type { SelectHTMLAttributes } from "react"

export function Select({ className = "", ...props }: SelectHTMLAttributes<HTMLSelectElement>) {
  return (
    <select
      className={`h-11 w-full rounded-2xl border border-line bg-paper-raised px-3 text-ink ${className}`}
      {...props}
    />
  )
}
