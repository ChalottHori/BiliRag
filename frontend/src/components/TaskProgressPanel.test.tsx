import { fireEvent, render, screen } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import TaskProgressPanel from './TaskProgressPanel'

const { getTasks, retryItem } = vi.hoisted(() => ({
  getTasks: vi.fn(),
  retryItem: vi.fn(),
}))

vi.mock('../api/summarize', () => ({ getTasks, retryItem }))

function renderPanel() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(
    <QueryClientProvider client={client}>
      <TaskProgressPanel />
    </QueryClientProvider>,
  )
}

describe('TaskProgressPanel', () => {
  beforeEach(() => {
    getTasks.mockReset()
    retryItem.mockReset()
  })

  it('renders nothing when there is no batch', () => {
    getTasks.mockResolvedValue({ batch_id: null, total: 0, done: 0, failed: 0, active: 0, items: [] })
    const { container } = renderPanel()
    expect(container).toBeEmptyDOMElement()
  })

  it('renders progress counts and failed item retry', async () => {
    getTasks.mockResolvedValue({
      batch_id: 'b1',
      total: 2,
      done: 1,
      failed: 1,
      active: 0,
      items: [
        { item_id: 'i1', title: '视频', part_title: 'P1', status: 'done', error_msg: '' },
        { item_id: 'i2', title: '视频', part_title: 'P2', status: 'failed', error_msg: 'boom' },
      ],
    })
    renderPanel()
    expect(await screen.findByText('完成 1 / 2 · 失败 1')).toBeInTheDocument()
    expect(await screen.findByText('重试')).toBeInTheDocument()
  })

  it('calls retryItem when clicking retry', async () => {
    getTasks.mockResolvedValue({
      batch_id: 'b1',
      total: 1,
      done: 0,
      failed: 1,
      active: 0,
      items: [{ item_id: 'i2', title: '视频', part_title: 'P2', status: 'failed', error_msg: 'boom' }],
    })
    retryItem.mockResolvedValue({ status: 'ok' })
    renderPanel()
    fireEvent.click(await screen.findByText('重试'))
    expect(retryItem).toHaveBeenCalledWith('i2')
  })
})
