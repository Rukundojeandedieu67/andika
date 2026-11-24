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
    <div className="min-h-screen bg-paper lg:grid lg:grid-cols-[240px_1fr]">
      <aside className="bg-forest px-4 py-6 text-[#f4efe6]">
        <NavLink to="/" className="font-display text-2xl">ANDIKA</NavLink>
        <p className="text-xs tracking-[0.16em] text-white/60 uppercase">Administration</p>
        <nav className="mt-6 grid gap-1" aria-label="Administration">
          {items.map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              end={item.end}
              className={({ isActive }) =>
                `rounded-xl px-3 py-2 text-sm ${isActive ? "bg-white/15 text-white" : "text-white/75 hover:bg-white/10"}`
              }
            >
              {item.label}
            </NavLink>
          ))}
        </nav>
      </aside>
      <div className="px-4 py-8 lg:px-8">
        <Outlet />
      </div>
    </div>
  )
}
