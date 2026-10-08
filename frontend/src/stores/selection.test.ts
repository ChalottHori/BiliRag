import { beforeEach, describe, expect, it } from 'vitest'
import { buildScopeFilter, useSelectionStore } from './selection'

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

  it('toggles folder scope on and off', () => {
    useSelectionStore.getState().toggleFolder({ id: 'f1', title: '收藏夹A' })
    expect(Object.keys(useSelectionStore.getState().selectedFolders)).toHaveLength(1)
    useSelectionStore.getState().toggleFolder({ id: 'f1', title: '收藏夹A' })
    expect(Object.keys(useSelectionStore.getState().selectedFolders)).toHaveLength(0)
  })

  it('clear empties both video and folder selection', () => {
    useSelectionStore.getState().selectMany([target('BV1')])
    useSelectionStore.getState().toggleFolder({ id: 'f1', title: 'A' })
    useSelectionStore.getState().clear()
    expect(Object.keys(useSelectionStore.getState().selected)).toHaveLength(0)
    expect(Object.keys(useSelectionStore.getState().selectedFolders)).toHaveLength(0)
  })

  it('buildScopeFilter returns null when empty and dedupes bvids', () => {
    expect(buildScopeFilter()).toBeNull()
    useSelectionStore.getState().selectMany([target('BV1', 1), target('BV1', 2), target('BV2', 1)])
    expect(buildScopeFilter()?.bvids).toEqual(['BV1', 'BV2'])
    useSelectionStore.getState().toggleFolder({ id: 'f1', title: 'A' })
    expect(buildScopeFilter()).toEqual({ folder_ids: ['f1'], bvids: ['BV1', 'BV2'] })
  })
})
