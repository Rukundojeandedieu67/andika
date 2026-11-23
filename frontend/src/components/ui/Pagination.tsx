import { ChevronLeft, ChevronRight } from "lucide-react"
import { pageCount } from "@/lib/format"

export function Pagination({
  page,
  pageSize,
  total,
  onPage,
}: {
  page: number
  pageSize: number
  total: number
  onPage: (page: number) => void
}) {
  const pages = pageCount(total, pageSize)
  if (total <= pageSize) return null
  return (
    <nav className="flex items-center justify-between gap-3" aria-label="Pagination">
      <button
        type="button"
        className="inline-flex items-center gap-1 rounded-full border border-line px-3 py-2 text-sm disabled:opacity-40"
        disabled={page <= 1}
        onClick={() => onPage(page - 1)}
      >
        <ChevronLeft size={16} /> Previous
      </button>
      <p className="text-sm text-ink-soft">
        Page {page} of {pages}
      </p>
      <button
        type="button"
        className="inline-flex items-center gap-1 rounded-full border border-line px-3 py-2 text-sm disabled:opacity-40"
        disabled={page >= pages}
        onClick={() => onPage(page + 1)}
      >
        Next <ChevronRight size={16} />
      </button>
    </nav>
  )
}
