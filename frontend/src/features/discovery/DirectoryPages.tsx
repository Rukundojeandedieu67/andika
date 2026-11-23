import { useState } from "react"
import { Link, useParams, useSearchParams } from "react-router"
import { useQuery } from "@tanstack/react-query"
import { ArticleCardView } from "@/components/shared/ArticleCardView"
import { EmptyState } from "@/components/ui/EmptyState"
import { ErrorState } from "@/components/ui/ErrorState"
import { Pagination } from "@/components/ui/Pagination"
import { Avatar } from "@/components/ui/Avatar"
import { displayName } from "@/lib/format"
import { resolveMediaUrl } from "@/lib/media-url"
import { discoverAuthors, searchContent } from "@/services/content"
import { categoryDetail, categoryPosts, categoryTree, listTags, tagDetail, tagPosts } from "@/services/taxonomy"
import { listPublications, publicationBySlug, publicationPosts } from "@/services/publications"

export function AuthorsPage() {
  const [page, setPage] = useState(1)
  const query = useQuery({ queryKey: ["authors", page], queryFn: () => discoverAuthors({ page }) })
  return (
    <main className="mx-auto max-w-6xl px-4 py-10">
      <h1 className="font-display text-5xl">Authors</h1>
      <p className="mt-2 text-ink-soft">Public authors with at least one listed article.</p>
      {query.error ? <ErrorState error={query.error} /> : null}
      <div className="mt-8 grid gap-4 md:grid-cols-2">
        {query.data?.items.map((author) => (
          <Link key={author.id} to={`/authors/${author.username}`} className="flex gap-4 rounded-3xl border border-line bg-paper-raised p-4">
            <Avatar name={displayName(author)} src={author.avatar_url} />
            <span>
              <span className="block font-medium">{displayName(author)}</span>
              <span className="text-sm text-ink-soft">{author.article_count} articles</span>
            </span>
          </Link>
        ))}
      </div>
      {query.data && query.data.items.length === 0 ? <EmptyState title="No public authors yet" body="Authors appear here after they publish a listed article." /> : null}
      {query.data ? <div className="mt-6"><Pagination page={query.data.page} pageSize={query.data.page_size} total={query.data.total} onPage={setPage} /></div> : null}
    </main>
  )
}

export function AuthorPage() {
  const { username = "" } = useParams()
  const [page, setPage] = useState(1)
  const profile = useQuery({
    queryKey: ["author-profile", username],
    queryFn: () => discoverAuthors({ q: username, page: 1 }),
  })
  const articles = useQuery({
    queryKey: ["author-articles", username, page],
    queryFn: () => searchContent({ type: "articles", author: username, page, page_size: 12, sort: "newest" }),
  })
  const author = profile.data?.items.find((item) => item.username.toLowerCase() === username.toLowerCase())
  return (
    <main className="mx-auto max-w-6xl px-4 py-10">
      {profile.isLoading ? <div className="h-32 animate-pulse rounded-3xl bg-line" /> : null}
      {author ? (
        <header className="flex gap-4">
          <Avatar name={displayName(author)} src={author.avatar_url} size={72} />
          <div>
            <h1 className="font-display text-5xl">{displayName(author)}</h1>
            <p className="text-ink-soft">@{author.username}</p>
            {author.bio ? <p className="mt-3 max-w-2xl">{author.bio}</p> : null}
          </div>
        </header>
      ) : profile.data ? (
        <h1 className="font-display text-5xl">@{username}</h1>
      ) : null}
      <div className="mt-8 grid gap-6 md:grid-cols-2">
        {articles.data?.articles.items.map((article) => <ArticleCardView key={article.id} article={article} />)}
      </div>
      {articles.data && articles.data.articles.items.length === 0 ? <EmptyState title="No listed articles" body="This username has no public articles in the current search." /> : null}
      {articles.data ? <div className="mt-6"><Pagination page={articles.data.articles.page} pageSize={articles.data.articles.page_size} total={articles.data.articles.total} onPage={setPage} /></div> : null}
    </main>
  )
}

export function CategoriesPage() {
  const query = useQuery({ queryKey: ["categories"], queryFn: categoryTree })
  return (
    <main className="mx-auto max-w-6xl px-4 py-10">
      <h1 className="font-display text-5xl">Categories</h1>
      {query.error ? <ErrorState error={query.error} /> : null}
      <div className="mt-8 grid gap-4 md:grid-cols-2">
        {(query.data ?? []).map((category) => (
          <Link key={category.id} to={`/categories/${category.slug}`} className="rounded-3xl border border-line bg-paper-raised p-5">
            <h2 className="font-display text-2xl">{category.name}</h2>
            {category.description ? <p className="mt-2 text-ink-soft">{category.description}</p> : null}
            <div className="mt-3 flex flex-wrap gap-2 text-sm">
              {category.children.map((child) => <span key={child.id}>{child.name}</span>)}
            </div>
          </Link>
        ))}
      </div>
    </main>
  )
}

