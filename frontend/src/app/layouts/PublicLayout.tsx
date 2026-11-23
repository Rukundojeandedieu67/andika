import { useState, type FormEvent } from "react"
import { Bell, Menu, Moon, Search, Sun, X } from "lucide-react"
import { Link, NavLink, Outlet, useNavigate } from "react-router"
import { useQuery } from "@tanstack/react-query"
import { useAuth } from "@/hooks/useAuth"
import { useTheme } from "@/hooks/useTheme"
import { Avatar } from "@/components/ui/Avatar"
import { Dropdown, DropdownItem } from "@/components/ui/Dropdown"
import { displayName } from "@/lib/format"
import { unreadCount } from "@/services/community"

const links = [
  { to: "/articles", label: "Articles" },
  { to: "/discover/trending", label: "Trending" },
  { to: "/publications", label: "Publications" },
  { to: "/categories", label: "Categories" },
  { to: "/authors", label: "Authors" },
]

export function PublicLayout() {
  const { user, status, logout } = useAuth()
  const { theme, toggle } = useTheme()
  const navigate = useNavigate()
  const [query, setQuery] = useState("")
  const [open, setOpen] = useState(false)
  const unread = useQuery({
    queryKey: ["notifications", "unread"],
    queryFn: unreadCount,
    enabled: status === "authenticated",
    refetchInterval: 60_000,
  })

  function search(event: FormEvent) {
    event.preventDefault()
    const value = query.trim()
    navigate(value ? `/search?q=${encodeURIComponent(value)}` : "/search")
    setOpen(false)
  }

  return (
    <div className="min-h-screen">
      <header className="sticky top-0 z-40 border-b border-line bg-[var(--header)] backdrop-blur">
        <div className="mx-auto flex max-w-6xl items-center gap-4 px-4 py-3">
          <button
            type="button"
            className="rounded-full p-2 md:hidden"
            aria-label="Open menu"
            onClick={() => setOpen(true)}
          >
            <Menu size={20} />
          </button>
          <Link to="/" className="font-display text-2xl tracking-tight">
            ANDIKA
          </Link>
          <nav className="hidden items-center gap-4 text-sm md:flex" aria-label="Primary">
            {links.map((link) => (
              <NavLink
                key={link.to}
                to={link.to}
                className={({ isActive }) => (isActive ? "text-brand" : "text-ink-soft hover:text-ink")}
              >
                {link.label}
              </NavLink>
            ))}
          </nav>
          <form onSubmit={search} className="ml-auto hidden min-w-56 items-center md:flex" role="search">
            <label className="relative w-full">
              <span className="sr-only">Search ANDIKA</span>
              <Search size={16} className="absolute top-3 left-3 text-ink-soft" />
              <input
                value={query}
                onChange={(event) => setQuery(event.target.value)}
                placeholder="Search stories"
                className="h-10 w-full rounded-full border border-line bg-paper-raised pr-3 pl-9 text-sm"
              />
            </label>
          </form>
          <button type="button" className="rounded-full p-2" onClick={toggle} aria-label="Toggle color theme">
            {theme === "dark" ? <Sun size={18} /> : <Moon size={18} />}
          </button>
          {status === "authenticated" && user ? (
            <div className="flex items-center gap-2">
              <Link to="/notifications" className="relative rounded-full p-2" aria-label="Notifications">
                <Bell size={18} />
                {unread.data ? (
                  <span className="absolute top-1 right-1 grid h-4 min-w-4 place-items-center rounded-full bg-accent px-1 text-[10px] text-white">
                    {unread.data}
                  </span>
                ) : null}
              </Link>
              <Dropdown
                label={
                  <span className="inline-flex items-center gap-2">
                    <Avatar name={displayName(user)} src={user.avatar_url} size={32} />
                    <span className="hidden text-sm sm:inline">{displayName(user)}</span>
                  </span>
                }
              >
                <DropdownItem onClick={() => navigate("/account")}>Profile</DropdownItem>
                <DropdownItem onClick={() => navigate("/workspace")}>Workspace</DropdownItem>
                {user.role === "administrator" ? (
                  <DropdownItem onClick={() => navigate("/admin")}>Administration</DropdownItem>
                ) : null}
                <DropdownItem
                  onClick={() => {
                    void logout()
                  }}
                >
                  Sign out
                </DropdownItem>
              </Dropdown>
            </div>
          ) : status === "loading" ? (
            <span className="text-sm text-ink-soft">…</span>
          ) : (
            <div className="flex items-center gap-2 text-sm">
              <Link to="/login" className="rounded-full px-3 py-2 hover:bg-line/60">
                Sign in
              </Link>
              <Link to="/register" className="rounded-full bg-brand px-3 py-2 text-paper-raised">
                Register
              </Link>
            </div>
          )}
        </div>
      </header>
      {open ? (
        <div className="fixed inset-0 z-50 bg-ink/40 md:hidden" onClick={() => setOpen(false)}>
          <nav
            className="h-full w-72 bg-paper p-5"
            aria-label="Mobile"
            onClick={(event) => event.stopPropagation()}
          >
            <div className="mb-6 flex items-center justify-between">
              <span className="font-display text-2xl">ANDIKA</span>
              <button type="button" aria-label="Close menu" onClick={() => setOpen(false)}>
                <X />
              </button>
            </div>
            <form onSubmit={search} className="mb-4">
              <input
                value={query}
                onChange={(event) => setQuery(event.target.value)}
                placeholder="Search stories"
                className="h-11 w-full rounded-full border border-line px-3"
              />
            </form>
            <div className="grid gap-2">
              {links.map((link) => (
                <Link key={link.to} to={link.to} onClick={() => setOpen(false)} className="rounded-xl px-2 py-2">
                  {link.label}
                </Link>
              ))}
            </div>
          </nav>
        </div>
      ) : null}
      <Outlet />
      <footer className="mt-16 border-t border-line">
        <div className="mx-auto grid max-w-6xl gap-6 px-4 py-10 md:grid-cols-3">
          <div>
            <p className="font-display text-2xl">ANDIKA</p>
            <p className="mt-2 text-sm text-ink-soft">A global desk for writers, editors, and readers.</p>
          </div>
          <div className="grid gap-2 text-sm">
            <Link to="/search">Search</Link>
            <Link to="/tags">Tags</Link>
            <Link to="/publications">Publications</Link>
          </div>
          <p className="text-sm text-ink-soft">
            Views are recorded reads. Comments shown publicly are approved comments.
          </p>
        </div>
      </footer>
    </div>
  )
}
