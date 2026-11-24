import { useState, type FormEvent } from "react"
import { Link } from "react-router"
import { useQuery } from "@tanstack/react-query"
import { toast } from "sonner"
import { Button } from "@/components/ui/Button"
import { EmptyState } from "@/components/ui/EmptyState"
import { ErrorState } from "@/components/ui/ErrorState"
import { Field } from "@/components/ui/Field"
import { Input } from "@/components/ui/Input"
import { Pagination } from "@/components/ui/Pagination"
import { Select } from "@/components/ui/Select"
import { formatDateTime, formatNumber, formatRate } from "@/lib/format"
import { toApiError } from "@/lib/errors"
import { adminContent, adminOverview, adminSeries, downloadAdminExport, type AnalyticsQuery } from "@/services/analytics"
import { AnalyticsFilters, AnalyticsNotes } from "@/features/analytics/AuthorAnalyticsPage"
import { listAllPosts } from "@/services/content"
import { adminCategories, createCategory, deleteCategory, setCategoryStatus } from "@/services/taxonomy"
import { adminDeleteMedia, adminMedia } from "@/services/media"
import { adminComments, adminModerate, adminReports, adminReviewReport, deliveryStats, moderationLogs } from "@/services/community"
import { adminTags, deleteTag } from "@/services/taxonomy"
import { searchStats } from "@/services/content"
import { preferredVariant } from "@/lib/media-url"
import type { CommentStatus } from "@/types/api"

export function AdminHome() {
  const [query, setQuery] = useState<AnalyticsQuery>({ period: "day", compare: true })
  const overview = useQuery({ queryKey: ["admin-overview", query], queryFn: () => adminOverview(query) })
  return (
    <div>
      <h2 className="font-display text-4xl">Platform</h2>
      <p className="mt-2 text-sm text-ink-soft">There is no user-directory endpoint. Accounts are not listed or edited here.</p>
      <div className="mt-4"><AnalyticsFilters query={query} onChange={setQuery} /></div>
      {overview.isLoading ? <div className="mt-6 h-28 animate-pulse rounded-3xl bg-line" /> : null}
      {overview.error ? <ErrorState error={overview.error} onRetry={() => void overview.refetch()} /> : null}
      {overview.data ? (
        <div className="mt-6 grid gap-3 md:grid-cols-3">
          <p>Registered users: {formatNumber(overview.data.registered_users)}</p>
          <p>Active users: {formatNumber(overview.data.active_users)}</p>
          <p>Publications: {formatNumber(overview.data.publications)}</p>
          <p>Published articles: {formatNumber(overview.data.published_articles)}</p>
          <p>All-time views: {formatNumber(overview.data.total_views)}</p>
          <p>Approved comments: {formatNumber(overview.data.total_approved_comments)}</p>
        </div>
      ) : null}
      {overview.data ? <p className="mt-3 text-sm">{overview.data.active_user_definition}</p> : null}
      <AnalyticsNotes limitations={overview.data?.limitations} />
    </div>
  )
}

export function AdminAnalyticsPage() {
  const [query, setQuery] = useState<AnalyticsQuery>({ period: "month" })
  const series = useQuery({ queryKey: ["admin-series", query], queryFn: () => adminSeries(query) })
  const content = useQuery({ queryKey: ["admin-content", query], queryFn: () => adminContent(query) })
  return (
    <div>
      <div className="flex justify-between gap-3"><h2 className="font-display text-4xl">Analytics</h2><Button onClick={() => downloadAdminExport(query).catch((error: unknown) => toast.error(toApiError(error).message))}>Export CSV</Button></div>
      <AnalyticsFilters query={query} onChange={setQuery} />
      <table className="mt-4 w-full text-sm">
        <thead><tr><th>Bucket</th><th>Views</th><th>Registrations</th><th>Publications</th></tr></thead>
        <tbody>
          {series.data?.points.map((point) => (
            <tr key={point.bucket_start}><td>{point.bucket_start}</td><td>{point.views}</td><td>{point.registrations}</td><td>{point.publications_created}</td></tr>
          ))}
        </tbody>
      </table>
      {content.data ? (
        <div className="mt-6 grid gap-2 text-sm">
          <p>Independent: {content.data.independent.published_articles} articles, {formatRate(content.data.independent.engagement_rate)}</p>
          <p>Public publications: {content.data.public_publication.published_articles} articles</p>
          <p>Other publications: {content.data.other_publication.published_articles} articles</p>
          {content.data.top_public_articles.map((article) => (
            <Link key={article.id} to={`/articles/${article.slug}`}>{article.title} · {formatNumber(article.views)} views</Link>
          ))}
          <p>{content.data.engagement_rate_formula}</p>
        </div>
      ) : null}
      <AnalyticsNotes limitations={content.data?.limitations} />
    </div>
  )
}

