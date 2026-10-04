import { create } from 'zustand'
import type { Citation } from '../api/types'

export interface ChatMessage {
  id?: string
  role: 'user' | 'assistant'
  content: string
  citations?: Citation[]
  streaming?: boolean
}

interface ChatState {
  sessionId: string | null
  messages: ChatMessage[]
  streaming: boolean
  setSessionId: (id: string | null) => void
  addMessage: (message: ChatMessage) => void
  appendToLast: (content: string) => void
  setLastCitations: (citations: Citation[]) => void
  setStreaming: (streaming: boolean) => void
  reset: () => void
}

export const useChatStore = create<ChatState>((set) => ({
  sessionId: null,
  messages: [],
  streaming: false,
  setSessionId: (id) => set({ sessionId: id }),
  addMessage: (message) => set((s) => ({ messages: [...s.messages, message] })),
  appendToLast: (content) =>
    set((s) => {
      const messages = [...s.messages]
      const last = messages[messages.length - 1]
      if (last) {
        messages[messages.length - 1] = { ...last, content: last.content + content }
      }
      return { messages }
    }),
  setLastCitations: (citations) =>
    set((s) => {
      const messages = [...s.messages]
      const last = messages[messages.length - 1]
      if (last) messages[messages.length - 1] = { ...last, citations }
      return { messages }
    }),
  setStreaming: (streaming) => set({ streaming }),
  reset: () => set({ sessionId: null, messages: [], streaming: false }),
}))
