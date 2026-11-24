import { forwardRef, type TextareaHTMLAttributes } from "react"

export const Textarea = forwardRef<HTMLTextAreaElement, TextareaHTMLAttributes<HTMLTextAreaElement>>(
  function Textarea({ className = "", ...props }, ref) {
    return (
      <textarea
        ref={ref}
        className={`min-h-32 w-full rounded-2xl border border-line bg-paper-raised px-3 py-3 text-ink placeholder:text-ink-soft/70 ${className}`}
        {...props}
      />
    )
  },
)
