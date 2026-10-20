import type { ButtonHTMLAttributes } from 'react'
import styles from './Button.module.css'

type Variant = 'primary' | 'secondary' | 'ghost'

interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: Variant
}

export default function Button({
  variant = 'primary',
  className,
  disabled,
  title,
  ...props
}: ButtonProps) {
  const cls = [styles.button, styles[variant], className].filter(Boolean).join(' ')
  const button = (
    <button className={cls} disabled={disabled} title={disabled ? undefined : title} {...props} />
  )
  // 禁用元素在部分浏览器不触发 hover，title 不显示；外包一层 span 保证悬停提示可见。
  if (disabled && title) {
    return (
      <span className={styles.disabledWrap} title={title}>
        {button}
      </span>
    )
  }
  return button
}
