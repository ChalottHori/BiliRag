import * as SwitchPrimitive from '@radix-ui/react-switch'
import styles from './Switch.module.css'

interface SwitchProps {
  checked: boolean
  onCheckedChange: (checked: boolean) => void
  id?: string
}

export default function Switch({ checked, onCheckedChange, id }: SwitchProps) {
  return (
    <SwitchPrimitive.Root
      id={id}
      className={styles.root}
      checked={checked}
      onCheckedChange={onCheckedChange}
    >
      <SwitchPrimitive.Thumb className={styles.thumb} />
    </SwitchPrimitive.Root>
  )
}
