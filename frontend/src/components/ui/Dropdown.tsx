import * as DropdownMenuPrimitive from '@radix-ui/react-dropdown-menu'
import type { ReactNode } from 'react'
import styles from './Dropdown.module.css'

export interface DropdownItem {
  label: string
  onSelect?: () => void
  danger?: boolean
}

interface DropdownProps {
  trigger: ReactNode
  items: DropdownItem[]
}

export default function Dropdown({ trigger, items }: DropdownProps) {
  return (
    <DropdownMenuPrimitive.Root>
      <DropdownMenuPrimitive.Trigger asChild>{trigger}</DropdownMenuPrimitive.Trigger>
      <DropdownMenuPrimitive.Portal>
        <DropdownMenuPrimitive.Content className={styles.content}>
          {items.map((item) => (
            <DropdownMenuPrimitive.Item
              key={item.label}
              className={item.danger ? styles.itemDanger : styles.item}
              onSelect={item.onSelect}
            >
              {item.label}
            </DropdownMenuPrimitive.Item>
          ))}
        </DropdownMenuPrimitive.Content>
      </DropdownMenuPrimitive.Portal>
    </DropdownMenuPrimitive.Root>
  )
}
