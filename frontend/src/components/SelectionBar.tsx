import Button from './ui/Button'
import styles from './SelectionBar.module.css'

interface SelectionBarProps {
  count: number
  onStart: () => void
  onClear: () => void
  disabled?: boolean
  disabledReason?: string
}

export default function SelectionBar({
  count,
  onStart,
  onClear,
  disabled,
  disabledReason,
}: SelectionBarProps) {
  if (count === 0) return null
  return (
    <div className={styles.bar}>
      <span className={styles.count}>已选 {count} 项</span>
      <div className={styles.actions}>
        <Button onClick={onStart} disabled={disabled} title={disabled ? disabledReason : undefined}>
          开始总结
        </Button>
        <Button
          variant="secondary"
          onClick={onClear}
          disabled={disabled}
          title={disabled ? disabledReason : undefined}
        >
          清空范围
        </Button>
      </div>
    </div>
  )
}