export function AdminArticlesPage() {
  const [search, setSearch] = useState("")
  const [status, setStatus] = useState("")
  const [page, setPage] = useState(1)
  const query = useQuery({
    queryKey: ["admin-posts", search, status, page],
    queryFn: () => listAllPosts({ page, page_size: 20, search: search || undefined, status: status || undefined }),
  })
  return (
    <div>
      <h2 className="font-display text-4xl">All articles</h2>
      <div className="mt-4 flex gap-2">
        <Input value={search} onChange={(event) => { setSearch(event.target.value); setPage(1) }} placeholder="Search" aria-label="Search articles" />
        <Select aria-label="Status" value={status} onChange={(event) => { setStatus(event.target.value); setPage(1) }}>
          <option value="">Any</option>
          <option value="draft">Draft</option>
          <option value="published">Published</option>
          <option value="archived">Archived</option>
        </Select>
      </div>
      <div className="mt-4 grid gap-2">
        {query.data?.items.map((post) => (
          <Link key={post.id} to={`/workspace/articles/${post.id}`}>{post.title} · {post.status} · {post.author.username}</Link>
        ))}
      </div>
      {query.error ? <ErrorState error={query.error} onRetry={() => void query.refetch()} /> : null}
      {query.data && query.data.items.length === 0 ? <EmptyState title="No articles" body="The administration list includes drafts, published articles, and archived articles." /> : null}
      {query.data ? <div className="mt-4"><Pagination page={query.data.page} pageSize={query.data.page_size} total={query.data.total} onPage={setPage} /></div> : null}
    </div>
  )
}

export function AdminCategoriesPage() {
  const query = useQuery({ queryKey: ["admin-categories"], queryFn: () => adminCategories(1) })
  const [name, setName] = useState("")
  async function submit(event: FormEvent) {
    event.preventDefault()
    try {
      await createCategory({ name })
      setName("")
      await query.refetch()
    } catch (error) {
      toast.error(toApiError(error).message)
    }
  }
  return (
    <div>
      <h2 className="font-display text-4xl">Categories</h2>
      <form className="mt-4 flex gap-2" onSubmit={submit}>
        <Field label="Name" htmlFor="category-name"><Input id="category-name" value={name} onChange={(event) => setName(event.target.value)} required /></Field>
        <Button type="submit">Create</Button>
      </form>
      {query.error ? <ErrorState error={query.error} onRetry={() => void query.refetch()} /> : null}
      <div className="mt-4 grid gap-2 text-sm">
        {query.data?.items.map((category) => (
          <div key={category.id} className="flex items-center justify-between rounded-2xl border border-line px-3 py-2">
            <span>{category.name} · {category.is_active ? "active" : "inactive"}</span>
            <span className="flex gap-2">
              <button type="button" onClick={() => setCategoryStatus(category.id, !category.is_active).then(() => query.refetch())}>{category.is_active ? "Deactivate" : "Activate"}</button>
              <button type="button" onClick={() => { if (!window.confirm(`Delete ${category.name}? A category with children cannot be deleted.`)) return; deleteCategory(category.id).then(() => query.refetch()).catch((error: unknown) => toast.error(toApiError(error).message)) }}>Delete</button>
            </span>
          </div>
        ))}
      </div>
    </div>
  )
}

export function AdminTagsPage() {
  const query = useQuery({ queryKey: ["admin-tags"], queryFn: () => adminTags(1) })
  return (
    <div>
      <h2 className="font-display text-4xl">Tags</h2>
      {query.error ? <ErrorState error={query.error} onRetry={() => void query.refetch()} /> : null}
      {query.data?.items.map((tag) => (
        <div key={tag.id} className="mt-2 flex justify-between text-sm">
          <span>{tag.name}</span>
          <button type="button" onClick={() => { if (!window.confirm(`Delete the tag ${tag.name}? Articles keep their text. The tag link is removed.`)) return; deleteTag(tag.id).then(() => query.refetch()).catch((error: unknown) => toast.error(toApiError(error).message)) }}>Delete</button>
        </div>
      ))}
    </div>
  )
}

