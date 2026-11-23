import { useState, type FormEvent, type ReactNode } from "react"
import { Link, useSearchParams } from "react-router"
import { useQuery } from "@tanstack/react-query"
import { ArticleCardView } from "@/components/shared/ArticleCardView"
import { EmptyState } from "@/components/ui/EmptyState"
import { ErrorState } from "@/components/ui/ErrorState"
import { Input } from "@/components/ui/Input"
import { Pagination } from "@/components/ui/Pagination"
import { Select } from "@/components/ui/Select"
import { usePageTitle } from "@/hooks/usePageTitle"
import { displayName } from "@/lib/format"
import { searchContent, suggest } from "@/services/content"
import type { ArticleSort, SearchType } from "@/types/api"

export function SearchPage() {
  const [params, setParams] = useSearchParams()
  const q = params.get("q") ?? ""
  const type = (params.get("type") as SearchType) || "all"
  const sort = (params.get("sort") as ArticleSort) || "relevance"
  const page = Number(params.get("page") || 1)
  const [draft, setDraft] = useState(q)
  const [seenQuery, setSeenQuery] = useState(q)
  if (q !== seenQuery) {
    setSeenQuery(q)
    setDraft(q)
  }
  usePageTitle(q ? `Search ${q}` : "Search")
  const suggestions = useQuery({
    queryKey: ["suggest", draft],
    queryFn: () => suggest(draft),
    enabled: draft.trim().length >= 2,
  })
  const results = useQuery({
    queryKey: ["search", q, type, sort, page, params.get("category"), params.get("tag"), params.get("author"), params.get("publication")],
    queryFn: () =>
      searchContent({
        q,
        type,
        sort,
        page,
        page_size: 12,
        category: params.get("category") || undefined,
        tag: params.get("tag") || undefined,
        author: params.get("author") || undefined,
        publication: params.get("publication") || undefined,
        date_from: params.get("date_from") || undefined,
        date_to: params.get("date_to") || undefined,
      }),
  })

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
    <main className="mx-auto max-w-6xl px-4 py-10">
      <h1 className="font-display text-5xl">Search</h1>
      <form
        className="mt-6 grid gap-3 md:grid-cols-[1fr_180px_180px_auto]"
        onSubmit={(event: FormEvent) => {
          event.preventDefault()
          update({ q: draft.trim() || undefined })
        }}
      >
        <div className="relative">
          <Input value={draft} onChange={(event) => setDraft(event.target.value)} placeholder="Titles, authors, publications" aria-label="Search query" />
          {suggestions.data && suggestions.data.items.length > 0 && draft.trim().length >= 2 ? (
            <ul className="absolute z-10 mt-2 w-full rounded-2xl border border-line bg-paper-raised p-2 shadow-lift">
              {suggestions.data.items.map((item) => (
                <li key={`${item.type}-${item.id}`}>
                  <button
                    type="button"
                    className="w-full rounded-xl px-3 py-2 text-left text-sm hover:bg-line/50"
                    onClick={() => {
                      setDraft(item.label)
                      if (item.type === "article" && item.slug) update({ q: item.label, type: "articles" })
                      else update({ q: item.label, type: item.type === "author" ? "authors" : item.type === "publication" ? "publications" : item.type === "category" ? "categories" : item.type === "tag" ? "tags" : "all" })
                    }}
                  >
                    {item.label} <span className="text-ink-soft">{item.type}</span>
                  </button>
                </li>
              ))}
            </ul>
          ) : null}
        </div>
        <Select aria-label="Result type" value={type} onChange={(event) => update({ type: event.target.value })}>
          {["all", "articles", "authors", "publications", "categories", "tags"].map((item) => (
            <option key={item} value={item}>{item}</option>
          ))}
        </Select>
        <Select aria-label="Sort" value={sort} onChange={(event) => update({ sort: event.target.value })}>
          {["relevance", "newest", "oldest", "most_viewed", "most_commented"].map((item) => (
            <option key={item} value={item}>{item.replaceAll("_", " ")}</option>
          ))}
        </Select>
        <button className="rounded-full bg-brand px-4 text-paper-raised" type="submit">Search</button>
      </form>
      <div className="mt-4 grid gap-3 md:grid-cols-3">
        <Input placeholder="Category slug" defaultValue={params.get("category") ?? ""} onBlur={(event) => update({ category: event.target.value || undefined })} aria-label="Category filter" />
        <Input placeholder="Tag slug" defaultValue={params.get("tag") ?? ""} onBlur={(event) => update({ tag: event.target.value || undefined })} aria-label="Tag filter" />
        <Input placeholder="Author username" defaultValue={params.get("author") ?? ""} onBlur={(event) => update({ author: event.target.value || undefined })} aria-label="Author filter" />
        <Input placeholder="Publication slug" defaultValue={params.get("publication") ?? ""} onBlur={(event) => update({ publication: event.target.value || undefined })} aria-label="Publication filter" />
        <Input type="date" defaultValue={params.get("date_from")?.slice(0, 10) ?? ""} onBlur={(event) => update({ date_from: event.target.value || undefined })} aria-label="Published from" />
        <Input type="date" defaultValue={params.get("date_to")?.slice(0, 10) ?? ""} onBlur={(event) => update({ date_to: event.target.value || undefined })} aria-label="Published to" />
      </div>
      {results.isLoading ? <div className="mt-8 h-40 animate-pulse rounded-3xl bg-line" /> : null}
      {results.error ? <div className="mt-8"><ErrorState error={results.error} onRetry={() => void results.refetch()} /></div> : null}
      {results.data ? (
        <div className="mt-8 grid gap-10">
          {results.data.articles.items.length === 0 &&
          results.data.authors.items.length === 0 &&
          results.data.publications.items.length === 0 &&
          results.data.categories.items.length === 0 &&
          results.data.tags.items.length === 0 ? (
            <EmptyState
              title={q ? "No matches" : "Nothing published yet"}
              body={
                q
                  ? "No public articles, authors, publications, categories, or tags matched this search."
                  : "An empty query asks for the latest public articles. None are published yet."
              }
            />
          ) : null}
          <Section title="Articles" empty={results.data.articles.items.length === 0}>
            <div className="grid gap-6 md:grid-cols-2">
              {results.data.articles.items.map((article) => <ArticleCardView key={article.id} article={article} />)}
            </div>
          </Section>
          <Directory title="Authors" empty={results.data.authors.items.length === 0} items={results.data.authors.items.map((author) => ({ href: `/authors/${author.username}`, label: displayName(author), meta: `${author.article_count} articles` }))} />
          <Directory title="Publications" empty={results.data.publications.items.length === 0} items={results.data.publications.items.map((item) => ({ href: `/publications/${item.slug}`, label: item.name, meta: `${item.article_count} articles` }))} />
          <Directory title="Categories" empty={results.data.categories.items.length === 0} items={results.data.categories.items.map((item) => ({ href: `/categories/${item.slug}`, label: item.name, meta: `${item.article_count} articles` }))} />
          <Directory title="Tags" empty={results.data.tags.items.length === 0} items={results.data.tags.items.map((item) => ({ href: `/tags/${item.slug}`, label: item.name, meta: `${item.article_count} articles` }))} />
          <Pagination page={results.data.articles.page} pageSize={results.data.articles.page_size} total={results.data.articles.total} onPage={(next) => update({ page: String(next) })} />
        </div>
      ) : null}
    </main>
  )
}

function Section({ title, empty, children }: { title: string; empty: boolean; children: ReactNode }) {
  if (empty) return null
  return <section><h2 className="mb-4 font-display text-3xl">{title}</h2>{children}</section>
}

function Directory({ title, empty, items }: { title: string; empty: boolean; items: Array<{ href: string; label: string; meta: string }> }) {
  if (empty) return null
  return (
    <section>
      <h2 className="mb-4 font-display text-3xl">{title}</h2>
      <div className="grid gap-3 md:grid-cols-2">
        {items.map((item) => (
          <Link key={item.href} to={item.href} className="rounded-2xl border border-line bg-paper-raised px-4 py-3">
            <span className="font-medium">{item.label}</span>
            <span className="mt-1 block text-sm text-ink-soft">{item.meta}</span>
          </Link>
        ))}
      </div>
    </section>
  )
}
