import { useQuery } from "@tanstack/react-query"
import { Link, useParams, useSearchParams } from "react-router"
import { usePageTitle } from "@/hooks/usePageTitle"
import { ArticleCardView } from "@/components/shared/ArticleCardView"
import { EmptyState } from "@/components/ui/EmptyState"
import { ErrorState } from "@/components/ui/ErrorState"
import { Pagination } from "@/components/ui/Pagination"
import { Select } from "@/components/ui/Select"
import { listPublished } from "@/services/content"
import type { ArticleFeed } from "@/types/api"
import { discoverArticles } from "@/services/content"

const feeds: ArticleFeed[] = ["latest", "trending", "popular", "discussed", "featured"]

export function ArticlesPage() {
  usePageTitle("Articles")
  const [params, setParams] = useSearchParams()
  const page = Number(params.get("page") || 1)
  const category = params.get("category") || undefined
  const tag = params.get("tag") || undefined
  const featured = params.get("featured")
  const query = useQuery({
    queryKey: ["posts", page, category, tag, featured],
    queryFn: () =>
      listPublished({
        page,
        page_size: 12,
        category,
        tag,
        featured: featured === "true" ? true : undefined,
      }),
  })
  return (
    <main className="mx-auto max-w-6xl px-4 py-10">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className="font-display text-5xl">Articles</h1>
          <p className="mt-2 text-ink-soft">Published work that is public on ANDIKA.</p>
        </div>
        <Select
          className="max-w-48"
          value={featured === "true" ? "featured" : "all"}
          aria-label="Filter articles"
          onChange={(event) => {
            const next = new URLSearchParams(params)
            if (event.target.value === "featured") next.set("featured", "true")
            else next.delete("featured")
            next.delete("page")
            setParams(next)
          }}
        >
          <option value="all">All published</option>
          <option value="featured">Featured</option>
        </Select>
      </div>
      <div className="mt-8">
        {query.isLoading ? <div className="h-64 animate-pulse rounded-3xl bg-line" /> : null}
        {query.error ? <ErrorState error={query.error} onRetry={() => void query.refetch()} /> : null}
        {query.data && query.data.items.length === 0 ? (
          <EmptyState title="Nothing matches" body="Try another category, tag, or remove the featured filter." />
        ) : null}
        <div className="grid gap-8 md:grid-cols-3">
          {query.data?.items.map((article) => (
            <ArticleCardView key={article.id} article={article} />
          ))}
        </div>
        {query.data ? (
          <div className="mt-8">
            <Pagination
              page={query.data.page}
              pageSize={query.data.page_size}
              total={query.data.total}
              onPage={(next) => {
                const updated = new URLSearchParams(params)
                updated.set("page", String(next))
                setParams(updated)
              }}
            />
          </div>
        ) : null}
      </div>
    </main>
  )
}

export function DiscoverPage() {
  const { feed: feedParam = "latest" } = useParams()
  const feed = feeds.includes(feedParam as ArticleFeed) ? (feedParam as ArticleFeed) : "latest"
  const [params, setParams] = useSearchParams()
  const page = Number(params.get("page") || 1)
  usePageTitle(feed)
  const query = useQuery({
    queryKey: ["discovery", feed, page],
    queryFn: () => discoverArticles(feed, page, 12),
  })
  const notes: Record<ArticleFeed, string> = {
    latest: "Newest published articles.",
    trending: "Last 7 days, scored as (views + 3 × approved comments) / (1 + age in days / 7).",
    popular: "All-time recorded views.",
    discussed: "All-time approved comments that were not deleted.",
    featured: "Articles marked featured, newest first.",
  }
  return (
    <main className="mx-auto max-w-6xl px-4 py-10">
      <h1 className="font-display text-5xl capitalize">{feed}</h1>
      <p className="mt-2 max-w-2xl text-ink-soft">{notes[feed]}</p>
      <div className="mt-4 flex flex-wrap gap-2 text-sm">
        {feeds.map((item) => (
          <Link
            key={item}
            to={`/discover/${item}`}
            className={`rounded-full px-3 py-1 ${item === feed ? "bg-brand text-paper-raised" : "border border-line"}`}
          >
            {item}
          </Link>
        ))}
      </div>
      <div className="mt-8 grid gap-8 md:grid-cols-3">
        {query.data?.items.map((article) => (
          <ArticleCardView key={article.id} article={article} />
        ))}
      </div>
      {query.error ? <ErrorState error={query.error} onRetry={() => void query.refetch()} /> : null}
      {query.data && query.data.items.length === 0 ? (
        <EmptyState title="This feed is empty" body="Published articles will appear when the platform has matching records." />
      ) : null}
      {query.data ? (
        <div className="mt-8">
          <Pagination page={query.data.page} pageSize={query.data.page_size} total={query.data.total} onPage={(next) => {
            const updated = new URLSearchParams(params)
            updated.set("page", String(next))
            setParams(updated)
          }} />
        </div>
      ) : null}
    </main>
  )
}
