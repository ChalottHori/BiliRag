import * as PopoverPrimitive from '@radix-ui/react-popover'
import type { ReactNode } from 'react'
import styles from './Popover.module.css'

interface PopoverProps {
  trigger: ReactNode
  children: ReactNode
}

export default function Popover({ trigger, children }: PopoverProps) {
  return (
    <PopoverPrimitive.Root>
      <PopoverPrimitive.Trigger asChild>{trigger}</PopoverPrimitive.Trigger>
      <PopoverPrimitive.Portal>
        <PopoverPrimitive.Content className={styles.content}>{children}</PopoverPrimitive.Content>
      </PopoverPrimitive.Portal>
    </PopoverPrimitive.Root>
  )
}
