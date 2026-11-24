import { api } from "@/lib/api"
import type { AuthorPublic, Page } from "@/types/api"

export interface Conversation {
  id: string
  other: AuthorPublic
  last_message: string | null
  last_message_at: string | null
  updated_at: string
}

export interface ChatMessage {
  id: string
  conversation_id: string
  body: string
  created_at: string
  sender: AuthorPublic
  mine: boolean
}

export async function listConversations() {
  const { data } = await api.get<Conversation[]>("/chats")
  return data
}

export async function openConversation(username: string) {
  const { data } = await api.post<Conversation>("/chats", { username })
  return data
}

export async function listMessages(conversationId: string, page = 1) {
  const { data } = await api.get<Page<ChatMessage>>(`/chats/${conversationId}/messages`, {
    params: { page, page_size: 50 },
  })
  return data
}

export async function sendMessage(conversationId: string, body: string) {
  const { data } = await api.post<ChatMessage>(`/chats/${conversationId}/messages`, { body })
  return data
}
