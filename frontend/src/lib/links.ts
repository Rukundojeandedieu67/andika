export function notificationHref(
  actionUrl: string | null,
  metadata: Record<string, unknown>,
): string | null {
  const slug = typeof metadata.article_slug === "string" ? metadata.article_slug : null
  if (slug) return `/articles/${slug}`
  if (!actionUrl) return null
  const article = actionUrl.match(/^\/api\/v1\/posts\/([a-z0-9-]+)$/)
  if (article?.[1] && article[1] !== "mine" && article[1] !== "admin") {
    return `/articles/${article[1]}`
  }
  const publication = actionUrl.match(/^\/api\/v1\/publications\/([0-9a-f-]{36})\/members$/i)
  if (publication?.[1]) return `/workspace/publications/${publication[1]}`
  return null
}

export function hashParam(name: string): string | null {
  const raw = window.location.hash.startsWith("#")
    ? window.location.hash.slice(1)
    : window.location.hash
  const value = new URLSearchParams(raw).get(name)
  return value && value.trim() ? value.trim() : null
}

export function clearHash(): void {
  window.history.replaceState(null, "", `${window.location.pathname}${window.location.search}`)
}
