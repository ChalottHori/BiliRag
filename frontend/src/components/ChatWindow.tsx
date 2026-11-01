import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useChatStream } from '../hooks/useChatStream'
import type { Source, VerificationIssue } from '../api/types'
import type { ChatMessage } from '../stores/chat'
import { useChatStore } from '../stores/chat'
import { buildScopeFilter, useSelectionStore } from '../stores/selection'
import Button from './ui/Button'
import styles from './ChatWindow.module.css'

function TraceLine({ message }: { message: ChatMessage }) {
  const trace = message.trace
  if (!trace) return null
  const routeText = trace.label ?? trace.route
  const steps = trace.steps ?? []

  if (steps.length > 0) {
    return (
      <div className={styles.traceLine}>
        {routeText && <div>路由：{routeText}</div>}
        <ol className={styles.stepList}>
          {steps.map((step, i) => (
            <li key={i} className={step.kind === 'tool_call' ? styles.stepCall : styles.stepObs}>
              {step.kind === 'tool_call' ? `🔍 ${step.label}` : `→ ${step.label}`}
            </li>
          ))}
        </ol>
      </div>
    )
  }

  const parts: string[] = []
  if (routeText) parts.push(`路由：${routeText}`)
  if (trace.route === 'vector' && trace.retrieval) {
    const r = trace.retrieval
    parts.push(
      `向量 ${r.vector_count} / 关键词 ${r.keyword_count} → 融合 ${r.final_count}（耗时 ${r.elapsed_ms}ms）`,
    )
  }
  if (parts.length === 0) return null
  return <div className={styles.traceLine}>{parts.join(' · ')}</div>
}

function formatIssue(issue: VerificationIssue): string {
  const reason = issue.reason ? `（${issue.reason}）` : ''
  if (issue.type === 'fabricated_source') return `编造来源：${issue.source ?? ''}${reason}`
  return `无支撑结论：${issue.claim ?? ''}${reason}`
}

function VerdictLine({ message }: { message: ChatMessage }) {
  const verdict = message.verdict
  if (!verdict || verdict.verdict !== 'fail') return null
  return (
    <details className={styles.verdict}>
      <summary className={styles.verdictTitle}>⚠ 部分内容存疑</summary>
      {verdict.issues.length > 0 && (
        <ul className={styles.verdictIssues}>
          {verdict.issues.map((issue, i) => (
            <li key={i}>{formatIssue(issue)}</li>
          ))}
        </ul>
      )}
    </details>
  )
}

function SourceCards({ message }: { message: ChatMessage }) {
  const sources: Source[] =
    message.sources && message.sources.length > 0
      ? message.sources
      : (message.citations ?? []).map((c) => ({
          bvid: c.bvid,
          title: c.title,
          url: `https://www.bilibili.com/video/${c.bvid}`,
          snippet: c.snippet,
        }))
  if (sources.length === 0) return null
  return (
    <div className={styles.sources}>
      {sources.map((src, i) => (
        <a key={i} className={styles.sourceCard} href={src.url} target="_blank" rel="noreferrer">
          <span className={styles.sourceTitle}>
            [{i + 1}] {src.title}
          </span>
          {src.snippet && <span className={styles.sourceSnippet}>{src.snippet}</span>}
        </a>
      ))}
    </div>
  )
}

function ChatBubble({ message }: { message: ChatMessage }) {
  const isUser = message.role === 'user'
  return (
    <div className={isUser ? styles.bubbleUser : styles.bubbleAssistant}>
      <div className={styles.bubbleText}>
        {message.content}
        {message.streaming && <span className={styles.cursor}>▌</span>}
      </div>
      {!isUser && <TraceLine message={message} />}
      {!isUser && <VerdictLine message={message} />}
      {!isUser && <SourceCards message={message} />}
    </div>
  )
}

export default function ChatWindow({ running = false }: { running?: boolean }) {
  const messages = useChatStore((s) => s.messages)
  const sessionId = useChatStore((s) => s.sessionId)
  const reset = useChatStore((s) => s.reset)
  const { send, streaming } = useChatStream()
  const [input, setInput] = useState('')
  const navigate = useNavigate()

  const busy = running || streaming
  const busyReason = streaming ? '回答生成中，检索范围已锁定' : '入库任务进行中，暂不可操作'

  const selected = useSelectionStore((s) => s.selected)
  const selectedFolders = useSelectionStore((s) => s.selectedFolders)
  const timeFrom = useSelectionStore((s) => s.timeFrom)
  const timeTo = useSelectionStore((s) => s.timeTo)

  const folderTitles = Object.values(selectedFolders).map((f) => f.title)
  const bvidCount = new Set(Object.values(selected).map((t) => t.bvid)).size
  const hasScope = folderTitles.length > 0 || bvidCount > 0
  const hasTime = Boolean(timeFrom || timeTo)
  const scopeParts: string[] = []
  if (folderTitles.length > 0) scopeParts.push(folderTitles.map((t) => `收藏夹·${t}`).join('、'))
  if (bvidCount > 0) scopeParts.push(`${bvidCount} 个视频`)
  if (hasTime) scopeParts.push(`${timeFrom || '…'} ~ ${timeTo || '…'}`)
  const scopeLabel = scopeParts.length === 0 ? '全库' : scopeParts.join(' + ')

  const submit = () => {
    const question = input.trim()
    if (!question || streaming) return
    setInput('')
    send(question, sessionId, buildScopeFilter())
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

      <div className={styles.scopeBar}>
        <span className={styles.scopeLabel}>检索范围：{scopeLabel}</span>
        <div className={styles.scopeControls}>
          <input
            type="date"
            className={styles.dateInput}
            value={timeFrom}
            aria-label="开始日期"
            disabled={busy}
            title={busy ? busyReason : undefined}
            onChange={(e) => useSelectionStore.getState().setTimeRange(e.target.value, timeTo)}
          />
          <span className={styles.dateSeparator}>~</span>
          <input
            type="date"
            className={styles.dateInput}
            value={timeTo}
            aria-label="结束日期"
            disabled={busy}
            title={busy ? busyReason : undefined}
            onChange={(e) => useSelectionStore.getState().setTimeRange(timeFrom, e.target.value)}
          />
          {hasTime && (
            <span className={styles.scopeClearWrap} title={busy ? busyReason : undefined}>
              <button
                type="button"
                className={styles.scopeClear}
                disabled={busy}
                onClick={() => useSelectionStore.getState().clearTime()}
              >
                清除时间
              </button>
            </span>
          )}
          {hasScope && (
            <span className={styles.scopeClearWrap} title={busy ? busyReason : undefined}>
              <button
                type="button"
                className={styles.scopeClear}
                disabled={busy}
                onClick={() => useSelectionStore.getState().clear()}
              >
                回到全库
              </button>
            </span>
          )}
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
        <Button onClick={submit} disabled={busy} title={busy ? busyReason : undefined}>
          发送
        </Button>
      </div>
    </div>
  )
}
