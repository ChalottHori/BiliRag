import Button from './ui/Button'
import styles from './SelectionBar.module.css'

interface SelectionBarProps {
  count: number
  onStart: () => void
  onClear: () => void
}

export default function SelectionBar({ count, onStart, onClear }: SelectionBarProps) {
  if (count === 0) return null
  return (
    <div className={styles.bar}>
      <span className={styles.count}>已选 {count} 项</span>
      <div className={styles.actions}>
        <Button onClick={onStart}>开始总结</Button>
        <Button variant="secondary" onClick={onClear}>
          清空范围
        </Button>
      </div>
    </div>
  )
}
