import { render, screen } from "@testing-library/react"
import { createMemoryRouter, RouterProvider } from "react-router"
import { describe, expect, it } from "vitest"
import { Button } from "@/components/ui/Button"
import { articleHtml } from "@/lib/article-content"
import { notificationHref } from "@/lib/links"
import { passwordError } from "@/lib/password"
import { applyAccessSession, getAccessToken, publishAuth } from "@/lib/session"
import { NotFoundPage } from "@/components/shared/states"
import type { UserPublic } from "@/types/api"

describe("password rules", () => {
  it("matches the backend minimum", () => {
    expect(passwordError("short1")).toMatch(/12/)
    expect(passwordError("longenoughpassword")).toMatch(/number/)
    expect(passwordError("andika123456")).toMatch(/common/)
    expect(passwordError("ReaderPass123", { username: "Reader" })).toMatch(/username/)
    expect(passwordError("A proper passphrase 1")).toBeNull()
  })
})

describe("article content", () => {
  it("escapes html and keeps markdown links", () => {
    const html = articleHtml("Hello <script>\n\n[site](https://andika.test)")
    expect(html).toContain("&lt;script&gt;")
    expect(html).not.toContain("<script>")
    expect(html).toContain('href="https://andika.test"')
  })
})

describe("notification links", () => {
  it("maps article API paths to the reader route", () => {
    expect(notificationHref("/api/v1/posts/field-notes", {})).toBe("/articles/field-notes")
    expect(notificationHref("/api/v1/publications/11111111-1111-1111-1111-111111111111/members", {})).toContain("/workspace/publications/")
  })
})

describe("session storage", () => {
  it("keeps the access token in memory and ignores the refresh token", () => {
    localStorage.clear()
    sessionStorage.clear()
    const user = {
      id: "1",
      username: "ada",
      email: "ada@example.com",
      full_name: null,
      avatar_url: null,
      bio: null,
      role: "reader",
      is_active: true,
      is_verified: false,
      created_at: "",
      updated_at: "",
      last_login_at: null,
    } satisfies UserPublic
    applyAccessSession("access-token", user)
    expect(getAccessToken()).toBe("access-token")
    expect(localStorage.getItem("refresh_token")).toBeNull()
    expect(sessionStorage.length).toBe(0)
    publishAuth(null)
    expect(getAccessToken()).toBeNull()
  })
})

describe("routing", () => {
  it("renders the not found page", () => {
    const router = createMemoryRouter([{ path: "*", element: <NotFoundPage /> }], { initialEntries: ["/missing"] })
    render(<RouterProvider router={router} />)
    expect(screen.getByRole("heading", { name: /not on andika/i })).toBeInTheDocument()
  })
})

describe("button", () => {
  it("renders its label", () => {
    render(<Button>Publish</Button>)
    expect(screen.getByRole("button", { name: "Publish" })).toBeEnabled()
  })
})
