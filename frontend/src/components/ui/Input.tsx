import type { InputHTMLAttributes } from "react"

export function Input({ className = "", ...props }: InputHTMLAttributes<HTMLInputElement>) {
  return (
    <input
      className={`h-11 w-full rounded-2xl border border-line bg-paper-raised px-3 text-ink placeholder:text-ink-soft/70 ${className}`}
      {...props}
    />
  )
}
