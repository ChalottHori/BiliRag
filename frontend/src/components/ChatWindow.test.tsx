import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { useChatStore } from '../stores/chat'
import ChatWindow from './ChatWindow'

function renderChatWindow() {
  return render(
    <MemoryRouter>
      <ChatWindow />
    </MemoryRouter>,
  )
}

describe('ChatWindow', () => {
  beforeEach(() => {
    useChatStore.getState().reset()
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
    expect(
      screen.getByText(/向量 12 \/ 关键词 5 → 融合 8（耗时 320ms）/),
    ).toBeInTheDocument()
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
    expect(
      screen.getByText(/向量 12 \/ 关键词 5 → 融合 8（耗时 320ms）/),
    ).toBeInTheDocument()
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
})
