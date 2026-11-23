import { Link } from "react-router"
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { toast } from "sonner"
import { Button } from "@/components/ui/Button"
import { EmptyState } from "@/components/ui/EmptyState"
import { ErrorState } from "@/components/ui/ErrorState"
import { Pagination } from "@/components/ui/Pagination"
import { formatDateTime } from "@/lib/format"
import { toApiError } from "@/lib/errors"
import { notificationHref } from "@/lib/links"
import {
  deleteNotification,
  markAllRead,
  markRead,
  notificationPreferences,
  notifications,
  updateNotificationPreferences,
} from "@/services/community"
import type { NotificationPreferences } from "@/types/api"
import { useState } from "react"

export function NotificationsPage() {
  const [page, setPage] = useState(1)
  const [unreadOnly, setUnreadOnly] = useState(false)
  const queryClient = useQueryClient()
  const query = useQuery({
    queryKey: ["notifications", page, unreadOnly],
    queryFn: () => notifications({ page, unread_only: unreadOnly }),
  })
  const refresh = () => {
    void queryClient.invalidateQueries({ queryKey: ["notifications"] })
  }
  return (
    <main className="mx-auto max-w-3xl px-4 py-10">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <h1 className="font-display text-5xl">Notifications</h1>
        <div className="flex gap-2">
          <Button variant="secondary" size="sm" onClick={() => setUnreadOnly((value) => !value)}>
            {unreadOnly ? "Show all" : "Unread only"}
          </Button>
          <Button
            size="sm"
            onClick={() =>
              markAllRead()
                .then((result) => {
                  toast.success(`${result.updated} marked read.`)
                  refresh()
                })
                .catch((error: unknown) => toast.error(toApiError(error).message))
            }
          >
            Mark all read
          </Button>
        </div>
      </div>
      <p className="mt-3">
        <Link to="/notifications/preferences" className="text-sm text-brand">
          Preferences
        </Link>
      </p>
      {query.error ? <ErrorState error={query.error} onRetry={() => void query.refetch()} /> : null}
      <div className="mt-6 grid gap-3">
        {query.data?.items.map((item) => {
          const href = notificationHref(item.action_url, item.metadata)
          return (
            <article key={item.id} className="rounded-3xl border border-line bg-paper-raised p-4">
              <p className="text-xs tracking-wide text-accent uppercase">{item.type.replaceAll("_", " ")}</p>
              <h2 className="mt-1 font-medium">{item.title}</h2>
              <p className="text-ink-soft">{item.message}</p>
              <p className="mt-2 text-xs text-ink-soft">{formatDateTime(item.created_at)}{item.is_read ? " · read" : ""}</p>
              <div className="mt-3 flex gap-2">
                {href ? <Link to={href} className="text-sm text-brand">Open</Link> : null}
                {!item.is_read ? (
                  <button type="button" className="text-sm" onClick={() => markRead(item.id).then(refresh).catch((error: unknown) => toast.error(toApiError(error).message))}>
                    Mark read
                  </button>
                ) : null}
                <button type="button" className="text-sm text-danger" onClick={() => deleteNotification(item.id).then(refresh).catch((error: unknown) => toast.error(toApiError(error).message))}>
                  Delete
                </button>
              </div>
            </article>
          )
        })}
      </div>
      {query.data && query.data.items.length === 0 ? (
        <EmptyState title="Inbox is clear" body="New comments, publication events, and editorial decisions appear here." />
      ) : null}
      {query.data ? <div className="mt-6"><Pagination page={query.data.page} pageSize={query.data.page_size} total={query.data.total} onPage={setPage} /></div> : null}
    </main>
  )
}

const preferenceFields: Array<{ key: keyof NotificationPreferences; label: string }> = [
  { key: "in_app_comments", label: "In-app comments" },
  { key: "email_comments", label: "Email comments" },
  { key: "in_app_publications", label: "In-app publications" },
  { key: "email_publications", label: "Email publications" },
  { key: "in_app_editorial", label: "In-app editorial decisions" },
  { key: "email_editorial", label: "Email editorial decisions" },
  { key: "in_app_account", label: "In-app account notices" },
  { key: "email_account", label: "Email account notices" },
]

export function NotificationPreferencesPage() {
  const query = useQuery({ queryKey: ["notification-preferences"], queryFn: notificationPreferences })
  const mutation = useMutation({
    mutationFn: updateNotificationPreferences,
    onSuccess: () => {
      toast.success("Preferences saved.")
      void query.refetch()
    },
    onError: (error) => toast.error(toApiError(error).message),
  })
  return (
    <main className="mx-auto max-w-2xl px-4 py-10">
      <h1 className="font-display text-4xl">Notification preferences</h1>
      <p className="mt-2 text-sm text-ink-soft">Invitation emails are still sent when publication email is off, because they carry the acceptance link.</p>
      {query.error ? <ErrorState error={query.error} /> : null}
      <div className="mt-6 grid gap-3">
        {query.data
          ? preferenceFields.map((field) => (
              <label key={field.key} className="flex items-center justify-between rounded-2xl border border-line px-4 py-3">
                <span>{field.label}</span>
                <input
                  type="checkbox"
                  checked={query.data[field.key]}
                  onChange={(event) => mutation.mutate({ [field.key]: event.target.checked })}
                />
              </label>
            ))
          : null}
      </div>
    </main>
  )
}
