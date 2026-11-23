import { api } from "@/lib/api"
import type {
  CommentOwned,
  CommentRead,
  CommentStatus,
  DeliveryStats,
  ModerationComment,
  ModerationLog,
  NotificationPreferences,
  NotificationRead,
  NotificationType,
  Page,
  ReportRead,
  ReportReason,
  ReportStatus,
} from "@/types/api"

export async function listComments(postId: string, page = 1) {
  const { data } = await api.get<Page<CommentRead>>(`/posts/${postId}/comments`, {
    params: { page, page_size: 20 },
  })
  return data
}

export async function createComment(postId: string, body: string) {
  const { data } = await api.post<CommentOwned>(`/posts/${postId}/comments`, { body })
  return data
}

export async function replyToComment(postId: string, commentId: string, body: string) {
  const { data } = await api.post<CommentOwned>(
    `/posts/${postId}/comments/${commentId}/replies`,
    { body },
  )
  return data
}

export async function myComments(page = 1) {
  const { data } = await api.get<Page<CommentOwned>>("/comments/mine", {
    params: { page, page_size: 20 },
  })
  return data
}

export async function editComment(commentId: string, body: string) {
  const { data } = await api.patch<CommentOwned>(`/comments/${commentId}`, { body })
  return data
}

export async function deleteComment(commentId: string) {
  await api.delete(`/comments/${commentId}`)
}

export async function reportComment(commentId: string, reason: ReportReason, description?: string) {
  const { data } = await api.post<ReportRead>(`/comments/${commentId}/report`, {
    reason,
    description: description || null,
  })
  return data
}

export async function authorModeration(postId: string, page = 1, status?: string) {
  const { data } = await api.get<Page<ModerationComment>>(`/posts/${postId}/moderation/comments`, {
    params: { page, page_size: 20, status },
  })
  return data
}

export async function authorModerate(
  postId: string,
  commentId: string,
  status: CommentStatus,
  reason?: string,
) {
  const { data } = await api.patch<ModerationComment>(
    `/posts/${postId}/moderation/comments/${commentId}/status`,
    { status, reason: reason || null },
  )
  return data
}

export async function authorReports(postId: string, page = 1) {
  const { data } = await api.get<Page<ReportRead>>(`/posts/${postId}/moderation/reports`, {
    params: { page, page_size: 20 },
  })
  return data
}

export async function authorReviewReport(postId: string, reportId: string, status: ReportStatus) {
  const { data } = await api.patch<ReportRead>(
    `/posts/${postId}/moderation/reports/${reportId}`,
    { status },
  )
  return data
}

export async function adminComments(params: Record<string, string | number | undefined>) {
  const { data } = await api.get<Page<ModerationComment>>("/moderation/comments", { params })
  return data
}

export async function adminModerate(commentId: string, status: CommentStatus, reason?: string) {
  const { data } = await api.patch<ModerationComment>(`/moderation/comments/${commentId}/status`, {
    status,
    reason: reason || null,
  })
  return data
}

export async function adminReports(params: Record<string, string | number | undefined>) {
  const { data } = await api.get<Page<ReportRead>>("/moderation/reports", { params })
  return data
}

export async function adminReviewReport(reportId: string, status: ReportStatus) {
  const { data } = await api.patch<ReportRead>(`/moderation/reports/${reportId}`, { status })
  return data
}

export async function moderationLogs(page = 1) {
  const { data } = await api.get<Page<ModerationLog>>("/moderation/logs", {
    params: { page, page_size: 30 },
  })
  return data
}

export async function notifications(params: {
  page?: number
  unread_only?: boolean
  type?: NotificationType
}) {
  const { data } = await api.get<Page<NotificationRead>>("/notifications", {
    params: { page: params.page ?? 1, page_size: 20, unread_only: params.unread_only, type: params.type },
  })
  return data
}

export async function unreadCount() {
  const { data } = await api.get<{ unread: number }>("/notifications/unread-count")
  return data.unread
}

export async function markRead(id: string) {
  const { data } = await api.patch<NotificationRead>(`/notifications/${id}/read`)
  return data
}

export async function markAllRead() {
  const { data } = await api.post<{ updated: number }>("/notifications/read-all")
  return data
}

export async function deleteNotification(id: string) {
  await api.delete(`/notifications/${id}`)
}

export async function notificationPreferences() {
  const { data } = await api.get<NotificationPreferences>("/notifications/preferences")
  return data
}

export async function updateNotificationPreferences(payload: Partial<NotificationPreferences>) {
  const { data } = await api.patch<NotificationPreferences>("/notifications/preferences", payload)
  return data
}

export async function deliveryStats() {
  const { data } = await api.get<DeliveryStats>("/notifications/admin/delivery")
  return data
}
