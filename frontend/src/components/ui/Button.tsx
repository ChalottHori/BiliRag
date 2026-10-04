import type { ButtonHTMLAttributes } from 'react'
import styles from './Button.module.css'

type Variant = 'primary' | 'secondary' | 'ghost'

interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: Variant
}

export default function Button({ variant = 'primary', className, ...props }: ButtonProps) {
  const cls = [styles.button, styles[variant], className].filter(Boolean).join(' ')
  return <button className={cls} {...props} />
}
