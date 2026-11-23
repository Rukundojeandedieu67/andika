import { api } from "@/lib/api"
import type {
  AdminContent,
  AdminOverview,
  AdminTimeSeries,
  AnalyticsPeriod,
  AnalyticsSort,
  ArticlePerformancePage,
  AuthorContributionPage,
  AuthorOverview,
  PublicationArticlePage,
  PublicationOverview,
  TimeSeries,
} from "@/types/api"

export interface AnalyticsQuery {
  date_from?: string
  date_to?: string
  period?: AnalyticsPeriod
  compare?: boolean
  page?: number
  page_size?: number
  sort?: AnalyticsSort
}

function params(query: AnalyticsQuery) {
  return {
    date_from: query.date_from || undefined,
    date_to: query.date_to || undefined,
    period: query.period,
    compare: query.compare,
    page: query.page,
    page_size: query.page_size,
    sort: query.sort,
  }
}

export async function authorOverview(query: AnalyticsQuery) {
  const { data } = await api.get<AuthorOverview>("/analytics/author/overview", { params: params(query) })
  return data
}

export async function authorArticles(query: AnalyticsQuery) {
  const { data } = await api.get<ArticlePerformancePage>("/analytics/author/articles", {
    params: params(query),
  })
  return data
}

export async function authorSeries(query: AnalyticsQuery) {
  const { data } = await api.get<TimeSeries>("/analytics/author/timeseries", { params: params(query) })
  return data
}

export async function downloadAuthorExport(query: AnalyticsQuery) {
  const response = await api.get<Blob>("/analytics/author/export", {
    params: params(query),
    responseType: "blob",
  })
  saveCsv(response.data, "andika-author-analytics.csv", response.headers["x-andika-export-truncated"])
}

export async function publicationOverview(id: string, query: AnalyticsQuery) {
  const { data } = await api.get<PublicationOverview>(`/analytics/publications/${id}/overview`, {
    params: params(query),
  })
  return data
}

export async function publicationArticles(id: string, query: AnalyticsQuery) {
  const { data } = await api.get<PublicationArticlePage>(`/analytics/publications/${id}/articles`, {
    params: params(query),
  })
  return data
}

export async function publicationAuthors(id: string, query: AnalyticsQuery) {
  const { data } = await api.get<AuthorContributionPage>(`/analytics/publications/${id}/authors`, {
    params: params(query),
  })
  return data
}

export async function downloadPublicationExport(id: string, query: AnalyticsQuery) {
  const response = await api.get<Blob>(`/analytics/publications/${id}/export`, {
    params: params(query),
    responseType: "blob",
  })
  saveCsv(
    response.data,
    "andika-publication-analytics.csv",
    response.headers["x-andika-export-truncated"],
  )
}

export async function adminOverview(query: AnalyticsQuery) {
  const { data } = await api.get<AdminOverview>("/analytics/admin/overview", { params: params(query) })
  return data
}

export async function adminSeries(query: AnalyticsQuery) {
  const { data } = await api.get<AdminTimeSeries>("/analytics/admin/timeseries", {
    params: params(query),
  })
  return data
}

export async function adminContent(query: AnalyticsQuery) {
  const { data } = await api.get<AdminContent>("/analytics/admin/content", { params: params(query) })
  return data
}

export async function downloadAdminExport(query: AnalyticsQuery) {
  const response = await api.get<Blob>("/analytics/admin/export", {
    params: params(query),
    responseType: "blob",
  })
  saveCsv(response.data, "andika-admin-analytics.csv", response.headers["x-andika-export-truncated"])
}

function saveCsv(blob: Blob, filename: string, truncated: unknown) {
  const url = URL.createObjectURL(blob)
  const link = document.createElement("a")
  link.href = url
  link.download = filename
  link.click()
  URL.revokeObjectURL(url)
  if (truncated === "true") {
    throw new Error("The export was truncated at the server limit of 5,000 articles.")
  }
}
