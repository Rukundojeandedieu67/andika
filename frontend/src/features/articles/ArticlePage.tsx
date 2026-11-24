import { useEffect, useState, type FormEvent } from "react"
import { Link, useNavigate, useParams } from "react-router"
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { toast } from "sonner"
import { ArticleBody } from "@/components/shared/ArticleBody"
import { ArticleCardView } from "@/components/shared/ArticleCardView"
import { ErrorState } from "@/components/ui/ErrorState"
import { Button } from "@/components/ui/Button"
import { Textarea } from "@/components/ui/Textarea"
import { useAuth } from "@/hooks/useAuth"
import { usePageTitle } from "@/hooks/usePageTitle"
import { displayName, formatDate, readingLabel } from "@/lib/format"
import { toApiError } from "@/lib/errors"
import { preferredVariant, resolveMediaUrl } from "@/lib/media-url"
import { readPublished, recordView, relatedArticles } from "@/services/content"
import {
  authorModerate,
  authorModeration,
  authorReports,
  authorReviewReport,
  createComment,
  deleteComment,
  editComment,
  listComments,
  replyToComment,
  reportComment,
} from "@/services/community"
import type { CommentRead, CommentStatus, ReportReason } from "@/types/api"

export function ArticlePage() {
  const { slug = "" } = useParams()
  const navigate = useNavigate()
  usePageTitle(slug || "Article")
  const article = useQuery({
    queryKey: ["article", slug],
    queryFn: () => readPublished(slug),
    enabled: Boolean(slug),
  })

  useEffect(() => {
    if (!article.data) return
    if (article.data.slug !== slug) {
      navigate(`/articles/${article.data.slug}`, { replace: true })
      return
    }
    recordView(article.data.slug).catch(() => undefined)
  }, [article.data, navigate, slug])

  if (article.isLoading) return <main className="mx-auto max-w-3xl px-4 py-16"><div className="h-80 animate-pulse rounded-3xl bg-line" /></main>
  if (article.error || !article.data) {
    return (
      <main className="mx-auto max-w-3xl px-4 py-16">
        <ErrorState error={article.error ?? new Error("Article not found.")} onRetry={() => void article.refetch()} />
      </main>
    )
  }
  const post = article.data
  const image = preferredVariant(post.featured_image_media?.variants) || resolveMediaUrl(post.featured_image)
  return (
    <main className="mx-auto max-w-3xl px-4 py-10">
      {image ? <img src={image} alt={post.featured_image_media?.alt_text || ""} className="mb-8 max-h-[28rem] w-full rounded-3xl object-cover" /> : null}
      <p className="text-sm tracking-[0.16em] text-accent uppercase">{post.category?.name || "Article"}</p>
      <h1 className="mt-3 font-display text-4xl leading-tight break-words sm:text-5xl">{post.title}</h1>
      {post.subtitle ? <p className="mt-4 text-xl text-ink-soft">{post.subtitle}</p> : null}
      <p className="mt-5 text-sm text-ink-soft">
        <Link to={`/authors/${post.author.username}`} className="text-ink">{displayName(post.author)}</Link>
        {" · "}
        {formatDate(post.published_at)}
        {" · "}
        {readingLabel(post.reading_time)}
      </p>
      <div className="mt-8">
        <ArticleBody content={post.content} />
      </div>
      {post.tags.length ? (
        <div className="mt-8 flex flex-wrap gap-2">
          {post.tags.map((tag) => (
            <Link key={tag.id} to={`/tags/${tag.slug}`} className="rounded-full border border-line px-3 py-1 text-sm">
              {tag.name}
            </Link>
          ))}
        </div>
      ) : null}
      <Comments postId={post.id} allow={post.allow_comments} authorId={post.author.id} />
      <Related postId={post.id} />
    </main>
  )
}

