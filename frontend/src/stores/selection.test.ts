import { beforeEach, describe, expect, it } from 'vitest'
import { useSelectionStore } from './selection'

function target(bvid: string, cid = 1) {
  return { bvid, cid, title: 't', partTitle: '', coverUrl: '', upName: '', pubdate: 0, duration: 0 }
}

describe('selection store', () => {
  beforeEach(() => useSelectionStore.getState().clear())

  it('toggles selection on and off', () => {
    useSelectionStore.getState().toggle(target('BV1'))
    expect(Object.keys(useSelectionStore.getState().selected)).toHaveLength(1)
    useSelectionStore.getState().toggle(target('BV1'))
    expect(Object.keys(useSelectionStore.getState().selected)).toHaveLength(0)
  })

  it('selects many then clears', () => {
    useSelectionStore.getState().selectMany([target('BV1'), target('BV2')])
    expect(Object.keys(useSelectionStore.getState().selected)).toHaveLength(2)
    useSelectionStore.getState().clear()
    expect(Object.keys(useSelectionStore.getState().selected)).toHaveLength(0)
  })
})
