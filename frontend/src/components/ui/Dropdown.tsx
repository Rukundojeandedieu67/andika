import type { ReactNode } from "react"
import { useEffect, useId, useRef, useState } from "react"

export function Dropdown({
  label,
  children,
}: {
  label: ReactNode
  children: ReactNode
}) {
  const [open, setOpen] = useState(false)
  const ref = useRef<HTMLDivElement>(null)
  const menuId = useId()

  useEffect(() => {
    if (!open) return
    const close = (event: MouseEvent) => {
      if (!ref.current?.contains(event.target as Node)) setOpen(false)
    }
    document.addEventListener("mousedown", close)
    return () => document.removeEventListener("mousedown", close)
  }, [open])

  return (
    <div className="relative" ref={ref}>
      <button
        type="button"
        aria-expanded={open}
        aria-controls={menuId}
        onClick={() => setOpen((value) => !value)}
        className="inline-flex items-center gap-2 rounded-full px-2 py-1 hover:bg-line/50"
      >
        {label}
      </button>
      {open ? (
        <div
          id={menuId}
          className="absolute right-0 z-30 mt-2 min-w-52 rounded-2xl border border-line bg-paper-raised p-2 shadow-lift"
          onClick={() => setOpen(false)}
        >
          {children}
        </div>
      ) : null}
    </div>
  )
}

export function DropdownItem({
  children,
  onClick,
}: {
  children: ReactNode
  onClick?: () => void
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      className="block w-full rounded-xl px-3 py-2 text-left text-sm hover:bg-line/60"
    >
      {children}
    </button>
  )
}
