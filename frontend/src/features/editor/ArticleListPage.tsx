import { Link, useSearchParams } from "react-router"
import { useQuery } from "@tanstack/react-query"
import { useAuth } from "@/hooks/useAuth"
import { usePageTitle } from "@/hooks/usePageTitle"
import { Badge } from "@/components/ui/Badge"
import { EmptyState } from "@/components/ui/EmptyState"
import { ErrorState } from "@/components/ui/ErrorState"
import { Input } from "@/components/ui/Input"
import { Pagination } from "@/components/ui/Pagination"
import { articleStatuses, statusTone } from "@/features/editor/article-desk"
import { formatDateTime } from "@/lib/format"
import { collectMine, listMine } from "@/services/content"
import type { PostStatus } from "@/types/api"

export function ArticleListPage() {
  usePageTitle("My articles")
  const { user } = useAuth()
  const [params, setParams] = useSearchParams()
  const page = Number(params.get("page") || 1)
  const search = params.get("q") || ""
  const status = (params.get("status") || "") as PostStatus | ""
  const canWrite = Boolean(user?.is_verified && (user.role === "author" || user.role === "administrator"))
  const listed = useQuery({
    queryKey: ["mine", page, search],
    queryFn: () => listMine({ page, page_size: 20, search: search || undefined }),
    enabled: canWrite && !status,
  })
  const filtered = useQuery({
    queryKey: ["mine", "filtered", search, status],
    queryFn: () => collectMine(search || undefined),
    enabled: canWrite && Boolean(status),
  })
  if (user && !canWrite) {
    return <EmptyState title="Verified author required" body="The article list is available to verified authors and administrators. Readers and unverified accounts cannot open it." />
  }
  const items = status
    ? (filtered.data?.items ?? []).filter((item) => item.status === status)
    : (listed.data?.items ?? [])
  const error = status ? filtered.error : listed.error
  function update(next: Record<string, string | undefined>) {
    const updated = new URLSearchParams(params)
    for (const [key, value] of Object.entries(next)) {
      if (!value) updated.delete(key)
      else updated.set(key, value)
    }
    if (!("page" in next)) updated.delete("page")
    setParams(updated)
  }
  return (
    <div>
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h2 className="font-display text-4xl">Articles</h2>
        <Link to="/workspace/articles/new" className="rounded-full bg-brand px-4 py-2 text-paper-raised">New article</Link>
      </div>
      <p className="mt-2 text-sm text-ink-soft">Ordered by last update. The API does not accept a status or sort parameter, so a status filter is applied after the matching pages are loaded.</p>
      <div className="mt-4 flex flex-wrap gap-2">
        <Input
          className="max-w-xs"
          placeholder="Search titles"
          defaultValue={search}
          aria-label="Search my articles"
          onBlur={(event) => update({ q: event.target.value || undefined })}
        />
        <button type="button" className={`rounded-full px-3 py-1 text-sm ${status === "" ? "bg-ink text-paper" : "border border-line"}`} onClick={() => update({ status: undefined })}>All</button>
        {articleStatuses.map((value) => (
          <button key={value} type="button" className={`rounded-full px-3 py-1 text-sm ${status === value ? "bg-ink text-paper" : "border border-line"}`} onClick={() => update({ status: value })}>
            {value}
          </button>
        ))}
      </div>
      {filtered.data && !filtered.data.complete ? <p className="mt-3 text-sm text-danger">More than 500 articles matched, so this filtered list is incomplete.</p> : null}
      {error ? <ErrorState error={error} onRetry={() => void (status ? filtered.refetch() : listed.refetch())} /> : null}
      <div className="mt-4 grid gap-2">
        {items.map((article) => (
          <Link key={article.id} to={`/workspace/articles/${article.id}`} className="flex items-center justify-between gap-3 rounded-2xl border border-line px-4 py-3">
            <span>
              <span className="block font-medium">{article.title}</span>
              <span className="text-sm text-ink-soft">{article.slug} · updated {formatDateTime(article.updated_at)}</span>
            </span>
            <Badge tone={statusTone(article.status)}>{article.status}</Badge>
          </Link>
        ))}
      </div>
      {!error && ((status && filtered.data) || (!status && listed.data)) && items.length === 0 ? (
        <EmptyState title="No articles" body={status ? `No ${status} articles matched this search.` : "Create a draft to start writing. It is not public until you publish it."} />
      ) : null}
      {!status && listed.data ? (
        <div className="mt-4">
          <Pagination page={listed.data.page} pageSize={listed.data.page_size} total={listed.data.total} onPage={(next) => update({ page: String(next) })} />
        </div>
      ) : null}
    </div>
  )
}
