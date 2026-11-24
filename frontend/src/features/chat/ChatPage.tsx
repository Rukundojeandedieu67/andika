import { useState, type FormEvent } from "react"
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { toast } from "sonner"
import { Button } from "@/components/ui/Button"
import { EmptyState } from "@/components/ui/EmptyState"
import { ErrorState } from "@/components/ui/ErrorState"
import { Input } from "@/components/ui/Input"
import { usePageTitle } from "@/hooks/usePageTitle"
import { toApiError } from "@/lib/errors"
import { displayName, formatDateTime } from "@/lib/format"
import { listConversations, listMessages, openConversation, sendMessage } from "@/services/chats"

export function ChatPage() {
  usePageTitle("Messages")
  const queryClient = useQueryClient()
  const [activeId, setActiveId] = useState<string | null>(null)
  const [username, setUsername] = useState("")
  const [body, setBody] = useState("")
  const conversations = useQuery({
    queryKey: ["chats"],
    queryFn: listConversations,
    refetchInterval: 8000,
  })
  const selected = activeId ?? conversations.data?.[0]?.id ?? null
  const messages = useQuery({
    queryKey: ["chats", selected, "messages"],
    queryFn: () => listMessages(selected as string),
    enabled: Boolean(selected),
    refetchInterval: 5000,
  })
  const open = useMutation({
    mutationFn: () => openConversation(username.trim()),
    onSuccess: (conversation) => {
      setUsername("")
      setActiveId(conversation.id)
      void queryClient.invalidateQueries({ queryKey: ["chats"] })
    },
    onError: (error) => toast.error(toApiError(error).message),
  })
  const send = useMutation({
    mutationFn: () => sendMessage(selected as string, body),
    onSuccess: () => {
      setBody("")
      void queryClient.invalidateQueries({ queryKey: ["chats"] })
    },
    onError: (error) => toast.error(toApiError(error).message),
  })

  function start(event: FormEvent) {
    event.preventDefault()
    if (username.trim()) open.mutate()
  }

  function submit(event: FormEvent) {
    event.preventDefault()
    if (selected && body.trim()) send.mutate()
  }

  const current = conversations.data?.find((item) => item.id === selected)

  return (
    <div>
      <h2 className="font-display text-4xl">Messages</h2>
      <p className="mt-2 max-w-2xl text-sm text-ink-soft">
        A conversation is private to the two accounts in it. Messages use public names, not email addresses.
      </p>
      <form onSubmit={start} className="mt-4 flex max-w-xl gap-2">
        <Input
          value={username}
          onChange={(event) => setUsername(event.target.value)}
          placeholder="Username"
          aria-label="Start a chat with a username"
        />
        <Button type="submit" disabled={open.isPending}>Start</Button>
      </form>
      {conversations.error ? <div className="mt-4"><ErrorState error={conversations.error} onRetry={() => void conversations.refetch()} /></div> : null}
      <div className="mt-6 grid overflow-hidden rounded-3xl border border-line bg-paper-raised lg:grid-cols-[280px_1fr]">
        <aside className="border-b border-line lg:border-r lg:border-b-0" aria-label="Conversations">
          {(conversations.data ?? []).map((item) => (
            <button
              key={item.id}
              type="button"
              onClick={() => setActiveId(item.id)}
              className={`block w-full px-4 py-3 text-left ${item.id === selected ? "bg-line/70" : "hover:bg-line/40"}`}
            >
              <p className="font-medium">{displayName(item.other)}</p>
              <p className="truncate text-sm text-ink-soft">{item.last_message || "No messages yet"}</p>
            </button>
          ))}
          {conversations.data && conversations.data.length === 0 ? (
            <p className="p-4 text-sm text-ink-soft">No conversations yet.</p>
          ) : null}
        </aside>
        <section className="flex min-h-96 flex-col">
          {current ? <p className="border-b border-line px-4 py-3 font-display text-2xl">{displayName(current.other)}</p> : null}
          {messages.error ? <ErrorState error={messages.error} onRetry={() => void messages.refetch()} /> : null}
          <div className="flex flex-1 flex-col gap-3 p-4">
            {messages.data?.items.map((item) => (
              <p
                key={item.id}
                className={`max-w-[80%] rounded-2xl px-3 py-2 text-sm ${item.mine ? "ml-auto bg-accent text-white" : "bg-line/70"}`}
              >
                {item.body}
                <span className={`mt-1 block text-xs ${item.mine ? "text-white/80" : "text-ink-soft"}`}>{formatDateTime(item.created_at)}</span>
              </p>
            ))}
            {selected && messages.data && messages.data.items.length === 0 ? (
              <EmptyState title="No messages yet" body="Send the first note in this conversation." />
            ) : null}
          </div>
          {selected ? (
            <form onSubmit={submit} className="flex gap-2 border-t border-line p-3">
              <Input value={body} onChange={(event) => setBody(event.target.value)} aria-label="Message" placeholder="Write a message" />
              <Button type="submit" disabled={send.isPending || body.trim() === ""}>Send</Button>
            </form>
          ) : null}
        </section>
      </div>
    </div>
  )
}
