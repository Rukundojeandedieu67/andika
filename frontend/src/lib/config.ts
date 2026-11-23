export const apiBaseUrl =
  import.meta.env.VITE_API_BASE_URL?.replace(/\/$/, "") || "/api/v1"

export function apiOrigin(): string {
  try {
    return new URL(apiBaseUrl).origin
  } catch {
    return "http://127.0.0.1:8000"
  }
}