export function AdminCommentsPage() {
  const [status, setStatus] = useState("")
  const query = useQuery({
    queryKey: ["admin-comments", status],
    queryFn: () => adminComments({ page: 1, page_size: 20, status: status || undefined }),
  })
  const logs = useQuery({ queryKey: ["moderation-logs"], queryFn: () => moderationLogs(1) })
  return (
    <div>
      <h2 className="font-display text-4xl">Comments</h2>
      <p className="mt-2 text-sm text-ink-soft">Administrators can reject a comment. Article authors can approve or hide, not reject.</p>
      <Select className="mt-4 max-w-xs" aria-label="Comment status" value={status} onChange={(event) => setStatus(event.target.value)}>
        <option value="">Any</option>
        <option value="pending">Pending</option>
        <option value="approved">Approved</option>
        <option value="hidden">Hidden</option>
        <option value="rejected">Rejected</option>
      </Select>
      {query.error ? <ErrorState error={query.error} onRetry={() => void query.refetch()} /> : null}
      {query.data?.items.map((comment) => (
        <article key={comment.id} className="mt-3 rounded-2xl border border-line p-3 text-sm">
          <p>{comment.status} · {comment.author.username}</p>
          <p>{comment.deleted_at ? "Removed" : comment.body}</p>
          <div className="mt-2 flex gap-2">
            {(["approved", "hidden", "rejected"] as CommentStatus[]).map((next) => (
              <button key={next} type="button" onClick={() => adminModerate(comment.id, next).then(() => query.refetch()).catch((error: unknown) => toast.error(toApiError(error).message))}>{next}</button>
            ))}
          </div>
        </article>
      ))}
      <h3 className="mt-8 font-display text-2xl">Audit log</h3>
      {logs.data?.items.map((log) => (
        <p key={log.id} className="text-sm">{formatDateTime(log.created_at)} · {log.action} · {log.previous_status} to {log.new_status}</p>
      ))}
    </div>
  )
}

export function AdminReportsPage() {
  const query = useQuery({ queryKey: ["admin-reports"], queryFn: () => adminReports({ page: 1, page_size: 20, status: "open" }) })
  return (
    <div>
      <h2 className="font-display text-4xl">Reports</h2>
      <p className="text-sm text-ink-soft">Reporter email addresses are not returned.</p>
      {query.data?.items.map((report) => (
        <div key={report.id} className="mt-3 text-sm">
          {report.reason} · {report.status} · {report.reporter.username}
          <button type="button" className="ml-2" onClick={() => adminReviewReport(report.id, "resolved").then(() => query.refetch())}>Resolve</button>
          <button type="button" className="ml-2" onClick={() => adminReviewReport(report.id, "dismissed").then(() => query.refetch())}>Dismiss</button>
        </div>
      ))}
    </div>
  )
}

export function AdminMediaPage() {
  const query = useQuery({ queryKey: ["admin-media"], queryFn: () => adminMedia(1) })
  return (
    <div>
      <h2 className="font-display text-4xl">Media</h2>
      {query.error ? <ErrorState error={query.error} onRetry={() => void query.refetch()} /> : null}
      <div className="mt-4 grid gap-3 sm:grid-cols-3">
        {query.data?.items.map((item) => (
          <article key={item.id}>
            <img src={preferredVariant(item.variants, ["thumbnail"]) || ""} alt="" className="h-28 w-full rounded-2xl object-cover" />
            <button type="button" className="text-sm" onClick={() => { if (!window.confirm("Delete this image from the library?")) return; adminDeleteMedia(item.id).then(() => query.refetch()).catch((error: unknown) => toast.error(toApiError(error).message)) }}>Delete</button>
          </article>
        ))}
      </div>
    </div>
  )
}

export function AdminSearchPage() {
  const query = useQuery({ queryKey: ["search-stats"], queryFn: searchStats })
  return (
    <div>
      <h2 className="font-display text-4xl">Search</h2>
      {query.error ? <ErrorState error={query.error} onRetry={() => void query.refetch()} /> : null}
      {query.data ? <p className="mt-2">{formatNumber(query.data.total)} searches since {formatDateTime(query.data.since)}. Individual searchers are not identified.</p> : null}
      {query.data?.top_queries.map((item) => <p key={item.query} className="text-sm">{item.query} · {item.count}</p>)}
    </div>
  )
}

export function AdminDeliveryPage() {
  const query = useQuery({ queryKey: ["delivery"], queryFn: deliveryStats })
  return (
    <div>
      <h2 className="font-display text-4xl">Email delivery</h2>
      <p className="text-sm text-ink-soft">Addresses and message bodies are omitted.</p>
      {query.error ? <ErrorState error={query.error} onRetry={() => void query.refetch()} /> : null}
      {query.data ? (
        <p className="mt-3">Pending {query.data.pending} · sending {query.data.sending} · sent {query.data.sent} · failed {query.data.failed} · not configured {query.data.not_configured}</p>
      ) : null}
      {query.data?.failed_jobs.map((job) => (
        <p key={job.id} className="text-sm">{job.notification_type} · attempts {job.attempts} · {job.last_error}</p>
      ))}
    </div>
  )
}
