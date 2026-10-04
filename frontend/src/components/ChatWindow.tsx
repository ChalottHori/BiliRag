import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useChatStream } from '../hooks/useChatStream'
import type { ChatMessage } from '../stores/chat'
import { useChatStore } from '../stores/chat'
import Button from './ui/Button'
import styles from './ChatWindow.module.css'

function ChatBubble({ message }: { message: ChatMessage }) {
  const isUser = message.role === 'user'
  return (
    <div className={isUser ? styles.bubbleUser : styles.bubbleAssistant}>
      <div className={styles.bubbleText}>
        {message.content}
        {message.streaming && <span className={styles.cursor}>▌</span>}
      </div>
      {message.citations && message.citations.length > 0 && (
        <div className={styles.citations}>
          {message.citations.map((citation, i) => (
            <span key={i} className={styles.citation}>
              [{i + 1}] {citation.title}
            </span>
          ))}
        </div>
      )}
    </div>
  )
}

export default function ChatWindow() {
  const messages = useChatStore((s) => s.messages)
  const sessionId = useChatStore((s) => s.sessionId)
  const reset = useChatStore((s) => s.reset)
  const { send, streaming } = useChatStream()
  const [input, setInput] = useState('')
  const navigate = useNavigate()

  const submit = () => {
    const question = input.trim()
    if (!question || streaming) return
    setInput('')
    send(question, sessionId)
  }

  return (
    <div className={styles.window}>
      <div className={styles.topbar}>
        <span className={styles.title}>{sessionId ? '当前会话' : '新对话'}</span>
        <div className={styles.topActions}>
          <button type="button" className={styles.iconBtn} onClick={reset} title="新建对话">
            +
          </button>
          <button
            type="button"
            className={styles.iconBtn}
            onClick={() => navigate('/history')}
            title="历史"
          >
            ☰
          </button>
        </div>
      </div>

      <div className={styles.messages}>
        {messages.length === 0 && <div className={styles.empty}>开始提问吧</div>}
        {messages.map((message, i) => (
          <ChatBubble key={i} message={message} />
        ))}
      </div>

      <div className={styles.inputArea}>
        <textarea
          className={styles.input}
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === 'Enter' && !e.shiftKey) {
              e.preventDefault()
              submit()
            }
          }}
          placeholder="输入问题…"
          rows={2}
        />
        <Button onClick={submit} disabled={streaming}>
          发送
        </Button>
      </div>
    </div>
  )
}
