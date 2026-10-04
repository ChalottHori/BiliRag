import { create } from 'zustand'

interface AuthState {
  loggedIn: boolean
  userName: string
  userMid: string
  setLoggedIn: (loggedIn: boolean, userName?: string, userMid?: string) => void
  logout: () => void
}

export const useAuthStore = create<AuthState>((set) => ({
  loggedIn: false,
  userName: '',
  userMid: '',
  setLoggedIn: (loggedIn, userName = '', userMid = '') => set({ loggedIn, userName, userMid }),
  logout: () => set({ loggedIn: false, userName: '', userMid: '' }),
}))
