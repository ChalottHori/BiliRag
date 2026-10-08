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
  toggle: (target: SelectionTarget) => void
  selectMany: (targets: SelectionTarget[]) => void
  toggleFolder: (folder: FolderScope) => void
  clear: () => void
}

export const useSelectionStore = create<SelectionState>((set) => ({
  selected: {},
  selectedFolders: {},
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
}))

export function selectedCount(): number {
  return Object.keys(useSelectionStore.getState().selected).length
}

export function buildScopeFilter(): { folder_ids: string[]; bvids: string[] } | null {
  const { selected, selectedFolders } = useSelectionStore.getState()
  const folder_ids = Object.keys(selectedFolders)
  const bvids = [...new Set(Object.values(selected).map((t) => t.bvid))]
  if (folder_ids.length === 0 && bvids.length === 0) return null
  return { folder_ids, bvids }
}
