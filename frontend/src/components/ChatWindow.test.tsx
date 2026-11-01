import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { useChatStore } from '../stores/chat'
import { useSelectionStore } from '../stores/selection'
import ChatWindow from './ChatWindow'

function renderChatWindow(running?: boolean) {
  return render(
    <MemoryRouter>
      <ChatWindow running={running} />
    </MemoryRouter>,
  )
}

describe('ChatWindow', () => {
  beforeEach(() => {
    useChatStore.getState().reset()
    useSelectionStore.getState().clear()
  })

  it('renders message bubbles from store', () => {
    useChatStore.setState({
      messages: [
        { role: 'user', content: '你好' },
        { role: 'assistant', content: '你好！', streaming: true },
      ],
    })
    renderChatWindow()
    expect(screen.getByText('你好')).toBeInTheDocument()
    expect(screen.getByText('你好！')).toBeInTheDocument()
  })

  it('renders execution trace line for vector route', () => {
    useChatStore.setState({
      messages: [
        {
          role: 'assistant',
          content: '答案',
          trace: {
            route: 'vector',
            label: '检索知识库',
            retrieval: { vector_count: 12, keyword_count: 5, final_count: 8, elapsed_ms: 320 },
          },
        },
      ],
    })
    renderChatWindow()
    expect(screen.getByText(/路由：检索知识库/)).toBeInTheDocument()
    expect(screen.getByText(/向量 12 \/ 关键词 5 → 融合 8（耗时 320ms）/)).toBeInTheDocument()
  })

  it('omits retrieval segment for non-vector route', () => {
    useChatStore.setState({
      messages: [
        {
          role: 'assistant',
          content: '答案',
          trace: { route: 'db_list', label: '浏览列表' },
        },
      ],
    })
    renderChatWindow()
    expect(screen.getByText(/路由：浏览列表/)).toBeInTheDocument()
    expect(screen.queryByText(/向量/)).not.toBeInTheDocument()
  })

  it('renders clickable source cards with title and snippet', () => {
    useChatStore.setState({
      messages: [
        {
          role: 'assistant',
          content: '答案',
          sources: [
            {
              bvid: 'BV1xx',
              title: '某视频',
              url: 'https://www.bilibili.com/video/BV1xx',
              snippet: '片段',
            },
          ],
        },
      ],
    })
    renderChatWindow()
    const link = screen.getByRole('link', { name: /某视频/ })
    expect(link).toHaveAttribute('href', 'https://www.bilibili.com/video/BV1xx')
    expect(link).toHaveAttribute('target', '_blank')
    expect(screen.getByText('片段')).toBeInTheDocument()
  })

  it('falls back to citations as clickable cards', () => {
    useChatStore.setState({
      messages: [
        {
          role: 'assistant',
          content: '答案',
          citations: [
            { item_id: 'i1', bvid: 'BV2xx', cid: 1, title: '历史引用', chunk_idx: 0, snippet: '' },
          ],
        },
      ],
    })
    renderChatWindow()
    const link = screen.getByRole('link', { name: /历史引用/ })
    expect(link).toHaveAttribute('href', 'https://www.bilibili.com/video/BV2xx')
  })

  it('streams assistant response via fetch', async () => {
    const stream = new ReadableStream({
      start(controller) {
        const encoder = new TextEncoder()
        controller.enqueue(encoder.encode('data: {"type":"delta","content":"这是"}\n\n'))
        controller.enqueue(encoder.encode('data: {"type":"delta","content":"答案"}\n\n'))
        controller.enqueue(encoder.encode('data: {"type":"done","session_id":"s1"}\n\n'))
        controller.close()
      },
    })
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response(stream, { status: 200 })))

    renderChatWindow()
    fireEvent.change(screen.getByPlaceholderText('输入问题…'), {
      target: { value: '问题' },
    })
    fireEvent.click(screen.getByText('发送'))

    await waitFor(() => {
      expect(screen.getByText('这是答案')).toBeInTheDocument()
    })
    vi.unstubAllGlobals()
  })

  it('parses route/retrieval/sources frames into trace and source cards', async () => {
    const stream = new ReadableStream({
      start(controller) {
        const encoder = new TextEncoder()
        controller.enqueue(
          encoder.encode('data: {"type":"route","route":"vector","label":"检索知识库"}\n\n'),
        )
        controller.enqueue(
          encoder.encode(
            'data: {"type":"retrieval","vector_count":12,"keyword_count":5,"final_count":8,"elapsed_ms":320}\n\n',
          ),
        )
        controller.enqueue(
          encoder.encode(
            'data: {"type":"sources","items":[{"bvid":"BV1xx","title":"某视频","url":"https://www.bilibili.com/video/BV1xx","snippet":"片段"}]}\n\n',
          ),
        )
        controller.enqueue(encoder.encode('data: {"type":"delta","content":"这是答案"}\n\n'))
        controller.enqueue(
          encoder.encode(
            'data: {"type":"done","session_id":"s1","citations":[{"item_id":"i1","bvid":"BV1xx","cid":1,"title":"某视频","chunk_idx":0,"snippet":"片段"}]}\n\n',
          ),
        )
        controller.close()
      },
    })
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response(stream, { status: 200 })))

    renderChatWindow()
    fireEvent.change(screen.getByPlaceholderText('输入问题…'), {
      target: { value: '问题' },
    })
    fireEvent.click(screen.getByText('发送'))

    await waitFor(() => {
      expect(screen.getByText('这是答案')).toBeInTheDocument()
    })

    expect(screen.getByText(/路由：检索知识库/)).toBeInTheDocument()
    expect(screen.getByText(/向量 12 \/ 关键词 5 → 融合 8（耗时 320ms）/)).toBeInTheDocument()
    const link = screen.getByRole('link', { name: /某视频/ })
    expect(link).toHaveAttribute('href', 'https://www.bilibili.com/video/BV1xx')
    expect(screen.getByText('片段')).toBeInTheDocument()

    const messages = useChatStore.getState().messages
    expect(messages[messages.length - 1].trace).toEqual({
      route: 'vector',
      label: '检索知识库',
      retrieval: { vector_count: 12, keyword_count: 5, final_count: 8, elapsed_ms: 320 },
    })
    expect(messages[messages.length - 1].sources).toEqual([
      {
        bvid: 'BV1xx',
        title: '某视频',
        url: 'https://www.bilibili.com/video/BV1xx',
        snippet: '片段',
      },
    ])

    vi.unstubAllGlobals()
  })

  it('shows full-library scope when nothing selected', () => {
    renderChatWindow()
    expect(screen.getByText('检索范围：全库')).toBeInTheDocument()
    expect(screen.queryByText('回到全库')).not.toBeInTheDocument()
  })

  it('shows folder + video scope and clears back to full library', () => {
    useSelectionStore.setState({
      selectedFolders: { f1: { id: 'f1', title: 'A' } },
      selected: {
        'BV1:0': {
          bvid: 'BV1',
          cid: 0,
          title: 't',
          partTitle: '',
          coverUrl: '',
          upName: '',
          pubdate: 0,
          duration: 0,
        },
        'BV2:0': {
          bvid: 'BV2',
          cid: 0,
          title: 't',
          partTitle: '',
          coverUrl: '',
          upName: '',
          pubdate: 0,
          duration: 0,
        },
      },
    })
    renderChatWindow()
    expect(screen.getByText('检索范围：收藏夹·A + 2 个视频')).toBeInTheDocument()

    fireEvent.click(screen.getByText('回到全库'))
    expect(screen.getByText('检索范围：全库')).toBeInTheDocument()
    expect(Object.keys(useSelectionStore.getState().selected)).toHaveLength(0)
    expect(Object.keys(useSelectionStore.getState().selectedFolders)).toHaveLength(0)
  })

  it('disables send button while a task is running', () => {
    renderChatWindow(true)
    expect(screen.getByText('发送')).toBeDisabled()
  })

  it('disables back-to-full-library while streaming', () => {
    useChatStore.setState({ streaming: true })
    useSelectionStore.setState({ selectedFolders: { f1: { id: 'f1', title: 'A' } } })
    renderChatWindow()
    expect(screen.getByText('回到全库')).toBeDisabled()
  })

  it('passes scope filter in chat request body', async () => {
    useSelectionStore.setState({
      selectedFolders: { f1: { id: 'f1', title: 'A' } },
    })
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(
        new ReadableStream({
          start(controller) {
            controller.enqueue(
              new TextEncoder().encode('data: {"type":"delta","content":"答"}\n\n'),
            )
            controller.enqueue(new TextEncoder().encode('data: {"type":"done"}\n\n'))
            controller.close()
          },
        }),
        { status: 200 },
      ),
    )
    vi.stubGlobal('fetch', fetchMock)

    renderChatWindow()
    fireEvent.change(screen.getByPlaceholderText('输入问题…'), { target: { value: '问题' } })
    fireEvent.click(screen.getByText('发送'))

    await waitFor(() => {
      expect(fetchMock).toHaveBeenCalled()
    })

    const [url, init] = fetchMock.mock.calls[0]
    expect(url).toBe('/api/chat')
    expect(JSON.parse(init.body).filter).toEqual({ folder_ids: ['f1'], bvids: [] })

    vi.unstubAllGlobals()
  })

  it('passes time range in chat request body and clears time', async () => {
    useSelectionStore.getState().setTimeRange('2026-10-01', '2026-10-27')
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(
        new ReadableStream({
          start(controller) {
            controller.enqueue(new TextEncoder().encode('data: {"type":"done"}\n\n'))
            controller.close()
          },
        }),
        { status: 200 },
      ),
    )
    vi.stubGlobal('fetch', fetchMock)

    renderChatWindow()
    expect(screen.getByText(/检索范围：2026-10-01 ~ 2026-10-27/)).toBeInTheDocument()

    fireEvent.change(screen.getByPlaceholderText('输入问题…'), { target: { value: '问题' } })
    fireEvent.click(screen.getByText('发送'))

    await waitFor(() => {
      expect(fetchMock).toHaveBeenCalled()
    })

    const [, init] = fetchMock.mock.calls[0]
    expect(JSON.parse(init.body).filter).toEqual({
      folder_ids: [],
      bvids: [],
      time_from: '2026-10-01',
      time_to: '2026-10-27T23:59:59',
    })

    fireEvent.click(screen.getByText('清除时间'))
    expect(screen.getByText('检索范围：全库')).toBeInTheDocument()

    vi.unstubAllGlobals()
  })

  it('renders agent step list when trace has steps', () => {
    useChatStore.setState({
      messages: [
        {
          role: 'assistant',
          content: '答案',
          trace: {
            route: 'vector',
            label: '多步检索',
            steps: [
              { kind: 'tool_call', tool: 'search', label: '正在检索知识库「X」' },
              { kind: 'observation', tool: 'search', label: '检索到 2 条片段' },
            ],
          },
        },
      ],
    })
    renderChatWindow()
    expect(screen.getByText(/路由：多步检索/)).toBeInTheDocument()
    expect(screen.getByText(/🔍 正在检索知识库「X」/)).toBeInTheDocument()
    expect(screen.getByText(/→ 检索到 2 条片段/)).toBeInTheDocument()
  })

  it('parses agent_step frames into step list', async () => {
    const stream = new ReadableStream({
      start(controller) {
        const encoder = new TextEncoder()
        controller.enqueue(
          encoder.encode('data: {"type":"route","route":"vector","label":"多步检索"}\n\n'),
        )
        controller.enqueue(
          encoder.encode(
            'data: {"type":"agent_step","step":{"kind":"tool_call","tool":"search","label":"正在检索"}}\n\n',
          ),
        )
        controller.enqueue(
          encoder.encode(
            'data: {"type":"agent_step","step":{"kind":"observation","tool":"search","label":"检索到 1 条"}}\n\n',
          ),
        )
        controller.enqueue(encoder.encode('data: {"type":"delta","content":"答案"}\n\n'))
        controller.enqueue(encoder.encode('data: {"type":"done"}\n\n'))
        controller.close()
      },
    })
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response(stream, { status: 200 })))

    renderChatWindow()
    fireEvent.change(screen.getByPlaceholderText('输入问题…'), { target: { value: '问题' } })
    fireEvent.click(screen.getByText('发送'))

    await waitFor(() => {
      expect(screen.getByText('答案')).toBeInTheDocument()
    })

    expect(screen.getByText(/🔍 正在检索/)).toBeInTheDocument()
    expect(screen.getByText(/→ 检索到 1 条/)).toBeInTheDocument()

    const messages = useChatStore.getState().messages
    expect(messages[messages.length - 1].trace?.steps).toEqual([
      { kind: 'tool_call', tool: 'search', label: '正在检索' },
      { kind: 'observation', tool: 'search', label: '检索到 1 条' },
    ])

    vi.unstubAllGlobals()
  })

  it('renders verification warning for fail verdict', () => {
    useChatStore.setState({
      messages: [
        {
          role: 'assistant',
          content: '答案',
          verdict: {
            verdict: 'fail',
            issues: [{ type: 'fabricated_source', source: '《假视频》', reason: '不在检索结果中' }],
          },
        },
      ],
    })
    renderChatWindow()
    expect(screen.getByText('⚠ 部分内容存疑')).toBeInTheDocument()
    expect(screen.getByText(/编造来源：《假视频》/)).toBeInTheDocument()
  })

  it('omits verification warning for pass verdict', () => {
    useChatStore.setState({
      messages: [{ role: 'assistant', content: '答案', verdict: { verdict: 'pass', issues: [] } }],
    })
    renderChatWindow()
    expect(screen.queryByText('⚠ 部分内容存疑')).not.toBeInTheDocument()
  })

  it('parses verification frame into verdict', async () => {
    const stream = new ReadableStream({
      start(controller) {
        const encoder = new TextEncoder()
        controller.enqueue(
          encoder.encode(
            'data: {"type":"verification","verdict":"fail","issues":[{"type":"unsupported_claim","claim":"x","reason":"无证据"}]}\n\n',
          ),
        )
        controller.enqueue(encoder.encode('data: {"type":"done"}\n\n'))
        controller.close()
      },
    })
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response(stream, { status: 200 })))

    renderChatWindow()
    fireEvent.change(screen.getByPlaceholderText('输入问题…'), { target: { value: '问题' } })
    fireEvent.click(screen.getByText('发送'))

    await waitFor(() => {
      expect(screen.getByText('⚠ 部分内容存疑')).toBeInTheDocument()
    })

    const messages = useChatStore.getState().messages
    expect(messages[messages.length - 1].verdict).toEqual({
      verdict: 'fail',
      issues: [{ type: 'unsupported_claim', claim: 'x', reason: '无证据' }],
    })

    vi.unstubAllGlobals()
  })
})
