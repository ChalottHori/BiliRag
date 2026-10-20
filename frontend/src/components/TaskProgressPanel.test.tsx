import { fireEvent, render, screen } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { useChatStore } from '../stores/chat'
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
    useChatStore.getState().reset()
  })

  it('renders nothing when there is no batch', () => {
    getTasks.mockResolvedValue({
      batch_id: null,
      total: 0,
      done: 0,
      failed: 0,
      active: 0,
      items: [],
    })
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
      items: [
        { item_id: 'i2', title: '视频', part_title: 'P2', status: 'failed', error_msg: 'boom' },
      ],
    })
    retryItem.mockResolvedValue({ status: 'ok' })
    renderPanel()
    fireEvent.click(await screen.findByText('重试'))
    expect(retryItem).toHaveBeenCalledWith('i2')
  })

  it('disables retry while a task is running', async () => {
    getTasks.mockResolvedValue({
      batch_id: 'b1',
      total: 2,
      done: 0,
      failed: 1,
      active: 1,
      items: [
        { item_id: 'i1', title: '视频', part_title: 'P1', status: 'transcribing', error_msg: '' },
        { item_id: 'i2', title: '视频', part_title: 'P2', status: 'failed', error_msg: 'boom' },
      ],
    })
    renderPanel()
    expect(await screen.findByText('重试')).toBeDisabled()
  })

  it('disables retry while a chat answer is streaming', async () => {
    useChatStore.setState({ streaming: true })
    getTasks.mockResolvedValue({
      batch_id: 'b1',
      total: 1,
      done: 0,
      failed: 1,
      active: 0,
      items: [
        { item_id: 'i2', title: '视频', part_title: 'P2', status: 'failed', error_msg: 'boom' },
      ],
    })
    renderPanel()
    expect(await screen.findByText('重试')).toBeDisabled()
  })

  it('shows video title, appending part title only when they differ', async () => {
    getTasks.mockResolvedValue({
      batch_id: 'b1',
      total: 2,
      done: 1,
      failed: 1,
      active: 0,
      items: [
        { item_id: 'i1', title: '视频A', part_title: 'P1 子标题', status: 'done', error_msg: '' },
        { item_id: 'i2', title: '视频B', part_title: '视频B', status: 'failed', error_msg: 'boom' },
      ],
    })
    renderPanel()
    expect(await screen.findByText('视频A · P1 子标题')).toBeInTheDocument()
    expect(await screen.findByText('视频B')).toBeInTheDocument()
  })
})
