import { useCallback } from 'react'
import type { MouseEvent as ReactMouseEvent } from 'react'

/** 拖拽调宽：返回供分隔条使用的 onMouseDown，拖动时回调 deltaX。 */
export function useResizable(onResize: (deltaX: number) => void) {
  const onMouseDown = useCallback(
    (event: ReactMouseEvent) => {
      event.preventDefault()
      const startX = event.clientX
      const onMove = (e: MouseEvent) => onResize(e.clientX - startX)
      const onUp = () => {
        document.removeEventListener('mousemove', onMove)
        document.removeEventListener('mouseup', onUp)
      }
      document.addEventListener('mousemove', onMove)
      document.addEventListener('mouseup', onUp)
    },
    [onResize],
  )

  return { onMouseDown }
}
