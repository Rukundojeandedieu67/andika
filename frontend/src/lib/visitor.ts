const STORAGE_KEY = "andika_visitor_id"
const VISITOR_PATTERN = /^[A-Za-z0-9_-]{8,80}$/

export function visitorId(): string {
  const existing = localStorage.getItem(STORAGE_KEY)
  if (existing && VISITOR_PATTERN.test(existing)) return existing
  const bytes = new Uint8Array(16)
  crypto.getRandomValues(bytes)
  const created = Array.from(bytes, (byte) => byte.toString(16).padStart(2, "0")).join("")
  localStorage.setItem(STORAGE_KEY, created)
  return created
}
