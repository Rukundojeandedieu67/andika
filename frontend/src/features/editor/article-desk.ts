import type { PostStatus } from "@/types/api"

export const articleStatuses = ["draft", "published", "archived"] as const

const mediaTypes = new Set(["image/jpeg", "image/png", "image/webp"])
const maxMediaBytes = 10 * 1024 * 1024

export function statusTone(status: string): "neutral" | "brand" | "accent" {
  if (status === "published") return "brand"
  if (status === "archived") return "accent"
  return "neutral"
}

export function countByStatus(items: Array<{ status: PostStatus }>) {
  const counts = { draft: 0, published: 0, archived: 0 }
  for (const item of items) counts[item.status] += 1
  return counts
}

export function mediaFileError(file: { size: number; type: string }): string | null {
  if (!mediaTypes.has(file.type)) return "Upload a JPEG, PNG, or WebP image."
  if (file.size > maxMediaBytes) return "Images must be 10 MB or smaller."
  return null
}

export function wrapSelection(
  value: string,
  start: number,
  end: number,
  before: string,
  after: string,
) {
  const selected = value.slice(start, end) || "text"
  return {
    value: `${value.slice(0, start)}${before}${selected}${after}${value.slice(end)}`,
    cursor: start + before.length + selected.length + after.length,
  }
}
