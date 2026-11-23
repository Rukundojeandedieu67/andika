import { Link } from "react-router"
import { useQuery } from "@tanstack/react-query"
import { useAuth } from "@/hooks/useAuth"
import { Badge } from "@/components/ui/Badge"
import { Card } from "@/components/ui/Card"
import { ErrorState } from "@/components/ui/ErrorState"
import { formatNumber } from "@/lib/format"
import { authorOverview } from "@/services/analytics"
import { listMine } from "@/services/content"
import { myPublications } from "@/services/publications"

export function WorkspaceHome() {
  const { user } = useAuth()
  const canList = user?.role === "author" || user?.role === "administrator"
  const articles = useQuery({
    queryKey: ["mine", "overview"],
    queryFn: () => listMine({ page: 1, page_size: 8 }),
    enabled: canList,
  })
  const analytics = useQuery({
    queryKey: ["author-overview", "desk"],
    queryFn: () => authorOverview({ compare: false }),
    enabled: Boolean(user?.is_verified),
    retry: false,
  })
  const publications = useQuery({
    queryKey: ["my-publications"],
    queryFn: () => myPublications(1),
    enabled: Boolean(user?.is_verified),
    retry: false,
  })
  const counts = { draft: 0, published: 0, archived: 0 }
  for (const item of articles.data?.items ?? []) counts[item.status] += 1
  return (
    <div>
      <h2 className="font-display text-4xl">Overview</h2>
      <p className="mt-2 text-ink-soft">
        {user?.is_verified
          ? "Verified accounts can open publications and read their own analytics."
          : "Verify your email before publishing or opening a publication."}
      </p>
      <div className="mt-6 grid gap-4 md:grid-cols-3">
        <Card>
          <p className="text-sm text-ink-soft">Published articles</p>
          <p className="font-display text-3xl">{analytics.data ? formatNumber(analytics.data.published_articles) : "—"}</p>
        </Card>
        <Card>
          <p className="text-sm text-ink-soft">All-time recorded views</p>
          <p className="font-display text-3xl">{analytics.data ? formatNumber(analytics.data.total_views) : "—"}</p>
        </Card>
        <Card>
          <p className="text-sm text-ink-soft">Approved comments</p>
          <p className="font-display text-3xl">{analytics.data ? formatNumber(analytics.data.total_approved_comments) : "—"}</p>
        </Card>
      </div>
      {analytics.data ? (
        <p className="mt-3 text-sm text-ink-soft">
          Period views ({formatNumber(analytics.data.period_views)}) use the selected window. Overview totals are all-time. Views are stored read events, not unique readers.
        </p>
      ) : null}
      {analytics.error ? <div className="mt-4"><ErrorState error={analytics.error} /></div> : null}
      <div className="mt-8 flex flex-wrap gap-3">
        {canList ? <Link to="/workspace/articles/new" className="rounded-full bg-brand px-4 py-2 text-paper-raised">New article</Link> : null}
        {user?.is_verified ? <Link to="/workspace/publications/new" className="rounded-full border border-line px-4 py-2">New publication</Link> : null}
      </div>
      {canList ? (
        <section className="mt-8">
          <h3 className="font-display text-2xl">Recent articles</h3>
          <p className="text-sm text-ink-soft">
            On this page: {counts.draft} drafts, {counts.published} published, {counts.archived} archived.
            The article list API does not filter by status, so these counts are only for the loaded page.
          </p>
          <div className="mt-4 grid gap-3">
            {articles.data?.items.map((article) => (
              <Link key={article.id} to={`/workspace/articles/${article.id}`} className="flex items-center justify-between rounded-2xl border border-line px-4 py-3">
                <span>{article.title}</span>
                <Badge>{article.status}</Badge>
              </Link>
            ))}
          </div>
        </section>
      ) : (
        <p className="mt-8 text-sm text-ink-soft">Independent articles require an author or administrator role. Publication members write inside a publication.</p>
      )}
      <section className="mt-8">
        <h3 className="font-display text-2xl">Publications</h3>
        <div className="mt-3 grid gap-2">
          {publications.data?.items.map((item) => (
            <Link key={item.id} to={`/workspace/publications/${item.id}`} className="rounded-2xl border border-line px-4 py-3">
              {item.name} · {item.role} · {item.status}
            </Link>
          ))}
        </div>
      </section>
    </div>
  )
}
