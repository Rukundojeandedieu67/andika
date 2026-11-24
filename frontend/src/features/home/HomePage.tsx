import { Link } from "react-router"
import { useQuery } from "@tanstack/react-query"
import { ArticleCardView } from "@/components/shared/ArticleCardView"
import { EmptyState } from "@/components/ui/EmptyState"
import { ErrorState } from "@/components/ui/ErrorState"
import { usePageTitle } from "@/hooks/usePageTitle"
import { displayName, formatDate, readingLabel } from "@/lib/format"
import { resolveMediaUrl } from "@/lib/media-url"
import { discoverArticles, discoverPublications } from "@/services/content"
import { categoryTree } from "@/services/taxonomy"

export function HomePage() {
  usePageTitle("ANDIKA")
  const featured = useQuery({ queryKey: ["discovery", "featured"], queryFn: () => discoverArticles("featured", 1, 1) })
  const latest = useQuery({ queryKey: ["discovery", "latest", "home"], queryFn: () => discoverArticles("latest", 1, 4) })
  const trending = useQuery({ queryKey: ["discovery", "trending", "home"], queryFn: () => discoverArticles("trending", 1, 3) })
  const categories = useQuery({ queryKey: ["categories"], queryFn: categoryTree })
  const publications = useQuery({ queryKey: ["discovery", "publications", "home"], queryFn: () => discoverPublications({ page: 1 }) })
  const lead = featured.data?.items[0] ?? latest.data?.items[0]
  const beside = (latest.data?.items ?? []).find((item) => item.id !== lead?.id)
  const heroImage = lead ? resolveMediaUrl(lead.featured_image) : ""

  return (
    <main>
      <section className="mx-auto grid max-w-6xl items-center gap-8 px-4 py-10 lg:grid-cols-[1.05fr_0.95fr] lg:py-16">
        <div>
          <h1 className="max-w-xl font-display text-5xl leading-[1.02] md:text-6xl">
            Ideas. Knowledge. A More Informed World.
          </h1>
          <p className="mt-4 max-w-md text-ink-soft">
            ANDIKA is a global publishing platform for thoughtful writers, curious readers and vibrant communities.
          </p>
          <Link to="/articles" className="mt-6 inline-flex rounded-full bg-accent px-5 py-3 text-sm font-medium text-white">
            Explore Articles
          </Link>
        </div>
        <Link to={lead ? `/articles/${lead.slug}` : "/articles"} className="relative block min-h-72 overflow-hidden rounded-[2rem]">
          {heroImage ? (
            <img src={heroImage} alt="" className="absolute inset-0 h-full w-full object-cover" />
          ) : (
            <div className="absolute inset-0 bg-gradient-to-br from-[#8f6a45] via-[#3d6b58] to-[#1a3c34]" />
          )}
          <div className="absolute inset-0 bg-gradient-to-t from-black/55 to-black/10" />
          <div className="relative flex min-h-72 items-end p-6 text-white">
            <p className="font-display text-3xl">{lead ? lead.title : "Stories will appear here when writers publish."}</p>
          </div>
        </Link>
      </section>

      <section className="mx-auto grid max-w-6xl gap-8 px-4 py-6 lg:grid-cols-[1.4fr_0.6fr]">
        <div>
          <div className="mb-4 flex items-end justify-between">
            <h2 className="font-display text-3xl">Featured</h2>
            <Link to="/discover/featured" className="text-sm text-ink-soft">View all</Link>
          </div>
          {latest.error ? <ErrorState error={latest.error} onRetry={() => void latest.refetch()} /> : null}
          {beside ? <ArticleCardView article={beside} /> : null}
          {!latest.isLoading && !latest.error && !beside && !lead ? (
            <EmptyState title="No published articles yet" body="When writers publish, featured and latest work appears here from the discovery feeds." />
          ) : null}
        </div>
        <div>
          <div className="mb-4 flex items-end justify-between">
            <h2 className="font-display text-3xl">Trending</h2>
            <Link to="/discover/trending" className="text-sm text-ink-soft">View all</Link>
          </div>
          {trending.error ? <ErrorState error={trending.error} /> : null}
          <ol className="grid gap-4">
            {(trending.data?.items ?? []).map((article, index) => (
              <li key={article.id} className="grid grid-cols-[2rem_1fr] gap-2">
                <span className="font-display text-2xl text-ink-soft">{index + 1}</span>
                <div>
                  <Link to={`/articles/${article.slug}`} className="font-medium hover:text-brand">{article.title}</Link>
                  <p className="text-xs text-ink-soft">{displayName(article.author)} · {formatDate(article.published_at)} · {readingLabel(article.reading_time)}</p>
                </div>
              </li>
            ))}
          </ol>
        </div>
      </section>

      <section className="mx-auto max-w-6xl px-4 py-8">
        <div className="mb-4 flex items-end justify-between">
          <h2 className="font-display text-3xl">Browse by Topic</h2>
          <Link to="/categories" className="text-sm text-ink-soft">View all</Link>
        </div>
        {categories.error ? <ErrorState error={categories.error} /> : null}
        <div className="flex flex-wrap gap-2">
          {(categories.data ?? []).slice(0, 8).map((category) => (
            <Link key={category.id} to={`/categories/${category.slug}`} className="rounded-full border border-line bg-paper-raised px-4 py-2 text-sm">
              {category.name}
            </Link>
          ))}
        </div>
      </section>

      <section className="mx-auto max-w-6xl px-4 py-8">
        <div className="mb-4 flex items-end justify-between">
          <h2 className="font-display text-3xl">Featured Publications</h2>
          <Link to="/publications" className="text-sm text-ink-soft">View all</Link>
        </div>
        {publications.error ? <ErrorState error={publications.error} /> : null}
        <div className="grid gap-4 md:grid-cols-3">
          {(publications.data?.items ?? []).slice(0, 3).map((publication) => (
            <Link key={publication.id} to={`/publications/${publication.slug}`} className="overflow-hidden rounded-3xl border border-line bg-paper-raised">
              <div className="h-36 bg-gradient-to-br from-[#c4a574] via-[#6d8f78] to-[#1a3c34]" />
              <div className="p-4">
                <h3 className="font-display text-2xl">{publication.name}</h3>
                <p className="text-sm text-ink-soft">{publication.article_count} published articles</p>
              </div>
            </Link>
          ))}
        </div>
      </section>
    </main>
  )
}
