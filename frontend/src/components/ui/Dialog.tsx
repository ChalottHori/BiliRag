import * as DialogPrimitive from '@radix-ui/react-dialog'
import type { ReactNode } from 'react'
import styles from './Dialog.module.css'

interface DialogProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  title: string
  children: ReactNode
}

export default function Dialog({ open, onOpenChange, title, children }: DialogProps) {
  return (
    <DialogPrimitive.Root open={open} onOpenChange={onOpenChange}>
      <DialogPrimitive.Portal>
        <DialogPrimitive.Overlay className={styles.overlay} />
        <DialogPrimitive.Content className={styles.content}>
          <div className={styles.header}>
            <DialogPrimitive.Title className={styles.title}>{title}</DialogPrimitive.Title>
            <DialogPrimitive.Close className={styles.close}>✕</DialogPrimitive.Close>
          </div>
          {children}
        </DialogPrimitive.Content>
      </DialogPrimitive.Portal>
    </DialogPrimitive.Root>
  )
}
