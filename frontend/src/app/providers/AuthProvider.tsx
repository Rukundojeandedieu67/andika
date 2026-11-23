import { useEffect, useMemo, useRef, useState, type ReactNode } from "react"
import { useQueryClient } from "@tanstack/react-query"
import { AuthContext, type AuthContextValue } from "@/features/auth/auth-context"
import { loginAccount, logoutAccount, restoreSession, updateProfile } from "@/services/auth"
import { getAccessToken, subscribeAuth } from "@/lib/session"
import type { UserPublic } from "@/types/api"

export function AuthProvider({ children }: { children: ReactNode }) {
  const queryClient = useQueryClient()
  const [user, setUser] = useState<UserPublic | null>(null)
  const [status, setStatus] = useState<AuthContextValue["status"]>("loading")
  const epoch = useRef(0)
  const userRef = useRef<UserPublic | null>(null)

  useEffect(() => {
    const ticket = ++epoch.current
    restoreSession().then((session) => {
      if (ticket !== epoch.current) return
      setUser(session?.user ?? null)
      setStatus(session ? "authenticated" : "anonymous")
    })
  }, [])

  useEffect(() => {
    return subscribeAuth((next) => {
      if (!next && userRef.current) queryClient.clear()
      userRef.current = next
      setUser(next)
      setStatus(next ? "authenticated" : "anonymous")
    })
  }, [queryClient])

  const value = useMemo<AuthContextValue>(
    () => ({
      user,
      status,
      login: async (email, password) => {
        epoch.current += 1
        const next = await loginAccount(email, password)
        setUser(next)
        setStatus("authenticated")
        return next
      },
      logout: async () => {
        epoch.current += 1
        await logoutAccount()
        setUser(null)
        setStatus("anonymous")
        queryClient.clear()
      },
      setUser,
      saveProfile: async (payload) => {
        const next = await updateProfile(payload)
        if (getAccessToken()) setUser(next)
        return next
      },
    }),
    [queryClient, status, user],
  )

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}
