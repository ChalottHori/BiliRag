import { del, patch, request } from './client'
import type { ChatMessage, ChatSession } from './types'

export interface SearchHit {
  session_id: string
  title: string
  pinned: boolean
  updated_at: string
  hit_count: number
  snippets: string[]
}

export function listSessions(): Promise<ChatSession[]> {
  return request('/api/chat/sessions')
}

export function listMessages(sessionId: string): Promise<ChatMessage[]> {
  return request(`/api/chat/sessions/${sessionId}/messages`)
}

export function patchSession(
  sessionId: string,
  data: { title?: string; pinned?: boolean },
): Promise<ChatSession> {
  return patch(`/api/chat/sessions/${sessionId}`, data)
}

export function deleteSession(sessionId: string): Promise<{ status: string }> {
  return del(`/api/chat/sessions/${sessionId}`)
}

export function searchChat(q: string, page = 1): Promise<{ total: number; items: SearchHit[] }> {
  return request(`/api/chat/search?q=${encodeURIComponent(q)}&page=${page}`)
}

export async function exportSession(sessionId: string): Promise<string> {
  const res = await fetch(`/api/chat/sessions/${sessionId}/export`, { method: 'POST' })
  if (!res.ok) throw new Error(`export failed: ${res.status}`)
  return res.text()
}
