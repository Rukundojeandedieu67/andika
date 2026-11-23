import { apiBaseUrl, apiOrigin } from "@/lib/config"

export function resolveMediaUrl(url: string | null | undefined): string | null {
  if (!url) return null
  if (/^https?:\/\//i.test(url)) return url
  if (url.startsWith("/")) {
    if (apiBaseUrl.startsWith("/")) return url
    return `${apiOrigin()}${url}`
  }
  return url
}

export function preferredVariant(
  variants: Array<{ kind: string; url: string }> | undefined,
  preference: string[] = ["large", "medium", "original", "thumbnail"],
): string | null {
  if (!variants?.length) return null
  for (const kind of preference) {
    const match = variants.find((variant) => variant.kind === kind)
    if (match) return resolveMediaUrl(match.url)
  }
  return resolveMediaUrl(variants[0]?.url)
}
