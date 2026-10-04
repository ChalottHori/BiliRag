import { put, request } from './client'
import type { Settings } from './types'

export function getConfig(): Promise<Settings> {
  return request('/api/config')
}

export function updateConfig(
  data: Partial<Settings> & { llm_api_key?: string },
): Promise<{ status: string }> {
  return put('/api/config', data)
}
