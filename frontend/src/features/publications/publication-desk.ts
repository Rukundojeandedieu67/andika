import type { EditorialStatus, MembershipRole, PostStatus } from "@/types/api"

const editorRoles = new Set<MembershipRole>(["owner", "editor"])

export function isPublicationEditor(role: MembershipRole | undefined) {
  return role !== undefined && editorRoles.has(role)
}

export function canSubmitOwnArticle(isAuthor: boolean, editorial: EditorialStatus | null) {
  return isAuthor && (editorial === "draft" || editorial === "changes_requested")
}

export function canStartReview(role: MembershipRole | undefined, editorial: EditorialStatus | null) {
  return isPublicationEditor(role) && editorial === "submitted"
}

export function canDecideReview(role: MembershipRole | undefined, editorial: EditorialStatus | null) {
  return isPublicationEditor(role) && (editorial === "submitted" || editorial === "in_review")
}

export function canPublishArticle(input: {
  publicationId: string | null
  role: MembershipRole | undefined
  requiresReview: boolean | undefined
  editorial: EditorialStatus | null
  status: PostStatus
  isAuthor: boolean
}) {
  if (input.status !== "draft") return false
  if (!input.publicationId) return true
  if (input.requiresReview === undefined || !input.role) return false
  if (input.requiresReview) {
    return isPublicationEditor(input.role) && input.editorial === "approved"
  }
  if (isPublicationEditor(input.role)) return true
  return input.role === "author" && input.isAuthor
}

export function canUnpublishArticle(publicationId: string | null, role: MembershipRole | undefined, status: PostStatus) {
  if (status !== "published") return false
  if (!publicationId) return true
  return isPublicationEditor(role)
}

export function canInviteRole(role: MembershipRole | undefined, editorsCanInvite: boolean): Array<"editor" | "author" | "contributor"> {
  if (role === "owner") return ["editor", "author", "contributor"]
  if (role === "editor" && editorsCanInvite) return ["author", "contributor"]
  return []
}

export function canRevokeInvitation(role: MembershipRole | undefined, editorsCanInvite: boolean, invitationRole: string, status: string) {
  if (status !== "pending") return false
  if (role === "owner") return true
  return role === "editor" && editorsCanInvite && invitationRole !== "editor"
}
