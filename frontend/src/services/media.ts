import { api } from "@/lib/api"
import type { MediaAdminRead, MediaRead, Page } from "@/types/api"

export async function uploadMedia(
  file: File,
  fields: { title?: string; caption?: string; alt_text?: string },
  onProgress?: (ratio: number) => void,
) {
  const form = new FormData()
  form.append("file", file)
  if (fields.title) form.append("title", fields.title)
  if (fields.caption) form.append("caption", fields.caption)
  if (fields.alt_text) form.append("alt_text", fields.alt_text)
  const { data } = await api.post<MediaRead>("/media/upload", form, {
    onUploadProgress: (event) => {
      if (event.total && onProgress) onProgress(event.loaded / event.total)
    },
  })
  return data
}

export async function myMedia(page = 1, search?: string) {
  const { data } = await api.get<Page<MediaRead>>("/media/mine", {
    params: { page, page_size: 24, search: search || undefined },
  })
  return data
}

export async function updateMedia(
  id: string,
  payload: { title?: string | null; caption?: string | null; alt_text?: string | null },
) {
  const { data } = await api.patch<MediaRead>(`/media/${id}`, payload)
  return data
}

export async function deleteMedia(id: string) {
  await api.delete(`/media/${id}`)
}

export async function adminMedia(page = 1) {
  const { data } = await api.get<Page<MediaAdminRead>>("/media/admin/all", {
    params: { page, page_size: 24 },
  })
  return data
}

export async function adminDeleteMedia(id: string) {
  await api.delete(`/media/admin/${id}`)
}
