import { post, request } from './client'

export interface QrcodeResult {
  qrcode_url: string
  qrcode_key: string
}

export interface PollResult {
  status: string
  code?: number
  user_name?: string
  user_mid?: string
}

export interface AuthStatus {
  logged_in: boolean
  user_name?: string
  user_mid?: string
  status?: string
}

export function generateQrcode(): Promise<QrcodeResult> {
  return post('/api/bilibili/qrcode/generate', {})
}

export function pollQrcode(key: string): Promise<PollResult> {
  return request(`/api/bilibili/qrcode/poll/${key}`)
}

export function getAuthStatus(): Promise<AuthStatus> {
  return request('/api/bilibili/status')
}

export function logout(): Promise<{ status: string }> {
  return post('/api/bilibili/logout', {})
}
