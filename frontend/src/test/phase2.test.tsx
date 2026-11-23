import { QueryClient, QueryClientProvider } from "@tanstack/react-query"
import { render, screen } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import type { ReactNode } from "react"
import { createMemoryRouter, RouterProvider } from "react-router"
import { beforeEach, describe, expect, it, vi } from "vitest"
import { AuthProvider } from "@/app/providers/AuthProvider"
import { RequireAuth } from "@/app/router/guards"
import { LoginPage, RegisterPage } from "@/features/auth/AuthPages"
import { DiscoverPage } from "@/features/discovery/DiscoveryPages"
import { SearchPage } from "@/features/search/SearchPage"
import { ApiError } from "@/lib/errors"
import { loginAccount, registerAccount, restoreSession } from "@/services/auth"
import { discoverArticles, searchContent } from "@/services/content"

vi.mock("@/services/auth", () => ({
  restoreSession: vi.fn(),
  loginAccount: vi.fn(),
  logoutAccount: vi.fn(),
  registerAccount: vi.fn(),
  updateProfile: vi.fn(),
}))

vi.mock("@/services/content", () => ({
  discoverArticles: vi.fn(),
  searchContent: vi.fn(),
  suggest: vi.fn().mockResolvedValue({ query: "", items: [] }),
}))

const reader = {
  id: "1",
  username: "ada",
  email: "ada@example.com",
  full_name: "Ada",
  avatar_url: null,
  bio: null,
  role: "reader" as const,
  is_active: true,
  is_verified: false,
  created_at: "",
  updated_at: "",
  last_login_at: null,
}

function renderRoutes(path: string) {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  const router = createMemoryRouter(
    [
      { path: "/login", element: <LoginPage /> },
      { path: "/register", element: <RegisterPage /> },
      { path: "/", element: <h1>Home</h1> },
      { element: <RequireAuth />, children: [{ path: "/account", element: <h1>Account</h1> }] },
      { path: "/discover/:feed", element: <DiscoverPage /> },
      { path: "/search", element: <SearchPage /> },
    ],
    { initialEntries: [path] },
  )
  function Wrap({ children }: { children: ReactNode }) {
    return (
      <QueryClientProvider client={queryClient}>
        <AuthProvider>{children}</AuthProvider>
      </QueryClientProvider>
    )
  }
  render(<RouterProvider router={router} />, { wrapper: Wrap })
  return router
}

beforeEach(() => {
  vi.mocked(restoreSession).mockResolvedValue(null)
  vi.mocked(loginAccount).mockReset()
  vi.mocked(registerAccount).mockReset()
})

describe("authentication screens", () => {
  it("rejects a registration that does not meet the password rules", async () => {
    renderRoutes("/register")
    const user = userEvent.setup()
    await user.type(screen.getByLabelText("Username"), "ada")
    await user.type(screen.getByLabelText("Email"), "ada@example.com")
    await user.type(screen.getByLabelText("Password"), "short")
    await user.type(screen.getByLabelText("Confirm password"), "short")
    await user.click(screen.getByRole("button", { name: "Create reader account" }))
    expect(await screen.findByRole("alert")).toHaveTextContent(/12/)
    expect(registerAccount).not.toHaveBeenCalled()
  })

  it("shows the backend login error and does not navigate", async () => {
    vi.mocked(loginAccount).mockRejectedValue(new ApiError(401, "unauthorized", "Invalid email or password."))
    renderRoutes("/login")
    const user = userEvent.setup()
    await user.type(screen.getByLabelText("Email"), "ada@example.com")
    await user.type(screen.getByLabelText("Password"), "ReaderPass123")
    await user.click(screen.getByRole("button", { name: "Sign in" }))
    expect(await screen.findByRole("alert")).toHaveTextContent(/invalid email or password/i)
  })

  it("sends an anonymous visitor away from an account page", async () => {
    renderRoutes("/account")
    expect(await screen.findByRole("heading", { name: "Sign in" })).toBeInTheDocument()
  })

  it("opens the account page after a successful login", async () => {
    vi.mocked(loginAccount).mockResolvedValue(reader)
    renderRoutes("/login")
    const user = userEvent.setup()
    await user.type(screen.getByLabelText("Email"), "ada@example.com")
    await user.type(screen.getByLabelText("Password"), "ReaderPass123")
    await user.click(screen.getByRole("button", { name: "Sign in" }))
    expect(await screen.findByRole("heading", { name: "Home" })).toBeInTheDocument()
    expect(loginAccount).toHaveBeenCalledWith("ada@example.com", "ReaderPass123")
  })
})

describe("public pages", () => {
  it("renders a discovery feed from the API", async () => {
    vi.mocked(discoverArticles).mockResolvedValue({
      items: [
        {
          id: "post-1",
          title: "Field notes",
          slug: "field-notes",
          excerpt: "A public essay",
          featured_image: null,
          published_at: "2026-01-01T00:00:00Z",
          reading_time: 3,
          comment_count: 0,
          view_count: 2,
          author: { id: "1", username: "ada", full_name: "Ada", avatar_url: null, bio: null },
          publication: null,
          category: null,
          tags: [],
        },
      ],
      page: 1,
      page_size: 12,
      total: 1,
    })
    renderRoutes("/discover/trending")
    expect(await screen.findByRole("heading", { name: "Field notes" })).toBeInTheDocument()
    expect(discoverArticles).toHaveBeenCalledWith("trending", 1, 12)
  })

  it("keeps the search query in the page", async () => {
    vi.mocked(searchContent).mockResolvedValue({
      query: "kelp",
      articles: { items: [], page: 1, page_size: 12, total: 0 },
      authors: { items: [], page: 1, page_size: 12, total: 0 },
      publications: { items: [], page: 1, page_size: 12, total: 0 },
      categories: { items: [], page: 1, page_size: 12, total: 0 },
      tags: { items: [], page: 1, page_size: 12, total: 0 },
    })
    renderRoutes("/search?q=kelp")
    expect(await screen.findByRole("heading", { name: "No matches" })).toBeInTheDocument()
    expect(searchContent).toHaveBeenCalledWith(expect.objectContaining({ q: "kelp" }))
  })
})
