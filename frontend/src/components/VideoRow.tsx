import { useState } from 'react'
import type { ItemStatus, PartInfo } from '../api/types'
import { formatDuration } from '../utils/format'
import StatusTag from './StatusTag'
import styles from './VideoRow.module.css'

export interface VideoRowData {
  bvid: string
  title: string
  coverUrl: string
  upName: string
  duration: number
  isCollection?: boolean
  isInvalid?: boolean
  parts?: PartInfo[]
  partCount?: number
  partsStatus?: Record<string, ItemStatus>
}

interface VideoRowProps {
  video: VideoRowData
  checked?: boolean
  onToggle?: (checked: boolean) => void
  onExpand?: () => void
  selectedCids?: Set<number>
  onTogglePart?: (part: PartInfo) => void
  onRetry?: (itemId: string) => void
}

export default function VideoRow({
  video,
  checked,
  onToggle,
  onExpand,
  selectedCids,
  onTogglePart,
  onRetry,
}: VideoRowProps) {
  const [expanded, setExpanded] = useState(false)

  const isMulti = (video.partCount ?? 1) > 1
  const statusEntries = Object.values(video.partsStatus ?? {})
  const doneCount = statusEntries.filter((s) => s.status === 'done').length
  const failedCount = statusEntries.filter((s) => s.status === 'failed').length
  const singleStatus = !isMulti ? statusEntries[0] : undefined

  const toggleExpand = () => {
    const next = !expanded
    setExpanded(next)
    if (next) onExpand?.()
  }

  const renderVideoStatus = () => {
    if (isMulti) {
      if (doneCount === 0 && failedCount === 0) return null
      const totalParts = video.partCount ?? statusEntries.length
      return (
        <div className={styles.statusRow}>
          {doneCount > 0 && (
            <span className={styles.importedTag}>
              已入库 {doneCount}/{totalParts}
            </span>
          )}
          {failedCount > 0 && <span className={styles.failedTag}>失败 {failedCount}</span>}
        </div>
      )
    }

    if (singleStatus?.status === 'failed') {
      return (
        <div className={styles.statusRow}>
          <StatusTag status="failed" />
          {onRetry && (
            <button
              type="button"
              className={styles.retryBtn}
              onClick={() => onRetry(singleStatus.item_id)}
            >
              重试
            </button>
          )}
        </div>
      )
    }

    if (singleStatus?.status === 'done') {
      return (
        <div className={styles.statusRow}>
          <StatusTag status="done" />
        </div>
      )
    }

    return null
  }

  return (
    <div className={video.isInvalid ? styles.invalid : ''}>
      <div className={styles.row}>
        <input
          type="checkbox"
          className={styles.checkbox}
          checked={checked}
          disabled={video.isInvalid}
          onChange={(e) => onToggle?.(e.target.checked)}
          aria-label={`选择 ${video.title}`}
        />
        <img className={styles.thumb} src={video.coverUrl} alt="" referrerPolicy="no-referrer" />
        <div className={styles.meta}>
          <div className={styles.title}>{video.title}</div>
          <div className={styles.sub}>
            <span>{formatDuration(video.duration)}</span>
            <span>{video.upName}</span>
          </div>
        </div>
        {renderVideoStatus()}
        {video.isCollection && (
          <button type="button" className={styles.expandBtn} onClick={toggleExpand}>
            {expanded ? '收起' : '展开'}
          </button>
        )}
      </div>

      {expanded && video.parts && (
        <div className={styles.parts}>
          {video.parts.map((part) => {
            const status = video.partsStatus?.[String(part.cid)]
            return (
              <div key={part.cid} className={styles.partRow}>
                {onTogglePart && (
                  <input
                    type="checkbox"
                    className={styles.checkbox}
                    checked={checked || (selectedCids?.has(part.cid) ?? false)}
                    onChange={() => onTogglePart(part)}
                    aria-label={`选择 ${video.title} P${part.page}`}
                  />
                )}
                <span className={styles.partTitle}>
                  P{part.page} · {part.part_title}
                </span>
                <span className={styles.partDuration}>{formatDuration(part.duration)}</span>
                {status?.status === 'done' && <StatusTag status="done" />}
                {status?.status === 'failed' && (
                  <>
                    <StatusTag status="failed" />
                    {onRetry && (
                      <button
                        type="button"
                        className={styles.retryBtn}
                        onClick={() => onRetry(status.item_id)}
                      >
                        重试
                      </button>
                    )}
                  </>
                )}
              </div>
            )
          })}
        </div>
      )}
    </div>
  )
}
