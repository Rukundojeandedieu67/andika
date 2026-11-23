import { Link } from "react-router"
import { useQuery } from "@tanstack/react-query"
import { usePageTitle } from "@/hooks/usePageTitle"
import { ArticleCardView } from "@/components/shared/ArticleCardView"
import { EmptyState } from "@/components/ui/EmptyState"
import { ErrorState } from "@/components/ui/ErrorState"
import { categoryTree } from "@/services/taxonomy"
import { discoverArticles, discoverPublications } from "@/services/content"

export function HomePage() {
  usePageTitle("ANDIKA")
  const featured = useQuery({
    queryKey: ["discovery", "featured"],
    queryFn: () => discoverArticles("featured", 1, 1),
  })
  const latest = useQuery({
    queryKey: ["discovery", "latest", "home"],
    queryFn: () => discoverArticles("latest", 1, 6),
  })
  const categories = useQuery({ queryKey: ["categories"], queryFn: categoryTree })
  const publications = useQuery({
    queryKey: ["discovery", "publications", "home"],
    queryFn: () => discoverPublications({ page: 1 }),
  })
  const lead = featured.data?.items[0] ?? latest.data?.items[0]
  const rest = (latest.data?.items ?? []).filter((item) => item.id !== lead?.id)

  return (
    <main>
      <section className="mx-auto grid max-w-6xl gap-10 px-4 py-12 lg:grid-cols-[1.2fr_0.8fr] lg:py-20">
        <div>
          <p className="text-sm tracking-[0.22em] text-accent uppercase">A global publishing desk</p>
          <h1 className="mt-4 max-w-xl font-display text-5xl leading-[1.05] md:text-7xl">
            Stories with a newsroom behind them.
          </h1>
          <p className="mt-5 max-w-lg text-lg text-ink-soft">
            Read published work, follow publications, and write with the editorial tools ANDIKA already runs.
          </p>
          <div className="mt-8 flex flex-wrap gap-3">
            <Link to="/articles" className="rounded-full bg-brand px-5 py-3 text-paper-raised">
              Latest articles
            </Link>
            <Link to="/register" className="rounded-full border border-line px-5 py-3">
              Open a reader account
            </Link>
          </div>
        </div>
        <div className="rounded-[2rem] border border-line bg-paper-raised p-6">
          {latest.isLoading ? <div className="h-64 animate-pulse rounded-3xl bg-line" /> : null}
          {latest.error ? <ErrorState error={latest.error} onRetry={() => void latest.refetch()} /> : null}
          {lead ? <ArticleCardView article={lead} /> : null}
          {!latest.isLoading && !latest.error && !lead ? (
            <EmptyState
              title="No published articles yet"
              body="When writers publish, the latest and featured work will appear here from the discovery feeds."
            />
          ) : null}
        </div>
      </section>
      <section className="mx-auto max-w-6xl px-4 py-8">
        <div className="mb-6 flex items-end justify-between">
          <h2 className="font-display text-3xl">Latest</h2>
          <Link to="/discover/latest" className="text-sm text-brand">
            All latest
          </Link>
        </div>
        <div className="grid gap-8 md:grid-cols-3">
          {rest.map((article) => (
            <ArticleCardView key={article.id} article={article} />
          ))}
        </div>
      </section>
      <section className="mx-auto grid max-w-6xl gap-10 px-4 py-10 md:grid-cols-2">
        <div>
          <h2 className="font-display text-3xl">Categories</h2>
          {categories.error ? <ErrorState error={categories.error} /> : null}
          <div className="mt-4 flex flex-wrap gap-2">
            {(categories.data ?? []).map((category) => (
              <Link
                key={category.id}
                to={`/categories/${category.slug}`}
                className="rounded-full border border-line px-3 py-1.5 text-sm hover:border-brand"
              >
                {category.name}
              </Link>
            ))}
          </div>
          {categories.data && categories.data.length === 0 ? (
            <p className="mt-3 text-sm text-ink-soft">No active categories are published yet.</p>
          ) : null}
        </div>
        <div>
          <h2 className="font-display text-3xl">Publications</h2>
          <div className="mt-4 grid gap-3">
            {(publications.data?.items ?? []).slice(0, 4).map((publication) => (
              <Link
                key={publication.id}
                to={`/publications/${publication.slug}`}
                className="rounded-2xl border border-line bg-paper-raised px-4 py-3 hover:border-brand"
              >
                <span className="font-medium">{publication.name}</span>
                <span className="mt-1 block text-sm text-ink-soft">
                  {publication.article_count} published articles
                </span>
              </Link>
            ))}
          </div>
          {publications.data && publications.data.items.length === 0 ? (
            <p className="mt-3 text-sm text-ink-soft">
              Public publications appear after they publish at least one article.
            </p>
          ) : null}
        </div>
      </section>
    </main>
  )
}