export function CategoryPage() {
  const { slug = "" } = useParams()
  const [page, setPage] = useState(1)
  const detail = useQuery({ queryKey: ["category", slug], queryFn: () => categoryDetail(slug) })
  const posts = useQuery({ queryKey: ["category-posts", slug, page], queryFn: () => categoryPosts(slug, page) })
  return (
    <main className="mx-auto max-w-6xl px-4 py-10">
      {detail.error ? <ErrorState error={detail.error} /> : null}
      <h1 className="font-display text-5xl">{detail.data?.name || slug}</h1>
      {detail.data?.description ? <p className="mt-3 max-w-2xl text-ink-soft">{detail.data.description}</p> : null}
      <div className="mt-8 grid gap-6 md:grid-cols-3">
        {posts.data?.items.map((article) => <ArticleCardView key={article.id} article={article} />)}
      </div>
      {posts.data ? <div className="mt-6"><Pagination page={posts.data.page} pageSize={posts.data.page_size} total={posts.data.total} onPage={setPage} /></div> : null}
    </main>
  )
}

export function TagsPage() {
  const [page, setPage] = useState(1)
  const query = useQuery({ queryKey: ["tags", page], queryFn: () => listTags(page) })
  return (
    <main className="mx-auto max-w-6xl px-4 py-10">
      <h1 className="font-display text-5xl">Tags</h1>
      <p className="mt-2 text-ink-soft">Tags used by at least one published article.</p>
      <div className="mt-8 flex flex-wrap gap-2">
        {query.data?.items.map((tag) => (
          <Link key={tag.id} to={`/tags/${tag.slug}`} className="rounded-full border border-line px-3 py-1.5">{tag.name}</Link>
        ))}
      </div>
      {query.data && query.data.items.length === 0 ? <EmptyState title="No public tags" body="Tags appear after they are used on a published article." /> : null}
      {query.data ? <div className="mt-6"><Pagination page={query.data.page} pageSize={query.data.page_size} total={query.data.total} onPage={setPage} /></div> : null}
    </main>
  )
}

export function TagPage() {
  const { slug = "" } = useParams()
  const [page, setPage] = useState(1)
  const detail = useQuery({ queryKey: ["tag", slug], queryFn: () => tagDetail(slug) })
  const posts = useQuery({ queryKey: ["tag-posts", slug, page], queryFn: () => tagPosts(slug, page) })
  return (
    <main className="mx-auto max-w-6xl px-4 py-10">
      {detail.error ? <ErrorState error={detail.error} /> : null}
      <h1 className="font-display text-5xl">{detail.data?.name || slug}</h1>
      <div className="mt-8 grid gap-6 md:grid-cols-3">
        {posts.data?.items.map((article) => <ArticleCardView key={article.id} article={article} />)}
      </div>
      {posts.data ? <div className="mt-6"><Pagination page={posts.data.page} pageSize={posts.data.page_size} total={posts.data.total} onPage={setPage} /></div> : null}
    </main>
  )
}

export function PublicationsPage() {
  const [params, setParams] = useSearchParams()
  const page = Number(params.get("page") || 1)
  const search = params.get("q") || undefined
  const query = useQuery({ queryKey: ["publications", page, search], queryFn: () => listPublications(page, search) })
  return (
    <main className="mx-auto max-w-6xl px-4 py-10">
      <h1 className="font-display text-5xl">Publications</h1>
      <p className="mt-2 text-ink-soft">Active public publications. Private, suspended, and archived publications stay hidden.</p>
      <div className="mt-8 grid gap-4 md:grid-cols-2">
        {query.data?.items.map((publication) => (
          <Link key={publication.id} to={`/publications/${publication.slug}`} className="overflow-hidden rounded-3xl border border-line bg-paper-raised">
            {publication.cover?.url ? <img src={resolveMediaUrl(publication.cover.url) || ""} alt="" className="h-36 w-full object-cover" /> : null}
            <div className="p-5">
              <h2 className="font-display text-2xl">{publication.name}</h2>
              {publication.description ? <p className="mt-2 text-ink-soft">{publication.description}</p> : null}
            </div>
          </Link>
        ))}
      </div>
      {query.data && query.data.items.length === 0 ? <EmptyState title="No public publications" body="A publication is listed after it is active and public." /> : null}
      {query.data ? <div className="mt-6"><Pagination page={query.data.page} pageSize={query.data.page_size} total={query.data.total} onPage={(next) => setParams({ page: String(next), q: search || "" })} /></div> : null}
    </main>
  )
}

export function PublicationPage() {
  const { slug = "" } = useParams()
  const [page, setPage] = useState(1)
  const publication = useQuery({ queryKey: ["publication", slug], queryFn: () => publicationBySlug(slug) })
  const posts = useQuery({ queryKey: ["publication-posts", slug, page], queryFn: () => publicationPosts(slug, page) })
  return (
    <main className="mx-auto max-w-6xl px-4 py-10">
      {publication.error ? <ErrorState error={publication.error} /> : null}
      {publication.data?.cover?.url ? <img src={resolveMediaUrl(publication.data.cover.url) || ""} alt="" className="h-56 w-full rounded-3xl object-cover" /> : null}
      <h1 className="mt-6 font-display text-5xl">{publication.data?.name || slug}</h1>
      {publication.data?.description ? <p className="mt-3 max-w-2xl">{publication.data.description}</p> : null}
      {publication.data ? <p className="mt-2 text-sm text-ink-soft">Edited by {displayName(publication.data.owner)}</p> : null}
      <div className="mt-8 grid gap-6 md:grid-cols-3">
        {posts.data?.items.map((article) => <ArticleCardView key={article.id} article={article} />)}
      </div>
      {posts.data ? <div className="mt-6"><Pagination page={posts.data.page} pageSize={posts.data.page_size} total={posts.data.total} onPage={setPage} /></div> : null}
    </main>
  )
}
