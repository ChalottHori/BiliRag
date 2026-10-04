import * as TabsPrimitive from '@radix-ui/react-tabs'
import type { ReactNode } from 'react'
import styles from './Tabs.module.css'

export interface TabItem {
  value: string
  label: string
}

interface TabsProps {
  value: string
  onValueChange: (value: string) => void
  items: TabItem[]
  children: ReactNode
}

export default function Tabs({ value, onValueChange, items, children }: TabsProps) {
  return (
    <TabsPrimitive.Root value={value} onValueChange={onValueChange}>
      <TabsPrimitive.List className={styles.list}>
        {items.map((item) => (
          <TabsPrimitive.Trigger key={item.value} value={item.value} className={styles.trigger}>
            {item.label}
          </TabsPrimitive.Trigger>
        ))}
      </TabsPrimitive.List>
      {children}
    </TabsPrimitive.Root>
  )
}

export function TabsContent({ value, children }: { value: string; children: ReactNode }) {
  return <TabsPrimitive.Content value={value}>{children}</TabsPrimitive.Content>
}
