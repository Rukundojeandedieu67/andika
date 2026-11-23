export function formatDate(value: string | null | undefined): string {
  if (!value) return "—"
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return "—"
  return new Intl.DateTimeFormat(undefined, {
    year: "numeric",
    month: "short",
    day: "numeric",
  }).format(date)
}

export function formatDateTime(value: string | null | undefined): string {
  if (!value) return "—"
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return "—"
  return new Intl.DateTimeFormat(undefined, {
    year: "numeric",
    month: "short",
    day: "numeric",
    hour: "numeric",
    minute: "2-digit",
    timeZone: "UTC",
    timeZoneName: "short",
  }).format(date)
}

export function formatNumber(value: number): string {
  return new Intl.NumberFormat().format(value)
}

export function formatRate(value: number): string {
  return `${new Intl.NumberFormat(undefined, { maximumFractionDigits: 2 }).format(value)}%`
}

export function displayName(person: { full_name: string | null; username: string }): string {
  return person.full_name?.trim() || person.username
}

export function pageCount(total: number, pageSize: number): number {
  return Math.max(1, Math.ceil(total / pageSize))
}

export function readingLabel(minutes: number): string {
  if (minutes <= 0) return "Short read"
  return `${minutes} min read`
}
