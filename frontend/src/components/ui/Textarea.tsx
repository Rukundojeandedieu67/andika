import type { TextareaHTMLAttributes } from "react"

export function Textarea({
  className = "",
  ...props
}: TextareaHTMLAttributes<HTMLTextAreaElement>) {
  return (
    <textarea
      className={`min-h-32 w-full rounded-2xl border border-line bg-paper-raised px-3 py-3 text-ink placeholder:text-ink-soft/70 ${className}`}
      {...props}
    />
  )
}
