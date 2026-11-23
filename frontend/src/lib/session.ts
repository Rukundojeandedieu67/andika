import type { UserPublic } from "@/types/api"

let accessToken: string | null = null
const listeners = new Set<(user: UserPublic | null) => void>()

export function getAccessToken(): string | null {
  return accessToken
}

export function setAccessToken(token: string | null): void {
  accessToken = token
}

export function subscribeAuth(listener: (user: UserPublic | null) => void): () => void {
  listeners.add(listener)
  return () => listeners.delete(listener)
}

export function publishAuth(user: UserPublic | null): void {
  if (!user) accessToken = null
  for (const listener of listeners) listener(user)
}

export function applyAccessSession(token: string, user: UserPublic): void {
  accessToken = token
  publishAuth(user)
}
