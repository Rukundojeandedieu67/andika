import { Link } from "react-router"
import { useQuery } from "@tanstack/react-query"
import { useAuth } from "@/hooks/useAuth"
import { usePageTitle } from "@/hooks/usePageTitle"
import { Badge } from "@/components/ui/Badge"
import { Card } from "@/components/ui/Card"
import { EmptyState } from "@/components/ui/EmptyState"
import { ErrorState } from "@/components/ui/ErrorState"
import { countByStatus, statusTone } from "@/features/editor/article-desk"
import { displayName, formatNumber } from "@/lib/format"
import { authorOverview } from "@/services/analytics"
import { collectMine } from "@/services/content"
import { myPublications } from "@/services/publications"

export function WorkspaceHome() {
  usePageTitle("Workspace")
  const { user } = useAuth()
  const canWrite = Boolean(user?.is_verified && (user.role === "author" || user.role === "administrator"))
  const articles = useQuery({
    queryKey: ["mine", "overview"],
    queryFn: () => collectMine(),
    enabled: canWrite,
  })
  const analytics = useQuery({
    queryKey: ["author-overview", "desk"],
    queryFn: () => authorOverview({ compare: false }),
    enabled: canWrite,
    retry: false,
  })
  const publications = useQuery({
    queryKey: ["my-publications"],
    queryFn: () => myPublications(1),
    enabled: canWrite,
    retry: false,
  })
  const counts = articles.data?.complete ? countByStatus(articles.data.items) : null
  const drafts = (articles.data?.items ?? []).filter((item) => item.status === "draft").slice(0, 4)
  return (
    <div>
      <p className="text-sm tracking-[0.16em] text-accent uppercase">Author desk</p>
      <h2 className="mt-2 font-display text-4xl">Welcome{user ? `, ${displayName(user)}` : ""}</h2>
      <p className="mt-2 max-w-2xl text-ink-soft">
        {canWrite
          ? "Write independently, or open a publication you belong to. Saving a draft does not publish it."
          : "Independent articles require a verified author or administrator. Publication members write inside a publication after their email is verified."}
      </p>
      <div className="mt-6 flex flex-wrap gap-3">
        {canWrite ? <Link to="/workspace/articles/new" className="rounded-full bg-brand px-4 py-2 text-paper-raised">New article</Link> : null}
        <Link to="/workspace/articles" className="rounded-full border border-line px-4 py-2">Article list</Link>
        {canWrite ? <Link to="/workspace/media" className="rounded-full border border-line px-4 py-2">Media library</Link> : null}
        {canWrite ? <Link to="/workspace/analytics" className="rounded-full border border-line px-4 py-2">Analytics</Link> : null}
      </div>
      <div className="mt-6 grid gap-4 md:grid-cols-3">
        <Card>
          <p className="text-sm text-ink-soft">Published articles</p>
          <p className="font-display text-3xl">{analytics.data ? formatNumber(analytics.data.published_articles) : "—"}</p>
          <p className="mt-1 text-xs text-ink-soft">{analytics.data ? "All-time total from author analytics." : canWrite ? (analytics.isLoading ? "Loading analytics." : "Analytics is unavailable.") : "Available to a verified author."}</p>
        </Card>
        <Card>
          <p className="text-sm text-ink-soft">Drafts</p>
          <p className="font-display text-3xl">{counts ? formatNumber(counts.draft) : "—"}</p>
          <p className="mt-1 text-xs text-ink-soft">{counts ? "Counted from your full article list." : canWrite ? "The list API has no status total." : "Available to a verified author."}</p>
        </Card>
        <Card>
          <p className="text-sm text-ink-soft">Archived</p>
          <p className="font-display text-3xl">{counts ? formatNumber(counts.archived) : "—"}</p>
          <p className="mt-1 text-xs text-ink-soft">{articles.data && !articles.data.complete ? "More than 500 articles, so this total is not shown." : "Archived articles are not public."}</p>
        </Card>
      </div>
      {analytics.data ? (
        <p className="mt-3 text-sm text-ink-soft">
          {formatNumber(analytics.data.total_views)} recorded views and {formatNumber(analytics.data.total_approved_comments)} approved comments. Views are stored read events, not unique readers.
        </p>
      ) : null}
      {analytics.error ? <div className="mt-4"><ErrorState error={analytics.error} /></div> : null}
      {articles.error ? <div className="mt-4"><ErrorState error={articles.error} onRetry={() => void articles.refetch()} /></div> : null}
      {canWrite ? (
        <section className="mt-8">
          <div className="flex items-end justify-between gap-3">
            <h3 className="font-display text-2xl">Recent drafts</h3>
            <Link to="/workspace/articles?status=draft" className="text-sm text-brand">All articles</Link>
          </div>
          <div className="mt-4 grid gap-3">
            {drafts.map((article) => (
              <Link key={article.id} to={`/workspace/articles/${article.id}`} className="flex items-center justify-between rounded-2xl border border-line px-4 py-3">
                <span>{article.title}</span>
                <Badge tone={statusTone(article.status)}>{article.status}</Badge>
              </Link>
            ))}
          </div>
          {articles.data && drafts.length === 0 ? <EmptyState title="No drafts in the loaded list" body="Start a new article. It stays a draft until you publish it." /> : null}
        </section>
      ) : null}
      <section className="mt-8">
        <h3 className="font-display text-2xl">Publications</h3>
        <div className="mt-3 grid gap-2">
          {publications.data?.items.map((item) => (
            <Link key={item.id} to={`/workspace/publications/${item.id}`} className="rounded-2xl border border-line px-4 py-3">
              {item.name} · {item.role} · {item.status}
            </Link>
          ))}
        </div>
        {publications.data && publications.data.items.length === 0 ? <p className="mt-3 text-sm text-ink-soft">You have no publications yet.</p> : null}
      </section>
    </div>
  )
}
