import { create } from 'zustand'

interface AuthState {
  loggedIn: boolean
  userName: string
  userMid: string
  loginModalOpen: boolean
  setLoggedIn: (loggedIn: boolean, userName?: string, userMid?: string) => void
  logout: () => void
  openLogin: () => void
  closeLogin: () => void
}

export const useAuthStore = create<AuthState>((set) => ({
  loggedIn: false,
  userName: '',
  userMid: '',
  loginModalOpen: false,
  setLoggedIn: (loggedIn, userName = '', userMid = '') => set({ loggedIn, userName, userMid }),
  logout: () => set({ loggedIn: false, userName: '', userMid: '' }),
  openLogin: () => set({ loginModalOpen: true }),
  closeLogin: () => set({ loginModalOpen: false }),
}))
