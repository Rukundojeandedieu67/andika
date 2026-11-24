import { describe, expect, it } from "vitest"
import {
  canDecideReview,
  canInviteRole,
  canPublishArticle,
  canRevokeInvitation,
  canStartReview,
  canSubmitOwnArticle,
  canUnpublishArticle,
} from "@/features/publications/publication-desk"

describe("publication permissions", () => {
  it("lets an author submit their own draft and hides editor review", () => {
    expect(canSubmitOwnArticle(true, "draft")).toBe(true)
    expect(canSubmitOwnArticle(false, "draft")).toBe(false)
    expect(canStartReview("author", "submitted")).toBe(false)
    expect(canDecideReview("contributor", "in_review")).toBe(false)
  })

  it("lets an editor review and publish only after approval when review is required", () => {
    expect(canStartReview("editor", "submitted")).toBe(true)
    expect(canDecideReview("owner", "in_review")).toBe(true)
    expect(canPublishArticle({
      publicationId: "pub",
      role: "editor",
      requiresReview: true,
      editorial: "approved",
      status: "draft",
      isAuthor: false,
    })).toBe(true)
    expect(canPublishArticle({
      publicationId: "pub",
      role: "author",
      requiresReview: true,
      editorial: "approved",
      status: "draft",
      isAuthor: true,
    })).toBe(false)
  })

  it("lets an author publish their own article when review is off, and never a contributor", () => {
    expect(canPublishArticle({
      publicationId: "pub",
      role: "author",
      requiresReview: false,
      editorial: "draft",
      status: "draft",
      isAuthor: true,
    })).toBe(true)
    expect(canPublishArticle({
      publicationId: "pub",
      role: "contributor",
      requiresReview: false,
      editorial: "draft",
      status: "draft",
      isAuthor: true,
    })).toBe(false)
    expect(canUnpublishArticle("pub", "contributor", "published")).toBe(false)
    expect(canUnpublishArticle("pub", "editor", "published")).toBe(true)
    expect(canUnpublishArticle(null, undefined, "published")).toBe(true)
  })

  it("limits invitations and revocation to the membership rules", () => {
    expect(canInviteRole("editor", true)).toEqual(["author", "contributor"])
    expect(canInviteRole("editor", false)).toEqual([])
    expect(canInviteRole("author", true)).toEqual([])
    expect(canRevokeInvitation("editor", true, "author", "pending")).toBe(true)
    expect(canRevokeInvitation("editor", true, "editor", "pending")).toBe(false)
    expect(canRevokeInvitation("owner", false, "editor", "pending")).toBe(true)
  })
})
