import { useState } from "react"
import { Link } from "react-router"
import { useQuery } from "@tanstack/react-query"
import { Button } from "@/components/ui/Button"
import { ErrorState } from "@/components/ui/ErrorState"
import { Input } from "@/components/ui/Input"
import { Select } from "@/components/ui/Select"
import { formatDate, formatNumber, formatRate } from "@/lib/format"
import {
  authorArticles,
  authorOverview,
  authorSeries,
  downloadAuthorExport,
  type AnalyticsQuery,
} from "@/services/analytics"
import type { AnalyticsPeriod } from "@/types/api"

const notes = [
  "Views are stored read events, not unique readers.",
  "Approved comments are not the same as all comments.",
  "Overview totals are all-time. Period metrics use the selected window.",
  "Active users, where shown, are accounts that signed in during the window, not readers.",
]

export function AnalyticsFilters({
  query,
  onChange,
}: {
  query: AnalyticsQuery
  onChange: (query: AnalyticsQuery) => void
}) {
  return (
    <div className="grid gap-3 md:grid-cols-4">
      <Input type="date" aria-label="From" value={query.date_from ?? ""} onChange={(event) => onChange({ ...query, date_from: event.target.value || undefined })} />
      <Input type="date" aria-label="To" value={query.date_to ?? ""} onChange={(event) => onChange({ ...query, date_to: event.target.value || undefined })} />
      <Select aria-label="Period" value={query.period ?? "day"} onChange={(event) => onChange({ ...query, period: event.target.value as AnalyticsPeriod })}>
        <option value="day">Day</option>
        <option value="week">Week</option>
        <option value="month">Month</option>
      </Select>
      <label className="flex items-center gap-2 text-sm">
        <input type="checkbox" checked={Boolean(query.compare)} onChange={(event) => onChange({ ...query, compare: event.target.checked })} />
        Compare previous window
      </label>
    </div>
  )
}

export function AnalyticsNotes({ limitations }: { limitations?: string[] }) {
  return (
    <ul className="mt-4 list-disc pl-5 text-sm text-ink-soft">
      {notes.map((note) => <li key={note}>{note}</li>)}
      {limitations?.map((note) => <li key={note}>{note}</li>)}
    </ul>
  )
}

export function AuthorAnalyticsPage() {
  const [query, setQuery] = useState<AnalyticsQuery>({ period: "day", compare: false, page: 1, sort: "views" })
  const overview = useQuery({ queryKey: ["author-overview", query], queryFn: () => authorOverview(query) })
  const series = useQuery({ queryKey: ["author-series", query], queryFn: () => authorSeries(query) })
  const articles = useQuery({ queryKey: ["author-articles", query], queryFn: () => authorArticles(query) })
  const max = Math.max(1, ...(series.data?.points.map((point) => point.views) ?? [1]))
  return (
    <div>
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h2 className="font-display text-4xl">Author analytics</h2>
        <Button onClick={() => downloadAuthorExport(query).catch((error: unknown) => alert(error instanceof Error ? error.message : "Export failed"))}>Export CSV</Button>
      </div>
      <div className="mt-4"><AnalyticsFilters query={query} onChange={setQuery} /></div>
      {overview.error ? <ErrorState error={overview.error} /> : null}
      {overview.data ? (
        <div className="mt-6 grid gap-4 md:grid-cols-3">
          <Metric label="Published articles" value={overview.data.published_articles} />
          <Metric label="All-time views" value={overview.data.total_views} />
          <Metric label="Period views" value={overview.data.period_views} />
          <Metric label="All-time approved comments" value={overview.data.total_approved_comments} />
          <Metric label="Period approved comments" value={overview.data.period_approved_comments} />
          <Metric label="Average views per article" value={overview.data.average_views_per_article} />
        </div>
      ) : null}
      {overview.data?.comparison ? (
        <p className="mt-3 text-sm text-ink-soft">
          Previous window views: {formatNumber(overview.data.comparison.views)}. Approved comments: {formatNumber(overview.data.comparison.approved_comments)}.
        </p>
      ) : null}
      <div className="mt-6 flex h-36 items-end gap-1" aria-label="Views over time">
        {series.data?.points.map((point) => (
          <div key={point.bucket_start} title={`${point.bucket_start}: ${point.views} views`} className="flex-1 rounded-t bg-brand" style={{ height: `${(point.views / max) * 100}%` }} />
        ))}
      </div>
      <table className="mt-6 w-full text-left text-sm">
        <thead><tr><th>Article</th><th>Views</th><th>Approved comments</th><th>Engagement</th></tr></thead>
        <tbody>
          {articles.data?.items.map((item) => (
            <tr key={item.id} className="border-t border-line">
              <td className="py-2"><Link to={`/articles/${item.slug}`}>{item.title}</Link><span className="block text-xs text-ink-soft">{formatDate(item.published_at)}</span></td>
              <td>{formatNumber(item.views)}</td>
              <td>{formatNumber(item.approved_comments)}</td>
              <td>{formatRate(item.engagement_rate)}</td>
            </tr>
          ))}
        </tbody>
      </table>
      {articles.data ? <p className="mt-2 text-xs text-ink-soft">{articles.data.engagement_rate_formula}</p> : null}
      <AnalyticsNotes limitations={overview.data?.limitations} />
    </div>
  )
}

function Metric({ label, value }: { label: string; value: number }) {
  return (
    <div className="rounded-3xl border border-line p-4">
      <p className="text-sm text-ink-soft">{label}</p>
      <p className="font-display text-3xl">{formatNumber(value)}</p>
    </div>
  )
}
