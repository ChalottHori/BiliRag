import type { ButtonHTMLAttributes } from 'react'
import styles from './Chip.module.css'

interface ChipProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  active?: boolean
}

export default function Chip({ active, className, ...props }: ChipProps) {
  const cls = [styles.chip, active ? styles.active : '', className].filter(Boolean).join(' ')
  return <button type="button" className={cls} {...props} />
}
