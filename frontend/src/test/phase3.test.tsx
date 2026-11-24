import { QueryClient, QueryClientProvider } from "@tanstack/react-query"
import { render, screen } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import type { ReactNode } from "react"
import { createMemoryRouter, RouterProvider } from "react-router"
import { describe, expect, it, vi } from "vitest"
import { AuthContext, type AuthContextValue } from "@/features/auth/auth-context"
import { ArticleListPage } from "@/features/editor/ArticleListPage"
import { EditorPage } from "@/features/editor/EditorPage"
import { countByStatus, mediaFileError, statusTone, wrapSelection } from "@/features/editor/article-desk"
import { WorkspaceHome } from "@/features/editor/WorkspaceHome"
import { authorOverview } from "@/services/analytics"
import { collectMine, createDraft, listMine } from "@/services/content"
import type { UserPublic } from "@/types/api"

vi.mock("@/services/content", () => ({
  listMine: vi.fn(),
  collectMine: vi.fn(),
  createDraft: vi.fn(),
}))

vi.mock("@/services/analytics", () => ({
  authorOverview: vi.fn(),
}))

vi.mock("@/services/publications", () => ({
  myPublications: vi.fn().mockResolvedValue({ items: [], page: 1, page_size: 20, total: 0 }),
}))

vi.mock("@/services/taxonomy", () => ({
  categoryTree: vi.fn().mockResolvedValue([]),
  listTags: vi.fn().mockResolvedValue({ items: [], page: 1, page_size: 40, total: 0 }),
  createTag: vi.fn(),
}))

vi.mock("@/services/media", () => ({
  myMedia: vi.fn().mockResolvedValue({ items: [], page: 1, page_size: 24, total: 0 }),
  uploadMedia: vi.fn(),
}))

const author = {
  id: "author-1",
  username: "ada",
  email: "ada@example.com",
  full_name: "Ada",
  avatar_url: null,
  bio: null,
  role: "author",
  is_active: true,
  is_verified: true,
  created_at: "",
  updated_at: "",
  last_login_at: null,
} satisfies UserPublic

const article = {
  id: "post-1",
  author_id: "author-1",
  publication_id: null,
  category_id: null,
  title: "Desk notes",
  slug: "desk-notes",
  subtitle: null,
  excerpt: null,
  content: "Hello",
  featured_image: null,
  featured_image_id: null,
  status: "draft" as const,
  editorial_status: null,
  is_featured: false,
  allow_comments: true,
  meta_title: null,
  meta_description: null,
  reading_time: 1,
  published_at: null,
  created_at: "",
  updated_at: "2026-01-02T00:00:00Z",
  deleted_at: null,
  author: { id: "author-1", username: "ada", full_name: "Ada", avatar_url: null, bio: null },
  category: null,
  tags: [],
  featured_image_media: null,
}

function renderDesk(path: string, user: UserPublic | null = author) {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  const auth = {
    user,
    status: user ? "authenticated" : "anonymous",
    login: vi.fn(),
    logout: vi.fn(),
    setUser: vi.fn(),
    saveProfile: vi.fn(),
  } satisfies AuthContextValue
  const router = createMemoryRouter(
    [
      { path: "/workspace", element: <WorkspaceHome /> },
      { path: "/workspace/articles", element: <ArticleListPage /> },
      { path: "/workspace/articles/new", element: <EditorPage /> },
    ],
    { initialEntries: [path] },
  )
  function Wrap({ children }: { children: ReactNode }) {
    return (
      <QueryClientProvider client={queryClient}>
        <AuthContext.Provider value={auth}>{children}</AuthContext.Provider>
      </QueryClientProvider>
    )
  }
  render(<RouterProvider router={router} />, { wrapper: Wrap })
}

describe("author desk helpers", () => {
  it("counts only the statuses returned by the API", () => {
    expect(countByStatus([{ status: "draft" }, { status: "draft" }, { status: "published" }])).toEqual({
      draft: 2,
      published: 1,
      archived: 0,
    })
    expect(statusTone("published")).toBe("brand")
    expect(statusTone("archived")).toBe("accent")
  })

  it("rejects media the upload endpoint will not accept", () => {
    expect(mediaFileError({ type: "image/gif", size: 100 })).toMatch(/JPEG/)
    expect(mediaFileError({ type: "image/png", size: 11 * 1024 * 1024 })).toMatch(/10 MB/)
    expect(mediaFileError({ type: "image/webp", size: 1024 })).toBeNull()
  })

  it("wraps the selected article text", () => {
    expect(wrapSelection("Hello", 0, 5, "**", "**").value).toBe("**Hello**")
  })
})

describe("author workspace screens", () => {
  it("shows analytics totals and leaves draft totals blank until the full list loads", async () => {
    vi.mocked(authorOverview).mockResolvedValue({
      published_articles: 4,
      publication_articles: 0,
      total_views: 10,
      period_views: 2,
      total_approved_comments: 1,
      period_approved_comments: 0,
      average_views_per_article: 2.5,
      window: { date_from: "2026-01-01T00:00:00Z", date_to: "2026-01-31T00:00:00Z", timezone: "UTC" },
      comparison: null,
      limitations: [],
    })
    vi.mocked(collectMine).mockResolvedValue({ items: [article], total: 1, complete: true })
    renderDesk("/workspace")
    expect(await screen.findByText("4")).toBeInTheDocument()
    expect(await screen.findByText("Counted from your full article list.")).toBeInTheDocument()
    expect(await screen.findByRole("link", { name: /Desk notes/ })).toBeInTheDocument()
  })

  it("keeps a reader out of the article list", async () => {
    renderDesk("/workspace/articles", { ...author, role: "reader", is_verified: true })
    expect(await screen.findByRole("heading", { name: "Verified author required" })).toBeInTheDocument()
    expect(listMine).not.toHaveBeenCalled()
  })

  it("renders a draft badge from the author list", async () => {
    vi.mocked(listMine).mockResolvedValue({ items: [article], page: 1, page_size: 20, total: 1 })
    renderDesk("/workspace/articles")
    expect(await screen.findByRole("link", { name: /Desk notes/ })).toBeInTheDocument()
  })

  it("filters the loaded list when a status is selected", async () => {
    vi.mocked(collectMine).mockResolvedValue({
      items: [article, { ...article, id: "post-2", title: "Live", slug: "live", status: "published" }],
      total: 2,
      complete: true,
    })
    renderDesk("/workspace/articles?status=published")
    expect(await screen.findByText("Live")).toBeInTheDocument()
    expect(screen.queryByText("Desk notes")).not.toBeInTheDocument()
  })
})

describe("draft creation", () => {
  it("saves a titled draft and does not publish it", async () => {
    vi.mocked(createDraft).mockResolvedValue(article)
    renderDesk("/workspace/articles/new")
    const user = userEvent.setup()
    await user.type(await screen.findByLabelText("Title"), "Desk notes")
    await user.click(screen.getByRole("button", { name: "Save Draft" }))
    expect(createDraft).toHaveBeenCalledWith(expect.objectContaining({ title: "Desk notes", content: "" }))
  })

  it("blocks an empty title before calling the API", async () => {
    vi.mocked(createDraft).mockClear()
    renderDesk("/workspace/articles/new")
    const user = userEvent.setup()
    await user.click(await screen.findByRole("button", { name: "Save Draft" }))
    expect(createDraft).not.toHaveBeenCalled()
  })
})
