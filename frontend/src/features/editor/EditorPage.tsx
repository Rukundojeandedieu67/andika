import { useEffect, useMemo, useRef, useState, type FormEvent } from "react"
import { Link, useBlocker, useNavigate, useParams, useSearchParams } from "react-router"
import { useQuery, useQueryClient } from "@tanstack/react-query"
import { toast } from "sonner"
import { ArticleBody } from "@/components/shared/ArticleBody"
import { Badge } from "@/components/ui/Badge"
import { Button } from "@/components/ui/Button"
import { Field } from "@/components/ui/Field"
import { Input } from "@/components/ui/Input"
import { Select } from "@/components/ui/Select"
import { Textarea } from "@/components/ui/Textarea"
import { useAuth } from "@/hooks/useAuth"
import { usePageTitle } from "@/hooks/usePageTitle"
import { toApiError } from "@/lib/errors"
import { mediaFileError, statusTone } from "@/features/editor/article-desk"
import { preferredVariant } from "@/lib/media-url"
import {
  approvePost,
  archivePost,
  createDraft,
  deletePost,
  listRevisions,
  publishPost,
  readMine,
  requestChanges,
  startReview,
  submitPost,
  unpublishPost,
  updatePost,
} from "@/services/content"
import { editorialDetail } from "@/services/content"
import { myMedia, uploadMedia } from "@/services/media"
import { myPublications } from "@/services/publications"
import { categoryTree, createTag, listTags } from "@/services/taxonomy"
import type { CategoryNode, PostRead } from "@/types/api"

function flatten(nodes: CategoryNode[], prefix = ""): Array<{ id: string; label: string }> {
  return nodes.flatMap((node) => [
    { id: node.id, label: `${prefix}${node.name}` },
    ...flatten(node.children, `${prefix}${node.name} / `),
  ])
}