function Comments({ postId, allow, authorId }: { postId: string; allow: boolean; authorId: string }) {
  const { user } = useAuth()
  const queryClient = useQueryClient()
  const comments = useQuery({ queryKey: ["comments", postId], queryFn: () => listComments(postId) })
  const [body, setBody] = useState("")
  const create = useMutation({
    mutationFn: () => createComment(postId, body),
    onSuccess: (created) => {
      setBody("")
      toast.success(created.status === "approved" ? "Comment published." : "Comment submitted for approval.")
      void queryClient.invalidateQueries({ queryKey: ["comments", postId] })
    },
    onError: (error) => toast.error(toApiError(error).message),
  })
  return (
    <section className="mt-14 border-t border-line pt-8">
      <h2 className="font-display text-3xl">Discussion</h2>
      <p className="mt-2 text-sm text-ink-soft">Only approved comments are shown. Pending comments stay private until approved.</p>
      {!allow ? <p className="mt-4">Comments are closed on this article.</p> : null}
      {allow && user ? (
        <form
          className="mt-4 grid gap-3"
          onSubmit={(event: FormEvent) => {
            event.preventDefault()
            create.mutate()
          }}
        >
          <Textarea value={body} onChange={(event) => setBody(event.target.value)} maxLength={2000} required placeholder="Write a comment" />
          <Button type="submit" disabled={create.isPending}>Publish comment</Button>
        </form>
      ) : null}
      {allow && !user ? <p className="mt-4"><Link to="/login" className="text-brand">Sign in</Link> to join the discussion.</p> : null}
      <div className="mt-6 grid gap-5">
        {comments.data?.items.map((comment) => (
          <CommentThread key={comment.id} comment={comment} postId={postId} />
        ))}
      </div>
      {user?.id === authorId ? <AuthorModeration postId={postId} /> : null}
    </section>
  )
}

function CommentThread({ comment, postId }: { comment: CommentRead; postId: string }) {
  const { user } = useAuth()
  const queryClient = useQueryClient()
  const [reply, setReply] = useState("")
  const [editing, setEditing] = useState(false)
  const [draft, setDraft] = useState(comment.body)
  const [reason, setReason] = useState<ReportReason>("spam")
  const refresh = () => void queryClient.invalidateQueries({ queryKey: ["comments", postId] })
  const sendReply = useMutation({
    mutationFn: () => replyToComment(postId, comment.id, reply),
    onSuccess: () => {
      setReply("")
      toast.success("Reply sent.")
      refresh()
    },
    onError: (error) => toast.error(toApiError(error).message),
  })
  const save = useMutation({
    mutationFn: () => editComment(comment.id, draft),
    onSuccess: () => {
      setEditing(false)
      refresh()
    },
    onError: (error) => toast.error(toApiError(error).message),
  })
  const remove = useMutation({
    mutationFn: () => deleteComment(comment.id),
    onSuccess: refresh,
    onError: (error) => toast.error(toApiError(error).message),
  })
  const report = useMutation({
    mutationFn: () => reportComment(comment.id, reason),
    onSuccess: () => toast.success("Report sent. The comment stays until a moderator reviews it."),
    onError: (error) => toast.error(toApiError(error).message),
  })
  const mine = user?.id === comment.author.id
  return (
    <article className="rounded-3xl border border-line bg-paper-raised p-4">
      <p className="text-sm">
        <Link to={`/authors/${comment.author.username}`}>{displayName(comment.author)}</Link>
        <span className="text-ink-soft"> · {formatDate(comment.created_at)}{comment.edited_at ? " · edited" : ""}</span>
      </p>
      {editing ? <Textarea className="mt-3" value={draft} onChange={(event) => setDraft(event.target.value)} /> : <p className="mt-2 whitespace-pre-wrap">{comment.body}</p>}
      <div className="mt-3 flex flex-wrap gap-2 text-sm">
        {mine ? (
          <>
            <button type="button" onClick={() => setEditing((value) => !value)}>Edit</button>
            {editing ? <button type="button" onClick={() => save.mutate()}>Save</button> : null}
            <button type="button" onClick={() => { if (window.confirm("Delete this comment?")) remove.mutate() }}>Delete</button>
          </>
        ) : null}
        {user ? (
          <label className="inline-flex items-center gap-2">
            <span className="sr-only">Report reason</span>
            <select value={reason} onChange={(event) => setReason(event.target.value as ReportReason)} className="rounded-full border border-line bg-transparent px-2 py-1">
              <option value="spam">Spam</option>
              <option value="harassment">Harassment</option>
              <option value="hate_speech">Hate speech</option>
              <option value="misinformation">Misinformation</option>
              <option value="inappropriate_content">Inappropriate content</option>
              <option value="other">Other</option>
            </select>
            <button type="button" onClick={() => report.mutate()}>Report</button>
          </label>
        ) : null}
      </div>
      {user ? (
        <form className="mt-3 grid gap-2" onSubmit={(event) => { event.preventDefault(); sendReply.mutate() }}>
          <Textarea value={reply} onChange={(event) => setReply(event.target.value)} placeholder="Reply" />
          <Button type="submit" size="sm" variant="secondary">Reply</Button>
        </form>
      ) : null}
      <div className="mt-4 grid gap-3 border-l border-line pl-4">
        {comment.replies.map((item) => (
          <div key={item.id}>
            <p className="text-sm">{displayName(item.author)} · {formatDate(item.created_at)}</p>
            <p className="whitespace-pre-wrap">{item.body}</p>
          </div>
        ))}
      </div>
    </article>
  )
}

