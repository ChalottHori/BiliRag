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

const keyOf = (t: SelectionTarget) => `${t.bvid}:${t.cid}`

interface SelectionState {
  selected: Record<string, SelectionTarget>
  toggle: (target: SelectionTarget) => void
  selectMany: (targets: SelectionTarget[]) => void
  clear: () => void
}

export const useSelectionStore = create<SelectionState>((set) => ({
  selected: {},
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
  clear: () => set({ selected: {} }),
}))

export function selectedCount(): number {
  return Object.keys(useSelectionStore.getState().selected).length
}
