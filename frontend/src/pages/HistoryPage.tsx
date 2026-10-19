import { useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useNavigate } from 'react-router-dom'
import {
  deleteSession,
  exportSession,
  listMessages,
  listSessions,
  patchSession,
  searchChat,
} from '../api/chat'
import { useChatStore } from '../stores/chat'
import Button from '../components/ui/Button'
import Input from '../components/ui/Input'
import styles from './HistoryPage.module.css'

export default function HistoryPage() {
  const queryClient = useQueryClient()
  const navigate = useNavigate()
  const [selectedId, setSelectedId] = useState<string | null>(null)
  const [query, setQuery] = useState('')

  const sessionsQuery = useQuery({ queryKey: ['chat-sessions'], queryFn: listSessions })
  const messagesQuery = useQuery({
    queryKey: ['chat-messages', selectedId],
    queryFn: () => listMessages(selectedId!),
    enabled: !!selectedId,
  })
  const searchQuery = useQuery({
    queryKey: ['chat-search', query],
    queryFn: () => searchChat(query),
    enabled: query.length > 0,
  })

  const deleteMutation = useMutation({
    mutationFn: deleteSession,
    onSuccess: () => {
      setSelectedId(null)
      queryClient.invalidateQueries({ queryKey: ['chat-sessions'] })
    },
  })

  const pinMutation = useMutation({
    mutationFn: ({ id, pinned }: { id: string; pinned: boolean }) => patchSession(id, { pinned }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['chat-sessions'] }),
  })

  const renameMutation = useMutation({
    mutationFn: ({ id, title }: { id: string; title: string }) => patchSession(id, { title }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['chat-sessions'] }),
  })

  const sessions =
    query.length > 0
      ? (searchQuery.data?.items ?? []).map((h) => ({
          id: h.session_id,
          title: h.title,
          pinned: h.pinned,
        }))
      : (sessionsQuery.data ?? [])
  const messages = messagesQuery.data ?? []

  const continueChat = async (id: string) => {
    const chatStore = useChatStore.getState()
    chatStore.reset()
    chatStore.setSessionId(id)
    const msgs = await listMessages(id)
    useChatStore.setState({
      messages: msgs.map((m) => ({
        id: m.id,
        role: m.role === 'user' ? 'user' : 'assistant',
        content: m.content,
        citations: m.citations_json ?? undefined,
        verdict: m.verdict_json ?? undefined,
      })),
    })
    navigate('/folders')
  }

  const handleRename = (id: string) => {
    const current = sessions.find((s) => s.id === id)?.title ?? ''
    const title = window.prompt('重命名会话', current)
    if (title) renameMutation.mutate({ id, title })
  }

  const handleExport = async (id: string) => {
    const text = await exportSession(id)
    const blob = new Blob([text], { type: 'text/markdown' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `session-${id.slice(0, 8)}.md`
    a.click()
    URL.revokeObjectURL(url)
  }

  const selected = sessions.find((s) => s.id === selectedId)

  return (
    <div className={styles.page}>
      <div className={styles.left}>
        <Input value={query} onChange={(e) => setQuery(e.target.value)} placeholder="搜索历史" />
        <div className={styles.sessionList}>
          {sessions.map((s) => (
            <button
              key={s.id}
              type="button"
              className={s.id === selectedId ? styles.sessionActive : styles.session}
              onClick={() => setSelectedId(s.id)}
            >
              {s.pinned ? '★ ' : ''}
              {s.title || '未命名'}
            </button>
          ))}
        </div>
      </div>

      <div className={styles.right}>
        {selectedId ? (
          <>
            <div className={styles.messages}>
              {messages.map((m) => (
                <div
                  key={m.id}
                  className={m.role === 'user' ? styles.msgUser : styles.msgAssistant}
                >
                  <div className={styles.role}>{m.role === 'user' ? '你' : '助手'}</div>
                  <div>{m.content}</div>
                  {m.verdict_json?.verdict === 'fail' && (
                    <div className={styles.verdictTag}>⚠ 部分内容存疑</div>
                  )}
                </div>
              ))}
            </div>
            <div className={styles.actions}>
              <Button variant="secondary" onClick={() => continueChat(selectedId)}>
                续聊
              </Button>
              <Button variant="secondary" onClick={() => handleRename(selectedId)}>
                重命名
              </Button>
              <Button
                variant="secondary"
                onClick={() => pinMutation.mutate({ id: selectedId, pinned: !selected?.pinned })}
              >
                置顶
              </Button>
              <Button variant="secondary" onClick={() => handleExport(selectedId)}>
                导出
              </Button>
              <Button variant="ghost" onClick={() => deleteMutation.mutate(selectedId)}>
                删除
              </Button>
            </div>
          </>
        ) : (
          <div className={styles.empty}>选择一个会话</div>
        )}
      </div>
    </div>
  )
}
