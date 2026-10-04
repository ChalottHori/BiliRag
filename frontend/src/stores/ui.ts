import { create } from 'zustand'
import { persist } from 'zustand/middleware'

interface UiState {
  sidebarCollapsed: boolean
  videoPanelWidth: number
  chatPanelWidth: number
  toggleSidebar: () => void
  setVideoPanelWidth: (width: number) => void
  setChatPanelWidth: (width: number) => void
}

export const useUiStore = create<UiState>()(
  persist(
    (set) => ({
      sidebarCollapsed: false,
      videoPanelWidth: 640,
      chatPanelWidth: 420,
      toggleSidebar: () => set((s) => ({ sidebarCollapsed: !s.sidebarCollapsed })),
      setVideoPanelWidth: (width) => set({ videoPanelWidth: width }),
      setChatPanelWidth: (width) => set({ chatPanelWidth: width }),
    }),
    { name: 'bilirag-ui' },
  ),
)
