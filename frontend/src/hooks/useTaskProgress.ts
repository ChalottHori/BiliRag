import { useEffect, useState } from 'react'

export interface TaskEvent {
  type: string
  item_id?: string
  status?: string
  error?: string
}

/** 订阅后端进度事件（SSE，`GET /api/events`，用 EventSource）。 */
export function useTaskProgress() {
  const [event, setEvent] = useState<TaskEvent | null>(null)
  const [connected, setConnected] = useState(false)

  useEffect(() => {
    const source = new EventSource('/api/events')
    source.onopen = () => setConnected(true)
    source.onmessage = (e) => {
      try {
        setEvent(JSON.parse(e.data) as TaskEvent)
      } catch {
        /* 忽略无法解析的帧 */
      }
    }
    source.onerror = () => setConnected(false)
    return () => source.close()
  }, [])

  return { event, connected }
}
