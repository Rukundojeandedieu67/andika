import { api } from "@/lib/api"
import type {
  CategoryAdmin,
  CategoryDetail,
  CategoryNode,
  Page,
  PostRead,
  TagAdmin,
  TagBrief,
} from "@/types/api"

export async function categoryTree() {
  const { data } = await api.get<CategoryNode[]>("/categories")
  return data
}

export async function categoryDetail(slug: string) {
  const { data } = await api.get<CategoryDetail>(`/categories/${slug}`)
  return data
}

export async function categoryPosts(slug: string, page = 1) {
  const { data } = await api.get<Page<PostRead>>(`/categories/${slug}/posts`, {
    params: { page, page_size: 12 },
  })
  return data
}

export async function adminCategories(page = 1) {
  const { data } = await api.get<Page<CategoryAdmin>>("/categories/admin/all", {
    params: { page, page_size: 50 },
  })
  return data
}

export async function createCategory(payload: {
  name: string
  description?: string | null
  parent_id?: string | null
  is_active?: boolean
}) {
  const { data } = await api.post<CategoryAdmin>("/categories", payload)
  return data
}

export async function updateCategory(
  id: string,
  payload: { name?: string; description?: string | null; parent_id?: string | null },
) {
  const { data } = await api.patch<CategoryAdmin>(`/categories/${id}`, payload)
  return data
}

export async function setCategoryStatus(id: string, isActive: boolean) {
  const { data } = await api.patch<CategoryAdmin>(`/categories/admin/${id}/status`, {
    is_active: isActive,
  })
  return data
}

export async function deleteCategory(id: string) {
  await api.delete(`/categories/admin/${id}`)
}

export async function listTags(page = 1) {
  const { data } = await api.get<Page<TagBrief>>("/tags", {
    params: { page, page_size: 40 },
  })
  return data
}

export async function tagDetail(slug: string) {
  const { data } = await api.get<TagBrief>(`/tags/${slug}`)
  return data
}

export async function tagPosts(slug: string, page = 1) {
  const { data } = await api.get<Page<PostRead>>(`/tags/${slug}/posts`, {
    params: { page, page_size: 12 },
  })
  return data
}

export async function createTag(name: string, description?: string) {
  const { data } = await api.post<TagBrief>("/tags", { name, description: description || null })
  return data
}

export async function adminTags(page = 1) {
  const { data } = await api.get<Page<TagAdmin>>("/tags/admin/all", {
    params: { page, page_size: 50 },
  })
  return data
}

export async function updateTag(id: string, payload: { name?: string; description?: string | null }) {
  const { data } = await api.patch<TagAdmin>(`/tags/admin/${id}`, payload)
  return data
}

export async function deleteTag(id: string) {
  await api.delete(`/tags/admin/${id}`)
}
