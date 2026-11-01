import { create } from 'zustand'

export interface SelectionTarget {
  bvid: string
  cid: number
  title: string
  partTitle: string
  coverUrl: string
  upName: string
  pubdate: number
  duration: number
  folderId?: string | null
}

export interface FolderScope {
  id: string
  title: string
}

const keyOf = (t: SelectionTarget) => `${t.bvid}:${t.cid}`

interface SelectionState {
  selected: Record<string, SelectionTarget>
  selectedFolders: Record<string, FolderScope>
  timeFrom: string
  timeTo: string
  toggle: (target: SelectionTarget) => void
  selectMany: (targets: SelectionTarget[]) => void
  toggleFolder: (folder: FolderScope) => void
  clear: () => void
  setTimeRange: (from: string, to: string) => void
  clearTime: () => void
}

export const useSelectionStore = create<SelectionState>((set) => ({
  selected: {},
  selectedFolders: {},
  timeFrom: '',
  timeTo: '',
  toggle: (target) =>
    set((s) => {
      const next = { ...s.selected }
      const k = keyOf(target)
      if (next[k]) delete next[k]
      else next[k] = target
      return { selected: next }
    }),
  selectMany: (targets) =>
    set((s) => {
      const next = { ...s.selected }
      for (const t of targets) next[keyOf(t)] = t
      return { selected: next }
    }),
  toggleFolder: (folder) =>
    set((s) => {
      const next = { ...s.selectedFolders }
      if (next[folder.id]) delete next[folder.id]
      else next[folder.id] = folder
      return { selectedFolders: next }
    }),
  clear: () => set({ selected: {}, selectedFolders: {} }),
  setTimeRange: (from, to) => set({ timeFrom: from, timeTo: to }),
  clearTime: () => set({ timeFrom: '', timeTo: '' }),
}))

export function selectedCount(): number {
  return Object.keys(useSelectionStore.getState().selected).length
}

export interface ScopeFilter {
  folder_ids: string[]
  bvids: string[]
  time_from?: string
  time_to?: string
}

export function buildScopeFilter(): ScopeFilter | null {
  const { selected, selectedFolders, timeFrom, timeTo } = useSelectionStore.getState()
  const folder_ids = Object.keys(selectedFolders)
  const bvids = [...new Set(Object.values(selected).map((t) => t.bvid))]
  const time_from = timeFrom || ''
  const time_to = timeTo ? `${timeTo}T23:59:59` : ''
  if (folder_ids.length === 0 && bvids.length === 0 && !time_from && !time_to) return null
  const filter: ScopeFilter = { folder_ids, bvids }
  if (time_from) filter.time_from = time_from
  if (time_to) filter.time_to = time_to
  return filter
}
