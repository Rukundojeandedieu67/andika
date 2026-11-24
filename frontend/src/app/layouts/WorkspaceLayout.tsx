import { NavLink, Outlet } from "react-router"
import { useAuth } from "@/hooks/useAuth"

const items = [
  { to: "/workspace", label: "Overview", end: true },
  { to: "/workspace/articles", label: "Articles" },
  { to: "/workspace/media", label: "Media" },
  { to: "/workspace/analytics", label: "Analytics" },
  { to: "/workspace/publications", label: "Publications" },
  { to: "/workspace/comments", label: "Comments" },
]

export function WorkspaceLayout() {
  const { user } = useAuth()
  return (
    <div className="mx-auto grid max-w-6xl gap-6 px-4 py-8 lg:grid-cols-[220px_1fr]">
      <aside>
        <p className="text-xs tracking-[0.18em] text-accent uppercase">Workspace</p>
        <h1 className="mt-2 font-display text-3xl">Desk</h1>
        <nav className="mt-4 flex gap-1 overflow-x-auto lg:mt-6 lg:grid" aria-label="Workspace">
          {items.map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              end={item.end}
              className={({ isActive }) =>
                `shrink-0 rounded-xl px-3 py-2 text-sm focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-brand ${isActive ? "bg-brand text-paper-raised" : "hover:bg-line/60"}`
              }
            >
              {item.label}
            </NavLink>
          ))}
          {user?.role === "administrator" ? (
            <NavLink to="/admin" className="rounded-xl px-3 py-2 text-sm hover:bg-line/60">
              Administration
            </NavLink>
          ) : null}
        </nav>
      </aside>
      <div>
        <Outlet />
      </div>
    </div>
  )
}
