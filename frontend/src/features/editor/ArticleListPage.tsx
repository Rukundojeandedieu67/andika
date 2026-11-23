import { Link, useSearchParams } from "react-router"
import { useQuery } from "@tanstack/react-query"
import { useAuth } from "@/hooks/useAuth"
import { Badge } from "@/components/ui/Badge"
import { EmptyState } from "@/components/ui/EmptyState"
import { ErrorState } from "@/components/ui/ErrorState"
import { Input } from "@/components/ui/Input"
import { Pagination } from "@/components/ui/Pagination"
import { listMine } from "@/services/content"
import type { PostStatus } from "@/types/api"

export function ArticleListPage() {
  const { user } = useAuth()
  const [params, setParams] = useSearchParams()
  const page = Number(params.get("page") || 1)
  const search = params.get("q") || ""
  const status = (params.get("status") || "") as PostStatus | ""
  const query = useQuery({
    queryKey: ["mine", page, search],
    queryFn: () => listMine({ page, page_size: 20, search: search || undefined }),
    enabled: user?.role === "author" || user?.role === "administrator",
  })
  const items = (query.data?.items ?? []).filter((item) => !status || item.status === status)
  if (user && user.role === "reader") {
    return <EmptyState title="Author role required" body="The article list is available to platform authors and administrators. Publication writing lives on each publication." />
  }
  return (
    <div>
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h2 className="font-display text-4xl">Articles</h2>
        <Link to="/workspace/articles/new" className="rounded-full bg-brand px-4 py-2 text-paper-raised">New article</Link>
      </div>
      <div className="mt-4 flex flex-wrap gap-2">
        <Input
          className="max-w-xs"
          placeholder="Search titles"
          defaultValue={search}
          onBlur={(event) => {
            const next = new URLSearchParams(params)
            if (event.target.value) next.set("q", event.target.value)
            else next.delete("q")
            next.delete("page")
            setParams(next)
          }}
          aria-label="Search my articles"
        />
        {(["", "draft", "published", "archived"] as const).map((value) => (
          <button
            key={value || "all"}
            type="button"
            className={`rounded-full px-3 py-1 text-sm ${status === value ? "bg-ink text-paper" : "border border-line"}`}
            onClick={() => {
              const next = new URLSearchParams(params)
              if (value) next.set("status", value)
              else next.delete("status")
              setParams(next)
            }}
          >
            {value || "all"}
          </button>
        ))}
      </div>
      <p className="mt-2 text-sm text-ink-soft">Status filtering applies to the current page. The API lists every status together.</p>
      {query.error ? <ErrorState error={query.error} onRetry={() => void query.refetch()} /> : null}
      <div className="mt-4 grid gap-2">
        {items.map((article) => (
          <Link key={article.id} to={`/workspace/articles/${article.id}`} className="flex items-center justify-between rounded-2xl border border-line px-4 py-3">
            <span>
              <span className="block font-medium">{article.title}</span>
              <span className="text-sm text-ink-soft">{article.slug}{article.editorial_status ? ` · ${article.editorial_status.replaceAll("_", " ")}` : ""}</span>
            </span>
            <Badge>{article.status}</Badge>
          </Link>
        ))}
      </div>
      {query.data && items.length === 0 ? <EmptyState title="No articles" body="Create a draft to start writing." /> : null}
      {query.data ? (
        <div className="mt-4">
          <Pagination page={query.data.page} pageSize={query.data.page_size} total={query.data.total} onPage={(next) => {
            const updated = new URLSearchParams(params)
            updated.set("page", String(next))
            setParams(updated)
          }} />
        </div>
      ) : null}
    </div>
  )
}
