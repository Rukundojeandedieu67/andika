import { NavLink, Outlet } from "react-router"

const items = [
  { to: "/admin", label: "Overview", end: true },
  { to: "/admin/analytics", label: "Analytics" },
  { to: "/admin/articles", label: "Articles" },
  { to: "/admin/categories", label: "Categories" },
  { to: "/admin/tags", label: "Tags" },
  { to: "/admin/comments", label: "Comments" },
  { to: "/admin/reports", label: "Reports" },
  { to: "/admin/media", label: "Media" },
  { to: "/admin/search", label: "Search" },
  { to: "/admin/delivery", label: "Delivery" },
]

export function AdminLayout() {
  return (
    <div className="mx-auto grid max-w-6xl gap-6 px-4 py-8 lg:grid-cols-[220px_1fr]">
      <aside>
        <p className="text-xs tracking-[0.18em] text-accent uppercase">Administration</p>
        <h1 className="mt-2 font-display text-3xl">Platform</h1>
        <nav className="mt-6 grid gap-1" aria-label="Administration">
          {items.map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              end={item.end}
              className={({ isActive }) =>
                `rounded-xl px-3 py-2 text-sm ${isActive ? "bg-ink text-paper" : "hover:bg-line/60"}`
              }
            >
              {item.label}
            </NavLink>
          ))}
        </nav>
      </aside>
      <div>
        <Outlet />
      </div>
    </div>
  )
}
