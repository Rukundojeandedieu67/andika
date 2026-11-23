import { Navigate, Outlet, useLocation } from "react-router"
import { useAuth } from "@/hooks/useAuth"

export function RequireAuth() {
  const { status } = useAuth()
  const location = useLocation()
  if (status === "loading") {
    return (
      <div className="mx-auto max-w-3xl px-4 py-16" aria-busy="true">
        <div className="h-8 w-40 animate-pulse rounded-xl bg-line" />
      </div>
    )
  }
  if (status !== "authenticated") {
    const next = `${location.pathname}${location.search}`
    return <Navigate to={`/login?next=${encodeURIComponent(next)}`} replace />
  }
  return <Outlet />
}

export function RequireAdmin() {
  const { user, status } = useAuth()
  if (status === "loading") return null
  if (!user) return <Navigate to="/login" replace />
  if (user.role !== "administrator" || !user.is_verified) {
    return <Navigate to="/" replace />
  }
  return <Outlet />
}

export function GuestOnly() {
  const { status } = useAuth()
  const location = useLocation()
  if (status === "loading") return null
  if (status === "authenticated") {
    const next = new URLSearchParams(location.search).get("next")
    const target = next && next.startsWith("/") && !next.startsWith("//") ? next : "/"
    return <Navigate to={target} replace />
  }
  return <Outlet />
}
