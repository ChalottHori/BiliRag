import styles from './StatusTag.module.css'

const LABELS: Record<string, string> = {
  pending: '待处理',
  transcribing: '转写中',
  summarizing: '总结中',
  done: '已入库',
  failed: '失败',
}

export default function StatusTag({ status }: { status: string }) {
  const key = status in LABELS ? status : 'pending'
  return <span className={`${styles.tag} ${styles[key]}`}>{LABELS[key]}</span>
}
