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
})
