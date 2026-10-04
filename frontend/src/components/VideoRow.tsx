import { useState } from 'react'
import type { PartInfo } from '../api/types'
import { formatDuration } from '../utils/format'
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
}

interface VideoRowProps {
  video: VideoRowData
  checked?: boolean
  onToggle?: (checked: boolean) => void
  onExpand?: () => void
}

export default function VideoRow({ video, checked, onToggle, onExpand }: VideoRowProps) {
  const [expanded, setExpanded] = useState(false)

  const toggleExpand = () => {
    const next = !expanded
    setExpanded(next)
    if (next) onExpand?.()
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
        <img className={styles.thumb} src={video.coverUrl} alt="" />
        <div className={styles.meta}>
          <div className={styles.title}>{video.title}</div>
          <div className={styles.sub}>
            <span>{formatDuration(video.duration)}</span>
            <span>{video.upName}</span>
          </div>
        </div>
        {video.isCollection && (
          <button type="button" className={styles.expandBtn} onClick={toggleExpand}>
            {expanded ? '收起' : '展开'}
          </button>
        )}
      </div>

      {expanded && video.parts && (
        <div className={styles.parts}>
          {video.parts.map((part) => (
            <div key={part.cid} className={styles.partRow}>
              <span className={styles.partTitle}>
                P{part.page} · {part.part_title}
              </span>
              <span className={styles.partDuration}>{formatDuration(part.duration)}</span>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
