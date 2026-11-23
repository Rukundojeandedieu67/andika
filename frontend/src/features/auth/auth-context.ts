import { createContext } from "react"
import type { UserPublic } from "@/types/api"

export interface AuthContextValue {
  user: UserPublic | null
  status: "loading" | "anonymous" | "authenticated"
  login: (email: string, password: string) => Promise<UserPublic>
  logout: () => Promise<void>
  setUser: (user: UserPublic) => void
  saveProfile: (payload: {
    username?: string
    full_name?: string | null
    bio?: string | null
    avatar_url?: string | null
  }) => Promise<UserPublic>
}

export const AuthContext = createContext<AuthContextValue | null>(null)
