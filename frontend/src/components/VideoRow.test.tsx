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

  it('disables checkbox and retry while locked', () => {
    const onRetry = vi.fn()
    render(
      <VideoRow
        video={{
          bvid: 'BV1',
          title: '锁定视频',
          coverUrl: '',
          upName: 'UP',
          duration: 60,
          partCount: 1,
          partsStatus: { '10': { item_id: 'i2', status: 'failed', error_msg: 'boom' } },
        }}
        disabled
        disabledReason="入库任务进行中"
        onRetry={onRetry}
      />,
    )
    expect(screen.getByLabelText('选择 锁定视频')).toBeDisabled()
    expect(screen.getByText('重试')).toBeDisabled()
  })

  it('formats duration correctly', () => {
    expect(formatDuration(75)).toBe('01:15')
    expect(formatDuration(3600)).toBe('60:00')
  })

  it('expands a collection and toggles individual parts', () => {
    const onTogglePart = vi.fn()
    render(
      <VideoRow
        video={{
          bvid: 'BV1',
          title: '合集',
          coverUrl: '',
          upName: 'UP',
          duration: 120,
          isCollection: true,
          parts: [{ cid: 1, page: 1, part_title: '第一集', duration: 60 }],
        }}
        selectedCids={new Set([1])}
        onTogglePart={onTogglePart}
      />,
    )

    fireEvent.click(screen.getByText('展开'))
    expect(screen.getByText('P1 · 第一集')).toBeInTheDocument()

    const partCheckbox = screen.getByLabelText('选择 合集 P1')
    expect(partCheckbox).toBeChecked()
    fireEvent.click(partCheckbox)
    expect(onTogglePart).toHaveBeenCalledWith({
      cid: 1,
      page: 1,
      part_title: '第一集',
      duration: 60,
    })
  })

  it('marks all parts checked when the video is selected as a whole', () => {
    render(
      <VideoRow
        video={{
          bvid: 'BV1',
          title: '合集',
          coverUrl: '',
          upName: 'UP',
          duration: 120,
          isCollection: true,
          parts: [
            { cid: 1, page: 1, part_title: '第一集', duration: 60 },
            { cid: 2, page: 2, part_title: '第二集', duration: 60 },
          ],
        }}
        checked
        onTogglePart={() => {}}
      />,
    )

    fireEvent.click(screen.getByText('展开'))
    expect(screen.getByLabelText('选择 合集 P1')).toBeChecked()
    expect(screen.getByLabelText('选择 合集 P2')).toBeChecked()
  })

  it('shows 已入库 tag for a done single-part video', () => {
    render(
      <VideoRow
        video={{
          bvid: 'BV1',
          title: '已入库视频',
          coverUrl: '',
          upName: 'UP',
          duration: 60,
          partCount: 1,
          partsStatus: { '10': { item_id: 'i1', status: 'done', error_msg: '' } },
        }}
      />,
    )
    expect(screen.getByText('已入库')).toBeInTheDocument()
  })

  it('shows 重试 button and calls onRetry for a failed single-part video', () => {
    const onRetry = vi.fn()
    render(
      <VideoRow
        video={{
          bvid: 'BV1',
          title: '失败视频',
          coverUrl: '',
          upName: 'UP',
          duration: 60,
          partCount: 1,
          partsStatus: { '10': { item_id: 'i2', status: 'failed', error_msg: 'boom' } },
        }}
        onRetry={onRetry}
      />,
    )
    fireEvent.click(screen.getByText('重试'))
    expect(onRetry).toHaveBeenCalledWith('i2')
  })

  it('shows aggregate 已入库 N/M for a collection', () => {
    render(
      <VideoRow
        video={{
          bvid: 'BV1',
          title: '合集',
          coverUrl: '',
          upName: 'UP',
          duration: 120,
          isCollection: true,
          partCount: 3,
          partsStatus: {
            '1': { item_id: 'i1', status: 'done', error_msg: '' },
            '2': { item_id: 'i2', status: 'done', error_msg: '' },
          },
        }}
      />,
    )
    expect(screen.getByText('已入库 2/3')).toBeInTheDocument()
  })
})
