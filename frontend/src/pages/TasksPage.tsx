import { useEffect } from 'react'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { listItems } from '../api/items'
import { getTasks, retryItem } from '../api/summarize'
import StatusTag from '../components/StatusTag'
import Button from '../components/ui/Button'
import { useTaskProgress } from '../hooks/useTaskProgress'
import styles from './TasksPage.module.css'

function StatCard({ label, value, color }: { label: string; value: number; color: string }) {
  return (
    <div className={styles.stat}>
      <span className={styles.statValue} style={{ color }}>
        {value}
      </span>
      <span className={styles.statLabel}>{label}</span>
    </div>
  )
}

export default function TasksPage() {
  const queryClient = useQueryClient()
  const { event } = useTaskProgress()

  const tasksQuery = useQuery({ queryKey: ['tasks'], queryFn: getTasks, refetchInterval: 3000 })
  const itemsQuery = useQuery({
    queryKey: ['tasks-items'],
    queryFn: () => listItems({ page_size: 100 }),
  })

  useEffect(() => {
    if (event) {
      queryClient.invalidateQueries({ queryKey: ['tasks'] })
      queryClient.invalidateQueries({ queryKey: ['tasks-items'] })
    }
  }, [event, queryClient])

  const tasks = tasksQuery.data ?? { total: 0, done: 0, failed: 0, active: [] }
  const items = itemsQuery.data?.items ?? []
  const percent = tasks.total > 0 ? Math.round((tasks.done / tasks.total) * 100) : 0

  const handleRetry = async (id: string) => {
    await retryItem(id)
    queryClient.invalidateQueries({ queryKey: ['tasks-items'] })
  }

  return (
    <div className={styles.page}>
      <div className={styles.stats}>
        <StatCard label="总数" value={tasks.total} color="var(--text-primary)" />
        <StatCard label="完成" value={tasks.done} color="var(--green)" />
        <StatCard label="失败" value={tasks.failed} color="var(--danger)" />
        <StatCard label="进行中" value={tasks.active.length} color="var(--blue)" />
      </div>

      <div className={styles.progressTrack}>
        <div className={styles.progressFill} style={{ width: `${percent}%` }} />
      </div>

      <div className={styles.list}>
        {items.map((item) => (
          <div key={item.id} className={styles.row}>
            <div className={styles.title}>{item.part_title || item.title}</div>
            <StatusTag status={item.status} />
            {item.status === 'failed' && (
              <>
                <span className={styles.error}>{item.error_msg}</span>
                <Button variant="secondary" onClick={() => handleRetry(item.id)}>
                  重试
                </Button>
              </>
            )}
          </div>
        ))}
        {items.length === 0 && <div className={styles.empty}>暂无任务</div>}
      </div>
    </div>
  )
}