export function EditorPage() {
  const { id } = useParams()
  const isNew = !id || id === "new"
  const [params] = useSearchParams()
  const publicationHint = params.get("publication")
  const { user } = useAuth()
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const canOwnList = user?.role === "author" || user?.role === "administrator"
  usePageTitle(isNew ? "New article" : "Edit article")
  const existing = useQuery({
    queryKey: ["editor", id, publicationHint],
    enabled: !isNew,
    queryFn: async () => {
      if (publicationHint) return editorialDetail(publicationHint, id!)
      return readMine(id!)
    },
  })
  const categories = useQuery({ queryKey: ["categories"], queryFn: categoryTree })
  const tags = useQuery({ queryKey: ["tags", 1], queryFn: () => listTags(1) })
  const publications = useQuery({
    queryKey: ["my-publications"],
    queryFn: () => myPublications(1),
    enabled: Boolean(user?.is_verified),
  })
  const media = useQuery({
    queryKey: ["media", "mine"],
    queryFn: () => myMedia(1),
    enabled: canOwnList,
  })
  const revisions = useQuery({
    queryKey: ["revisions", id],
    queryFn: () => listRevisions(id!),
    enabled: !isNew && canOwnList,
  })
  const [draft, setDraft] = useState<Partial<PostRead> & { tag_ids?: string[]; publication_id?: string | null }>({})
  const [dirty, setDirty] = useState(false)
  const [preview, setPreview] = useState(false)
  const [progress, setProgress] = useState<number | null>(null)
  const [reason, setReason] = useState("")
  const [tagQuery, setTagQuery] = useState("")
  const [saving, setSaving] = useState(false)
  const contentRef = useRef<HTMLTextAreaElement>(null)
  const blocker = useBlocker(dirty)

  const loaded = existing.data
  const loadedKey = loaded ? `${loaded.id}:${loaded.updated_at}` : ""
  const [syncedKey, setSyncedKey] = useState("")
  if (loaded && loadedKey !== syncedKey) {
    setSyncedKey(loadedKey)
    setDraft({
      ...loaded,
      tag_ids: loaded.tags.map((tag) => tag.id),
      publication_id: loaded.publication_id,
    })
    setDirty(false)
  }

  useEffect(() => {
    if (blocker.state === "blocked") {
      const leave = window.confirm("Leave with unsaved changes?")
      if (leave) blocker.proceed()
      else blocker.reset()
    }
  }, [blocker])

  useEffect(() => {
    const onLeave = (event: BeforeUnloadEvent) => {
      if (!dirty) return
      event.preventDefault()
    }
    window.addEventListener("beforeunload", onLeave)
    return () => window.removeEventListener("beforeunload", onLeave)
  }, [dirty])

  const categoryOptions = useMemo(() => flatten(categories.data ?? []), [categories.data])
  const post = existing.data
  function update(partial: Record<string, unknown>) {
    setDraft((current) => ({ ...current, ...partial }))
    setDirty(true)
  }
  const payload = () => ({
    title: draft.title,
    subtitle: draft.subtitle || null,
    excerpt: draft.excerpt || null,
    content: draft.content ?? "",
    slug: isNew ? undefined : draft.slug,
    category_id: draft.category?.id || null,
    tag_ids: draft.tag_ids ?? [],
    allow_comments: draft.allow_comments ?? true,
    is_featured: draft.is_featured ?? false,
    meta_title: draft.meta_title || null,
    meta_description: draft.meta_description || null,
    featured_image_id: draft.featured_image_media?.id || null,
    publication_id: isNew ? draft.publication_id || null : undefined,
  })
  async function save(event?: FormEvent) {
    event?.preventDefault()
    if (!draft.title?.trim()) {
      toast.error("Title is required.")
      throw new Error("Title is required.")
    }
    setSaving(true)
    try {
      const body = payload()
      const saved = isNew ? await createDraft(body) : await updatePost(id!, body)
      setDirty(false)
      toast.success(isNew ? "Draft created." : "Saved.")
      await queryClient.invalidateQueries({ queryKey: ["mine"] })
      await queryClient.invalidateQueries({ queryKey: ["posts"] })
      if (isNew) navigate(`/workspace/articles/${saved.id}`, { replace: true })
      else {
        await queryClient.invalidateQueries({ queryKey: ["editor", id] })
        await queryClient.invalidateQueries({ queryKey: ["revisions", id] })
      }
      return saved
    } catch (error) {
      if (error instanceof Error && error.message === "Title is required.") throw error
      toast.error(toApiError(error).message)
      throw error
    } finally {
      setSaving(false)
    }
  }
  async function act(action: () => Promise<PostRead>, message: string, confirmText: string) {
    if (!window.confirm(confirmText)) return
    try {
      if (dirty) await save()
      const saved = await action()
      toast.success(message)
      setDraft((current) => ({ ...current, ...saved, tag_ids: saved.tags.map((tag) => tag.id) }))
      setDirty(false)
      await queryClient.invalidateQueries({ queryKey: ["editor", id] })
      await queryClient.invalidateQueries({ queryKey: ["mine"] })
      await queryClient.invalidateQueries({ queryKey: ["posts"] })
      await queryClient.invalidateQueries({ queryKey: ["discovery"] })
      await queryClient.invalidateQueries({ queryKey: ["article", saved.slug] })
    } catch (error) {
      if (error instanceof Error && error.message === "Title is required.") return
      toast.error(toApiError(error).message)
    }
  }
  function format(before: string, after: string) {
    const field = contentRef.current
    const value = draft.content ?? ""
    const start = field?.selectionStart ?? value.length
    const end = field?.selectionEnd ?? value.length
    const selected = value.slice(start, end) || "text"
    const next = `${value.slice(0, start)}${before}${selected}${after}${value.slice(end)}`
    update({ content: next })
    requestAnimationFrame(() => {
      field?.focus()
      const cursor = start + before.length + selected.length + after.length
      field?.setSelectionRange(cursor, cursor)
    })
  }
  if (!isNew && existing.isLoading) return <div className="h-40 animate-pulse rounded-3xl bg-line" />
  if (!isNew && existing.error) return <p>{toApiError(existing.error).message}</p>
  const image = preferredVariant(draft.featured_image_media?.variants)
  return (
    <form className="grid gap-6" onSubmit={(event) => { void save(event).catch(() => undefined) }}>
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h2 className="font-display text-4xl">{isNew ? "New article" : "Edit article"}</h2>
          <p className="mt-1 text-sm text-ink-soft" role="status">
            {saving ? "Saving…" : dirty ? "Unsaved changes" : "Saved"}
            {post ? <> · <Badge tone={statusTone(post.status)}>{post.status}</Badge></> : null}
          </p>
        </div>
        <div className="flex flex-wrap gap-2">
          <Button type="button" variant="secondary" onClick={() => setPreview((value) => !value)}>{preview ? "Edit" : "Preview"}</Button>
          <Button type="submit" disabled={saving}>Save</Button>
          {post?.status === "draft" ? <Button type="button" onClick={() => act(() => publishPost(id!), "Published.", "Publish this draft? Independent articles become public. Publication articles publish only when your membership allows it.")}>Publish</Button> : null}
          {post?.status === "published" ? <Button type="button" variant="secondary" onClick={() => act(() => unpublishPost(id!), "Returned to draft.", "Unpublish this article? It leaves public listings and returns to draft.")}>Unpublish</Button> : null}
          {post && post.status !== "archived" ? <Button type="button" variant="secondary" onClick={() => act(() => archivePost(id!), "Archived.", "Archive this article? It will no longer be public, and the API does not restore archived articles.")}>Archive</Button> : null}
          {post ? (
            <Button type="button" variant="danger" onClick={() => { if (window.confirm("Soft-delete this article? It disappears from public and editorial listings.")) deletePost(id!).then(() => navigate("/workspace/articles")).catch((error: unknown) => toast.error(toApiError(error).message)) }}>
              Delete
            </Button>
          ) : null}
        </div>
      </div>
      {post?.editorial_status ? <p className="text-sm text-ink-soft">Editorial state: {post.editorial_status.replaceAll("_", " ")}</p> : null}
      {post?.status === "archived" ? <p className="text-sm text-ink-soft">This article is archived. The API has no restore transition, so it stays out of public listings.</p> : null}
      {preview ? (
        <article>
          <h1 className="font-display text-5xl">{draft.title || "Untitled"}</h1>
          {draft.excerpt ? <p className="mt-3 text-ink-soft">{draft.excerpt}</p> : null}
          {image ? <img src={image} alt="" className="mt-6 rounded-3xl" /> : null}
          <div className="mt-6"><ArticleBody content={draft.content || ""} /></div>
        </article>
      ) : (
        <>
          <Field label="Title" htmlFor="title"><Input id="title" value={draft.title ?? ""} onChange={(event) => update({ title: event.target.value })} required /></Field>
          {!isNew ? <Field label="Slug" htmlFor="slug" hint="Lowercase letters, numbers, and hyphens. mine and admin are reserved."><Input id="slug" value={draft.slug ?? ""} onChange={(event) => update({ slug: event.target.value })} /></Field> : null}
          <Field label="Subtitle" htmlFor="subtitle"><Input id="subtitle" value={draft.subtitle ?? ""} onChange={(event) => update({ subtitle: event.target.value })} /></Field>
          <Field label="Excerpt" htmlFor="excerpt"><Textarea id="excerpt" value={draft.excerpt ?? ""} maxLength={500} onChange={(event) => update({ excerpt: event.target.value })} /></Field>
          <Field label="Content" htmlFor="content" hint="Stored as plain text. Each save of the title, excerpt, or content keeps a numbered revision, so saving is manual.">
            <div className="mb-2 flex flex-wrap gap-2" role="toolbar" aria-label="Formatting">
              <button type="button" className="rounded-full border border-line px-3 py-1 text-sm" onClick={() => format("**", "**")}>Bold</button>
              <button type="button" className="rounded-full border border-line px-3 py-1 text-sm" onClick={() => format("*", "*")}>Italic</button>
              <button type="button" className="rounded-full border border-line px-3 py-1 text-sm" onClick={() => format("\n## ", "")}>Heading</button>
              <button type="button" className="rounded-full border border-line px-3 py-1 text-sm" onClick={() => format("\n- ", "")}>List</button>
              <button type="button" className="rounded-full border border-line px-3 py-1 text-sm" onClick={() => format("[", "](https://)")}>Link</button>
            </div>
            <Textarea ref={contentRef} id="content" className="min-h-80 font-serif" value={draft.content ?? ""} onChange={(event) => update({ content: event.target.value })} />
          </Field>
          {isNew ? (
            <Field label="Publication" htmlFor="publication" hint="Leave empty for an independent article. Readers who are publication members must choose a publication.">
              <Select id="publication" value={draft.publication_id ?? ""} onChange={(event) => update({ publication_id: event.target.value || null })}>
                <option value="">Independent</option>
                {publications.data?.items.filter((item) => item.membership_status === "active").map((item) => (
                  <option key={item.id} value={item.id}>{item.name} · {item.role}</option>
                ))}
              </Select>
            </Field>
          ) : null}
          <Field label="Category" htmlFor="category">
            <Select id="category" value={draft.category?.id ?? ""} onChange={(event) => {
              const found = categoryOptions.find((item) => item.id === event.target.value)
              update({ category: found ? { id: found.id, name: found.label, slug: "", description: null } : null })
            }}>
              <option value="">None</option>
              {categoryOptions.map((item) => <option key={item.id} value={item.id}>{item.label}</option>)}
            </Select>
          </Field>
          <fieldset>
            <legend className="text-sm font-medium">Tags</legend>
            <Input className="mt-2" value={tagQuery} onChange={(event) => setTagQuery(event.target.value)} aria-label="Find a tag" placeholder="Filter public tags" />
            <div className="mt-2 flex flex-wrap gap-2">
              {tags.data?.items.filter((tag) => tag.name.toLowerCase().includes(tagQuery.trim().toLowerCase())).map((tag) => {
                const selected = draft.tag_ids?.includes(tag.id)
                return (
                  <button key={tag.id} type="button" className={`rounded-full px-3 py-1 text-sm ${selected ? "bg-brand text-paper-raised" : "border border-line"}`} onClick={() => {
                    const current = draft.tag_ids ?? []
                    update({ tag_ids: selected ? current.filter((item) => item !== tag.id) : [...current, tag.id].slice(0, 20) })
                  }}>{tag.name}</button>
                )
              })}
            </div>
            <p className="mt-2 text-xs text-ink-soft">The public list includes tags already used on a published article. A verified author can create another tag. An article can have 20.</p>
            {canOwnList ? (
              <button type="button" className="mt-2 text-sm text-brand" onClick={() => {
                const name = window.prompt("New tag name")
                if (!name) return
                createTag(name).then((tag) => {
                  void queryClient.invalidateQueries({ queryKey: ["tags"] })
                  update({ tag_ids: [...(draft.tag_ids ?? []), tag.id] })
                }).catch((error: unknown) => toast.error(toApiError(error).message))
              }}>Create tag</button>
            ) : null}
          </fieldset>
          <label className="flex items-center gap-2 text-sm"><input type="checkbox" checked={draft.allow_comments ?? true} onChange={(event) => update({ allow_comments: event.target.checked })} /> Allow comments</label>
          <label className="flex items-center gap-2 text-sm"><input type="checkbox" checked={draft.is_featured ?? false} onChange={(event) => update({ is_featured: event.target.checked })} /> Featured</label>
          <Field label="Meta title" htmlFor="meta-title"><Input id="meta-title" maxLength={70} value={draft.meta_title ?? ""} onChange={(event) => update({ meta_title: event.target.value })} /></Field>
          <Field label="Meta description" htmlFor="meta-description"><Textarea id="meta-description" maxLength={160} value={draft.meta_description ?? ""} onChange={(event) => update({ meta_description: event.target.value })} /></Field>
          {canOwnList ? (
            <section>
              <h3 className="font-medium">Featured image</h3>
              <p className="text-sm text-ink-soft">JPEG, PNG, or WebP. Default limit is 10 MB.</p>
              {image ? <img src={image} alt="" className="mt-3 max-h-56 rounded-2xl" /> : null}
              <input className="mt-3 block" type="file" accept="image/jpeg,image/png,image/webp" aria-label="Upload featured image" onChange={(event) => {
                const file = event.target.files?.[0]
                event.target.value = ""
                if (!file) return
                const problem = mediaFileError(file)
                if (problem) {
                  toast.error(problem)
                  return
                }
                setProgress(0)
                uploadMedia(file, {}, setProgress).then((uploaded) => {
                  update({ featured_image_media: uploaded })
                  setProgress(null)
                  toast.success("Image stored. Save the article to attach it as the featured image.")
                  void queryClient.invalidateQueries({ queryKey: ["media"] })
                }).catch((error: unknown) => {
                  setProgress(null)
                  toast.error(toApiError(error).message)
                })
              }} />
              {progress !== null ? <p className="text-sm">Uploading {Math.round(progress * 100)}%</p> : null}
              <div className="mt-3 flex flex-wrap gap-2">
                {media.data?.items.map((item) => (
                  <button key={item.id} type="button" className="overflow-hidden rounded-xl border border-line" onClick={() => update({ featured_image_media: item })}>
                    <img src={preferredVariant(item.variants, ["thumbnail", "medium"]) || ""} alt={item.alt_text || ""} className="h-16 w-16 object-cover" />
                  </button>
                ))}
              </div>
              {draft.featured_image_media ? <button type="button" className="mt-2 text-sm" onClick={() => update({ featured_image_media: null })}>Remove featured image</button> : null}
            </section>
          ) : null}
        </>
      )}
      {post?.publication_id ? (
        <section className="rounded-3xl border border-line p-4">
          <h3 className="font-display text-2xl">Editorial actions</h3>
          <div className="mt-3 flex flex-wrap gap-2">
            {post.editorial_status === "draft" || post.editorial_status === "changes_requested" ? <Button type="button" onClick={() => act(() => submitPost(post.id), "Submitted.", "Submit this article to the publication editors?")}>Submit for review</Button> : null}
            {post.editorial_status === "submitted" ? <Button type="button" onClick={() => act(() => startReview(post.id), "Review started.", "Start review of this submission?")}>Start review</Button> : null}
            {post.editorial_status === "submitted" || post.editorial_status === "in_review" ? (
              <>
                <Input className="max-w-sm" value={reason} onChange={(event) => setReason(event.target.value)} placeholder="Reason for changes" />
                <Button type="button" variant="secondary" onClick={() => act(() => requestChanges(post.id, reason), "Changes requested.", "Send this change request to the author?")}>Request changes</Button>
                <Button type="button" onClick={() => act(() => approvePost(post.id), "Approved.", "Approve this article for publication?")}>Approve</Button>
              </>
            ) : null}
          </div>
          <p className="mt-2 text-sm text-ink-soft">The API rejects transitions the current membership cannot make. Contributors cannot publish.</p>
        </section>
      ) : null}
      {revisions.data && revisions.data.length > 0 ? (
        <section>
          <h3 className="font-display text-2xl">Revisions</h3>
          <ul className="mt-2 grid gap-2 text-sm">
            {revisions.data.map((revision) => (
              <li key={revision.id} className="rounded-2xl border border-line px-3 py-2">
                #{revision.revision_number} · {revision.title}
                <button type="button" className="ml-3 text-brand" onClick={() => update({ title: revision.title, excerpt: revision.excerpt, content: revision.content })}>Load into editor</button>
              </li>
            ))}
          </ul>
        </section>
      ) : null}
      {post?.status === "published" ? <Link to={`/articles/${post.slug}`} className="text-sm text-brand">Open public article</Link> : null}
    </form>
  )
}
