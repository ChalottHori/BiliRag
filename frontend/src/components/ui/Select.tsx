import type { SelectHTMLAttributes } from 'react'
import styles from './Select.module.css'

export default function Select({
  className,
  children,
  ...props
}: SelectHTMLAttributes<HTMLSelectElement>) {
  return (
    <select className={[styles.select, className].filter(Boolean).join(' ')} {...props}>
      {children}
    </select>
  )
}
