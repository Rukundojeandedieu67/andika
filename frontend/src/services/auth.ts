import { api, refreshSession } from "@/lib/api"
import { applyAccessSession, publishAuth } from "@/lib/session"
import type { AccessTokenResponse, MessageResponse, UserPublic } from "@/types/api"

export async function registerAccount(payload: {
  username: string
  email: string
  password: string
  password_confirm: string
  full_name?: string | null
}): Promise<UserPublic> {
  const { data } = await api.post<UserPublic>("/auth/register", payload)
  return data
}

export async function loginAccount(email: string, password: string): Promise<UserPublic> {
  const { data } = await api.post<AccessTokenResponse>("/auth/login", { email, password })
  applyAccessSession(data.access_token, data.user)
  return data.user
}

export async function logoutAccount(): Promise<void> {
  try {
    await api.post("/auth/logout", {})
  } finally {
    publishAuth(null)
  }
}

export function restoreSession() {
  return refreshSession()
}

export async function forgotPassword(email: string): Promise<MessageResponse> {
  const { data } = await api.post<MessageResponse>("/auth/forgot-password", { email })
  return data
}

export async function resetPassword(token: string, password: string): Promise<MessageResponse> {
  const { data } = await api.post<MessageResponse>("/auth/reset-password", { token, password })
  return data
}

export async function verifyEmail(token: string): Promise<UserPublic> {
  const { data } = await api.post<UserPublic>("/auth/verify-email", { token })
  return data
}

export async function resendVerification(email: string): Promise<MessageResponse> {
  const { data } = await api.post<MessageResponse>("/auth/resend-verification", { email })
  return data
}

export async function currentProfile(): Promise<UserPublic> {
  const { data } = await api.get<UserPublic>("/users/me")
  return data
}

export async function updateProfile(payload: {
  username?: string
  full_name?: string | null
  bio?: string | null
  avatar_url?: string | null
}): Promise<UserPublic> {
  const { data } = await api.patch<UserPublic>("/users/me", payload)
  return data
}
