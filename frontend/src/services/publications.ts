import { api } from "@/lib/api"
import type {
  InvitationCreated,
  InvitationRead,
  MemberRead,
  Page,
  PostRead,
  PublicationAudit,
  PublicationManage,
  PublicationMineItem,
  PublicationPublic,
} from "@/types/api"

export async function listPublications(page = 1, search?: string) {
  const { data } = await api.get<Page<PublicationPublic>>("/publications", {
    params: { page, page_size: 12, search: search || undefined },
  })
  return data
}

export async function publicationBySlug(slug: string) {
  const { data } = await api.get<PublicationPublic>(`/publications/${slug}`)
  return data
}

export async function publicationPosts(slug: string, page = 1) {
  const { data } = await api.get<Page<PostRead>>(`/publications/${slug}/posts`, {
    params: { page, page_size: 12 },
  })
  return data
}

export async function myPublications(page = 1) {
  const { data } = await api.get<Page<PublicationMineItem>>("/publications/mine", {
    params: { page, page_size: 20 },
  })
  return data
}

export async function createPublication(payload: Record<string, unknown>) {
  const { data } = await api.post<PublicationPublic>("/publications", payload)
  return data
}

export async function managePublication(id: string) {
  const { data } = await api.get<PublicationManage>(`/publications/${id}/manage`)
  return data
}

export async function updatePublication(id: string, payload: Record<string, unknown>) {
  const { data } = await api.patch<PublicationPublic>(`/publications/${id}`, payload)
  return data
}

export async function archivePublication(id: string) {
  const { data } = await api.post<PublicationManage>(`/publications/${id}/archive`)
  return data
}

export async function restorePublication(id: string) {
  const { data } = await api.post<PublicationManage>(`/publications/${id}/restore`)
  return data
}

export async function listMembers(id: string, page = 1) {
  const { data } = await api.get<Page<MemberRead>>(`/publications/${id}/members`, {
    params: { page, page_size: 30 },
  })
  return data
}

export async function changeMemberRole(publicationId: string, memberId: string, role: string) {
  const { data } = await api.patch<MemberRead>(
    `/publications/${publicationId}/members/${memberId}`,
    { role },
  )
  return data
}

export async function suspendMember(publicationId: string, memberId: string) {
  const { data } = await api.post<MemberRead>(
    `/publications/${publicationId}/members/${memberId}/suspend`,
  )
  return data
}

export async function removeMember(publicationId: string, memberId: string) {
  const { data } = await api.post<MemberRead>(
    `/publications/${publicationId}/members/${memberId}/remove`,
  )
  return data
}

export async function transferOwnership(publicationId: string, userId: string) {
  const { data } = await api.post<PublicationManage>(
    `/publications/${publicationId}/transfer-ownership`,
    { user_id: userId },
  )
  return data
}

export async function inviteMember(publicationId: string, email: string, role: string) {
  const { data } = await api.post<InvitationCreated>(`/publications/${publicationId}/invitations`, {
    email,
    role,
  })
  return data
}

export async function listInvitations(publicationId: string, page = 1) {
  const { data } = await api.get<Page<InvitationRead>>(`/publications/${publicationId}/invitations`, {
    params: { page, page_size: 30 },
  })
  return data
}

export async function revokeInvitation(publicationId: string, invitationId: string) {
  const { data } = await api.post<InvitationRead>(
    `/publications/${publicationId}/invitations/${invitationId}/revoke`,
  )
  return data
}

export async function acceptInvitation(token: string) {
  const { data } = await api.post<MemberRead>("/invitations/accept", { token })
  return data
}

export async function auditLogs(publicationId: string, page = 1) {
  const { data } = await api.get<Page<PublicationAudit>>(`/publications/${publicationId}/audit-logs`, {
    params: { page, page_size: 30 },
  })
  return data
}
