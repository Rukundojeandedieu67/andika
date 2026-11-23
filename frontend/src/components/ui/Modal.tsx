import type { ReactNode } from "react"
import { useEffect } from "react"
import { X } from "lucide-react"

export function Modal({
  title,
  open,
  onClose,
  children,
}: {
  title: string
  open: boolean
  onClose: () => void
  children: ReactNode
}) {
  useEffect(() => {
    if (!open) return
    const onKey = (event: KeyboardEvent) => {
      if (event.key === "Escape") onClose()
    }
    window.addEventListener("keydown", onKey)
    return () => window.removeEventListener("keydown", onKey)
  }, [open, onClose])

  if (!open) return null
  return (
    <div className="fixed inset-0 z-50 grid place-items-center bg-ink/40 p-4" role="presentation">
      <div
        role="dialog"
        aria-modal="true"
        aria-labelledby="dialog-title"
        className="max-h-[90vh] w-full max-w-lg overflow-auto rounded-3xl bg-paper-raised p-5 shadow-lift"
      >
        <div className="mb-4 flex items-start justify-between gap-4">
          <h2 id="dialog-title" className="font-display text-2xl">
            {title}
          </h2>
          <button type="button" aria-label="Close" onClick={onClose} className="rounded-full p-2">
            <X size={18} />
          </button>
        </div>
        {children}
      </div>
    </div>
  )
}
