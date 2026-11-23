import { api } from "@/lib/api"
import { visitorId } from "@/lib/visitor"
import type {
  ArticleCard,
  ArticleFeed,
  ArticleSort,
  AuthorCard,
  EditorialPostDetail,
  Page,
  PostRead,
  PostRevision,
  PublicationCard,
  SearchResponse,
  SearchStats,
  SearchType,
  Suggestion,
} from "@/types/api"

export async function listPublished(params: Record<string, string | number | boolean | undefined>) {
  const { data } = await api.get<Page<PostRead>>("/posts", { params })
  return data
}

export async function readPublished(slug: string) {
  const { data } = await api.get<PostRead>(`/posts/${slug}`)
  return data
}

export async function recordView(slug: string) {
  await api.post(`/posts/${slug}/view`, null, {
    headers: { "X-Visitor-Id": visitorId() },
    params: { source: "web" },
  })
}

export async function relatedArticles(postId: string) {
  const { data } = await api.get<Page<ArticleCard>>(`/posts/${postId}/related`)
  return data
}

export async function discoverArticles(feed: ArticleFeed, page = 1, pageSize = 12) {
  const { data } = await api.get<Page<ArticleCard>>("/discovery/articles", {
    params: { feed, page, page_size: pageSize },
  })
  return data
}

export async function discoverAuthors(params: { q?: string; category?: string; page?: number }) {
  const { data } = await api.get<Page<AuthorCard>>("/discovery/authors", { params })
  return data
}

export async function discoverPublications(params: { q?: string; page?: number }) {
  const { data } = await api.get<Page<PublicationCard>>("/discovery/publications", { params })
  return data
}

export async function searchContent(params: {
  q?: string
  type?: SearchType
  category?: string
  tag?: string
  author?: string
  publication?: string
  date_from?: string
  date_to?: string
  sort?: ArticleSort
  page?: number
  page_size?: number
}) {
  const { data } = await api.get<SearchResponse>("/search", { params })
  return data
}

export async function suggest(q: string) {
  const { data } = await api.get<{ query: string; items: Suggestion[] }>("/search/suggestions", {
    params: { q },
  })
  return data
}

export async function searchStats() {
  const { data } = await api.get<SearchStats>("/search/admin/stats")
  return data
}

export async function listMine(params: { page?: number; page_size?: number; search?: string }) {
  const { data } = await api.get<Page<PostRead>>("/posts/mine", { params })
  return data
}

export async function readMine(postId: string) {
  const { data } = await api.get<PostRead>(`/posts/mine/${postId}`)
  return data
}

export async function listAllPosts(params: Record<string, string | number | undefined>) {
  const { data } = await api.get<Page<PostRead>>("/posts/admin/all", { params })
  return data
}

export async function createDraft(payload: Record<string, unknown>) {
  const { data } = await api.post<PostRead>("/posts", payload)
  return data
}

export async function updatePost(postId: string, payload: Record<string, unknown>) {
  const { data } = await api.patch<PostRead>(`/posts/${postId}`, payload)
  return data
}

export async function publishPost(postId: string) {
  const { data } = await api.post<PostRead>(`/posts/${postId}/publish`)
  return data
}

export async function unpublishPost(postId: string) {
  const { data } = await api.post<PostRead>(`/posts/${postId}/unpublish`)
  return data
}

export async function archivePost(postId: string) {
  const { data } = await api.post<PostRead>(`/posts/${postId}/archive`)
  return data
}

export async function deletePost(postId: string) {
  await api.delete(`/posts/${postId}`)
}

export async function listRevisions(postId: string) {
  const { data } = await api.get<PostRevision[]>(`/posts/${postId}/revisions`)
  return data
}

export async function submitPost(postId: string) {
  const { data } = await api.post<PostRead>(`/posts/${postId}/submit`)
  return data
}

export async function startReview(postId: string) {
  const { data } = await api.post<PostRead>(`/posts/${postId}/start-review`)
  return data
}

export async function requestChanges(postId: string, reason: string) {
  const { data } = await api.post<PostRead>(`/posts/${postId}/request-changes`, { reason })
  return data
}

export async function approvePost(postId: string) {
  const { data } = await api.post<PostRead>(`/posts/${postId}/approve`)
  return data
}

export async function editorialPosts(publicationId: string, page = 1, search?: string) {
  const { data } = await api.get<Page<PostRead>>(`/publications/${publicationId}/editorial/posts`, {
    params: { page, page_size: 20, search: search || undefined },
  })
  return data
}

export async function editorialDetail(publicationId: string, postId: string) {
  const { data } = await api.get<EditorialPostDetail>(
    `/publications/${publicationId}/editorial/posts/${postId}`,
  )
  return data
}

export async function editorialSubmissions(publicationId: string, page = 1) {
  const { data } = await api.get<Page<PostRead>>(
    `/publications/${publicationId}/editorial/submissions`,
    { params: { page, page_size: 20 } },
  )
  return data
}
