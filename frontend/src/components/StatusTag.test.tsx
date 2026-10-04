import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import StatusTag from './StatusTag'

describe('StatusTag', () => {
  it('renders label for known status', () => {
    render(<StatusTag status="done" />)
    expect(screen.getByText('已完成')).toBeInTheDocument()
  })

  it('falls back to pending for unknown status', () => {
    render(<StatusTag status="unknown" />)
    expect(screen.getByText('待处理')).toBeInTheDocument()
  })
})
