import { useState } from "react"
import { useQuery, useQueryClient } from "@tanstack/react-query"
import { toast } from "sonner"
import { EmptyState } from "@/components/ui/EmptyState"
import { ErrorState } from "@/components/ui/ErrorState"
import { Pagination } from "@/components/ui/Pagination"
import { Textarea } from "@/components/ui/Textarea"
import { toApiError } from "@/lib/errors"
import { formatDateTime } from "@/lib/format"
import { deleteComment, editComment, myComments } from "@/services/community"

export function MyCommentsPage() {
  const [page, setPage] = useState(1)
  const queryClient = useQueryClient()
  const query = useQuery({ queryKey: ["my-comments", page], queryFn: () => myComments(page) })
  const refresh = () => void queryClient.invalidateQueries({ queryKey: ["my-comments"] })
  return (
    <div>
      <h2 className="font-display text-4xl">My comments</h2>
      <p className="mt-2 text-sm text-ink-soft">Pending comments stay private until the article author approves them. Authors cannot reject comments.</p>
      {query.isLoading ? <div className="mt-6 h-32 animate-pulse rounded-3xl bg-line" /> : null}
      {query.error ? <ErrorState error={query.error} onRetry={() => void query.refetch()} /> : null}
      <div className="mt-6 grid gap-3">
        {query.data?.items.map((comment) => (
          <OwnComment key={comment.id} id={comment.id} body={comment.body} status={comment.status} createdAt={comment.created_at} onChanged={refresh} />
        ))}
      </div>
      {query.data && query.data.items.length === 0 ? <EmptyState title="No comments yet" body="Comments you write on published articles appear here, including ones still waiting for approval." /> : null}
      {query.data && query.data.total > query.data.page_size ? <div className="mt-6"><Pagination page={query.data.page} pageSize={query.data.page_size} total={query.data.total} onPage={setPage} /></div> : null}
    </div>
  )
}

function OwnComment({
  id,
  body,
  status,
  createdAt,
  onChanged,
}: {
  id: string
  body: string
  status: string
  createdAt: string
  onChanged: () => void
}) {
  const [editing, setEditing] = useState(false)
  const [draft, setDraft] = useState(body)
  return (
    <article className="rounded-2xl border border-line px-4 py-3">
      <p className="text-xs tracking-wide text-accent uppercase">{status.replaceAll("_", " ")}</p>
      {editing ? <Textarea className="mt-2" value={draft} onChange={(event) => setDraft(event.target.value)} maxLength={2000} /> : <p className="mt-2 whitespace-pre-wrap">{body}</p>}
      <p className="mt-2 text-xs text-ink-soft">{formatDateTime(createdAt)}</p>
      <div className="mt-2 flex gap-3 text-sm">
        <button type="button" onClick={() => setEditing((value) => !value)}>{editing ? "Cancel" : "Edit"}</button>
        {editing ? (
          <button
            type="button"
            onClick={() => {
              editComment(id, draft)
                .then(() => {
                  setEditing(false)
                  onChanged()
                })
                .catch((error: unknown) => toast.error(toApiError(error).message))
            }}
          >
            Save
          </button>
        ) : null}
        <button
          type="button"
          className="text-danger"
          onClick={() => {
            if (!window.confirm("Delete this comment?")) return
            deleteComment(id).then(onChanged).catch((error: unknown) => toast.error(toApiError(error).message))
          }}
        >
          Delete
        </button>
      </div>
    </article>
  )
}
