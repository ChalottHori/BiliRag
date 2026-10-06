import { useEffect, useRef, useState } from 'react'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { getTasks, retryItem } from '../api/summarize'
import StatusTag from './StatusTag'
import styles from './TaskProgressPanel.module.css'

/** 收藏夹页底部的任务进度面板：进度条 + 完成/总数 + 任务列表（状态/失败重试）。 */
export default function TaskProgressPanel() {
  const queryClient = useQueryClient()
  const { data } = useQuery({ queryKey: ['tasks'], queryFn: getTasks, refetchInterval: 3000 })

  const [hiddenBatch, setHiddenBatch] = useState<string | null>(null)
  const [justDone, setJustDone] = useState(false)
  const prevTotalRef = useRef(0)

  useEffect(() => {
    const total = data?.total ?? 0
    if (prevTotalRef.current > 0 && total === 0) {
      setJustDone(true)
      const timer = setTimeout(() => setJustDone(false), 2500)
      return () => clearTimeout(timer)
    }
    prevTotalRef.current = total
  }, [data])

  const snapshot = data && data.total > 0 ? data : null

  const handleRetry = async (itemId: string) => {
    await retryItem(itemId)
    queryClient.invalidateQueries({ queryKey: ['tasks'] })
  }

  if (snapshot && hiddenBatch !== snapshot.batch_id) {
    const percent = snapshot.total > 0 ? Math.round((snapshot.done / snapshot.total) * 100) : 0
    return (
      <div className={styles.panel}>
        <div className={styles.header}>
          <div className={styles.progressTrack}>
            <div className={styles.progressFill} style={{ width: `${percent}%` }} />
          </div>
          <span className={styles.counts}>
            完成 {snapshot.done} / {snapshot.total} · 失败 {snapshot.failed}
          </span>
          <button
            type="button"
            className={styles.close}
            onClick={() => setHiddenBatch(snapshot.batch_id)}
            aria-label="关闭进度"
          >
            ×
          </button>
        </div>
        <ul className={styles.list}>
          {snapshot.items.map((item) => (
            <li key={item.item_id} className={styles.row}>
              <span className={styles.title}>{item.part_title || item.title}</span>
              <StatusTag status={item.status} />
              {item.status === 'failed' && (
                <>
                  <span className={styles.error}>{item.error_msg}</span>
                  <button
                    type="button"
                    className={styles.retry}
                    onClick={() => handleRetry(item.item_id)}
                  >
                    重试
                  </button>
                </>
              )}
            </li>
          ))}
        </ul>
      </div>
    )
  }

  if (justDone) {
    return <div className={styles.doneBanner}>全部处理完成</div>
  }

  return null
}
