import { useCallback } from 'react'
import type { Citation } from '../api/types'
import { useChatStore } from '../stores/chat'

interface StreamFrame {
  type: string
  content?: string
  session_id?: string
  citations?: Citation[]
}

/**
 * 流式问答：`POST /api/chat` 是流式响应，浏览器 `EventSource` 不支持 POST，
 * 因此用 `fetch + ReadableStream` 逐块解析 SSE 帧（Part 0.7 第 2 条）。
 */
export function useChatStream() {
  const addMessage = useChatStore((s) => s.addMessage)
  const appendToLast = useChatStore((s) => s.appendToLast)
  const setLastCitations = useChatStore((s) => s.setLastCitations)
  const finishLastMessage = useChatStore((s) => s.finishLastMessage)
  const setStreaming = useChatStore((s) => s.setStreaming)
  const streaming = useChatStore((s) => s.streaming)

  const send = useCallback(
    async (question: string, sessionId?: string | null) => {
      addMessage({ role: 'user', content: question })
      addMessage({ role: 'assistant', content: '', streaming: true })
      setStreaming(true)

      try {
        const res = await fetch('/api/chat', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ session_id: sessionId ?? null, question }),
        })
        if (!res.ok || !res.body) throw new Error(`chat failed: ${res.status}`)

        const reader = res.body.getReader()
        const decoder = new TextDecoder()
        let buffer = ''

        while (true) {
          const { done, value } = await reader.read()
          if (done) break
          buffer += decoder.decode(value, { stream: true })
          const frames = buffer.split('\n\n')
          buffer = frames.pop() ?? ''
          for (const frame of frames) {
            const line = frame.trim()
            if (!line.startsWith('data: ')) continue
            const payload = line.slice(6).trim()
            if (!payload || payload === '[DONE]') continue
            try {
              const data = JSON.parse(payload) as StreamFrame
              if (data.type === 'delta' && data.content) appendToLast(data.content)
              if (data.type === 'done') {
                if (data.session_id) useChatStore.getState().setSessionId(data.session_id)
                if (data.citations) setLastCitations(data.citations)
              }
            } catch {
              /* 忽略无法解析的帧 */
            }
          }
        }
      } finally {
        finishLastMessage()
        setStreaming(false)
      }
    },
    [addMessage, appendToLast, setLastCitations, finishLastMessage, setStreaming],
  )

  return { send, streaming }
}
