import { renderHook, waitFor } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import type { ReactNode } from 'react'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { useTasksRunning } from './useTasksRunning'

const { getTasks } = vi.hoisted(() => ({ getTasks: vi.fn() }))
vi.mock('../api/summarize', () => ({ getTasks }))

function wrapper({ children }: { children: ReactNode }) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return <QueryClientProvider client={client}>{children}</QueryClientProvider>
}

describe('useTasksRunning', () => {
  beforeEach(() => {
    getTasks.mockReset()
  })

  it('returns true when there are active (non-terminal) items', async () => {
    getTasks.mockResolvedValue({
      batch_id: 'b1',
      total: 2,
      done: 0,
      failed: 1,
      active: 1,
      items: [],
    })
    const { result } = renderHook(() => useTasksRunning(), { wrapper })
    await waitFor(() => expect(result.current).toBe(true))
  })

  it('returns false when the batch is fully terminal (done/failed)', async () => {
    getTasks.mockResolvedValue({
      batch_id: 'b1',
      total: 2,
      done: 1,
      failed: 1,
      active: 0,
      items: [],
    })
    const { result } = renderHook(() => useTasksRunning(), { wrapper })
    await waitFor(() => expect(result.current).toBe(false))
  })
})
