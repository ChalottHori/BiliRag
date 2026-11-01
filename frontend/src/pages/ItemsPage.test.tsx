import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { exportMarkdown } from '../api/export'
import ItemsPage from './ItemsPage'

vi.mock('../api/config', () => ({
  getConfig: vi.fn().mockResolvedValue({ export_dir: '/tmp/export' }),
}))

vi.mock('../api/export', () => ({
  exportMarkdown: vi
    .fn()
    .mockResolvedValue({ count: 3, dest_dir: '/tmp/export', files: ['a.md'] }),
}))

vi.mock('../api/folders', () => ({
  listFolders: vi.fn().mockResolvedValue([{ id: 'f1', title: '收藏夹A' }]),
}))

vi.mock('../api/items', () => ({
  listItems: vi.fn().mockResolvedValue({
    items: [{ id: 'i1', title: '视频', part_title: '', status: 'done' }],
    total: 1,
  }),
  getItem: vi.fn().mockResolvedValue({
    id: 'i1',
    title: '视频',
    part_title: '',
    status: 'done',
    summary: null,
    transcript_snippet: '',
  }),
  deleteItem: vi.fn(),
}))

vi.mock('../api/summarize', () => ({
  collectionSummary: vi.fn(),
  resummarizeItem: vi.fn(),
  retryItem: vi.fn(),
}))

function renderPage() {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  })
  return render(
    <QueryClientProvider client={queryClient}>
      <ItemsPage />
    </QueryClientProvider>,
  )
}

describe('ItemsPage 导出', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('从筛选栏导出当前收藏夹范围（全部）', async () => {
    renderPage()
    await waitFor(() => expect(screen.getByText('视频')).toBeInTheDocument())

    fireEvent.click(screen.getByRole('button', { name: '导出' }))

    const dialog = screen.getByRole('dialog')
    await waitFor(() => expect(within(dialog).getByDisplayValue('/tmp/export')).toBeInTheDocument())

    fireEvent.click(within(dialog).getByRole('button', { name: '导出' }))

    await waitFor(() => {
      expect(vi.mocked(exportMarkdown)).toHaveBeenCalledWith({ all: true, dest_dir: '/tmp/export' })
    })
    expect(screen.getByText('已导出 3 条 → /tmp/export')).toBeInTheDocument()
  })

  it('从详情抽屉导出单条条目', async () => {
    renderPage()
    await waitFor(() => expect(screen.getByText('视频')).toBeInTheDocument())

    fireEvent.click(screen.getByRole('button', { name: /视频/ }))
    await waitFor(() => expect(screen.getAllByRole('button', { name: '导出' })).toHaveLength(2))

    const drawerButtons = screen.getAllByRole('button', { name: '导出' })
    fireEvent.click(drawerButtons[drawerButtons.length - 1])

    const dialog = screen.getByRole('dialog')
    fireEvent.click(within(dialog).getByRole('button', { name: '导出' }))

    await waitFor(() => {
      expect(vi.mocked(exportMarkdown)).toHaveBeenCalledWith({
        item_ids: ['i1'],
        dest_dir: '/tmp/export',
      })
    })
  })
})
