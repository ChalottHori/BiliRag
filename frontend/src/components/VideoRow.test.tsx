import { fireEvent, render, screen } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import { formatDuration } from '../utils/format'
import VideoRow from './VideoRow'

describe('VideoRow', () => {
  it('renders title and toggles checkbox', () => {
    const onToggle = vi.fn()
    render(
      <VideoRow
        video={{ bvid: 'BV1', title: '测试视频', coverUrl: '', upName: 'UP', duration: 75 }}
        checked={false}
        onToggle={onToggle}
      />,
    )
    expect(screen.getByText('测试视频')).toBeInTheDocument()
    fireEvent.click(screen.getByLabelText('选择 测试视频'))
    expect(onToggle).toHaveBeenCalledWith(true)
  })

  it('disables checkbox for invalid video', () => {
    render(
      <VideoRow
        video={{
          bvid: 'BV1',
          title: '失效视频',
          coverUrl: '',
          upName: 'UP',
          duration: 75,
          isInvalid: true,
        }}
      />,
    )
    expect(screen.getByLabelText('选择 失效视频')).toBeDisabled()
  })

  it('formats duration correctly', () => {
    expect(formatDuration(75)).toBe('01:15')
    expect(formatDuration(3600)).toBe('60:00')
  })
})
