import { BarChart3, FileText, Images, LayoutDashboard, LogOut, MessagesSquare, Moon, Newspaper, Settings, Sun } from "lucide-react"
import { NavLink, Outlet, useNavigate } from "react-router"
import { useAuth } from "@/hooks/useAuth"
import { useTheme } from "@/hooks/useTheme"
import { displayName } from "@/lib/format"

const items = [
  { to: "/workspace", label: "Dashboard", icon: LayoutDashboard, end: true },
  { to: "/workspace/articles", label: "Articles", icon: FileText },
  { to: "/workspace/media", label: "Media", icon: Images },
  { to: "/workspace/analytics", label: "Analytics", icon: BarChart3 },
  { to: "/workspace/messages", label: "Messages", icon: MessagesSquare },
  { to: "/workspace/publications", label: "Publications", icon: Newspaper },
]

export function WorkspaceLayout() {
  const { user, logout } = useAuth()
  const { theme, toggle } = useTheme()
  const navigate = useNavigate()
  return (
    <div className="min-h-screen bg-paper lg:grid lg:grid-cols-[240px_1fr]">
      <aside className="flex flex-col bg-forest text-[#f4efe6] lg:min-h-screen">
        <div className="px-5 py-6">
          <NavLink to="/" className="font-display text-2xl tracking-tight">ANDIKA</NavLink>
          <p className="text-xs tracking-[0.16em] text-white/60 uppercase">Workspace</p>
        </div>
        <nav className="flex gap-1 overflow-x-auto px-3 lg:grid lg:overflow-visible" aria-label="Workspace">
          {items.map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              end={item.end}
              className={({ isActive }) =>
                `flex shrink-0 items-center gap-3 rounded-xl px-3 py-2.5 text-sm ${isActive ? "bg-white/12 text-white" : "text-white/75 hover:bg-white/8 hover:text-white"}`
              }
            >
              <item.icon size={18} />
              {item.label}
            </NavLink>
          ))}
        </nav>
        <div className="mt-auto grid gap-1 px-3 py-4">
          <button type="button" className="flex items-center gap-3 rounded-xl px-3 py-2 text-sm text-white/75" onClick={toggle}>
            {theme === "dark" ? <Sun size={18} /> : <Moon size={18} />}
            {theme === "dark" ? "Light mode" : "Dark mode"}
          </button>
          <button type="button" className="flex items-center gap-3 rounded-xl px-3 py-2 text-sm text-white/75" onClick={() => navigate("/account")}>
            <Settings size={18} />
            {user ? displayName(user) : "Account"}
          </button>
          {user?.role === "administrator" ? (
            <button type="button" className="rounded-xl px-3 py-2 text-left text-sm text-white/75" onClick={() => navigate("/admin")}>
              Administration
            </button>
          ) : null}
          <button type="button" className="flex items-center gap-3 rounded-xl px-3 py-2 text-sm text-white/75" onClick={() => void logout()}>
            <LogOut size={18} />
            Sign out
          </button>
        </div>
      </aside>
      <div className="px-4 py-8 lg:px-8">
        <Outlet />
      </div>
    </div>
  )
}