function AuthorModeration({ postId }: { postId: string }) {
  const queryClient = useQueryClient()
  const queue = useQuery({ queryKey: ["moderation", postId], queryFn: () => authorModeration(postId) })
  const reports = useQuery({ queryKey: ["reports", postId], queryFn: () => authorReports(postId) })
  const decide = useMutation({
    mutationFn: ({ id, status }: { id: string; status: CommentStatus }) => authorModerate(postId, id, status),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["moderation", postId] })
      void queryClient.invalidateQueries({ queryKey: ["comments", postId] })
    },
    onError: (error) => toast.error(toApiError(error).message),
  })
  return (
    <div className="mt-8 rounded-3xl border border-line p-4">
      <h3 className="font-display text-2xl">Moderation</h3>
      <p className="text-sm text-ink-soft">Authors can approve or hide comments. Rejection is reserved for administrators.</p>
      <div className="mt-4 grid gap-3">
        {queue.data?.items.map((comment) => (
          <div key={comment.id} className="rounded-2xl bg-paper p-3">
            <p className="text-sm">{comment.status} · {displayName(comment.author)}</p>
            <p className="whitespace-pre-wrap">{comment.deleted_at ? "This comment was removed." : comment.body}</p>
            <div className="mt-2 flex gap-2">
              {comment.status !== "approved" && comment.status !== "rejected" ? (
                <Button size="sm" onClick={() => decide.mutate({ id: comment.id, status: "approved" })}>Approve</Button>
              ) : null}
              {comment.status !== "hidden" && comment.status !== "rejected" ? (
                <Button size="sm" variant="secondary" onClick={() => decide.mutate({ id: comment.id, status: "hidden" })}>Hide</Button>
              ) : null}
            </div>
          </div>
        ))}
      </div>
      <h4 className="mt-6 font-medium">Reports</h4>
      {reports.data?.items.map((report) => (
        <div key={report.id} className="mt-2 text-sm">
          {report.reason} · {report.status} · {displayName(report.reporter)}
          {report.status === "open" ? (
            <span className="ml-2">
              <button type="button" onClick={() => authorReviewReport(postId, report.id, "resolved").then(() => reports.refetch())}>Resolve</button>
              <button type="button" className="ml-2" onClick={() => authorReviewReport(postId, report.id, "dismissed").then(() => reports.refetch())}>Dismiss</button>
            </span>
          ) : null}
        </div>
      ))}
    </div>
  )
}

function Related({ postId }: { postId: string }) {
  const related = useQuery({ queryKey: ["related", postId], queryFn: () => relatedArticles(postId) })
  if (!related.data?.items.length) return null
  return (
    <section className="mt-14">
      <h2 className="font-display text-3xl">Related Articles</h2>
      <div className="mt-6 grid gap-6 sm:grid-cols-3">
        {related.data.items.map((article) => (
          <ArticleCardView key={article.id} article={article} />
        ))}
      </div>
    </section>
  )
}
