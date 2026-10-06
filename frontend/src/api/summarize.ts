import { post, request } from './client'
import type { TaskSnapshot } from './types'

export function summarize(
  targets: unknown[],
  folderId?: string | null,
): Promise<{ created: number; item_ids: string[]; batch_id: string }> {
  return post('/api/summarize', { targets, folder_id: folderId ?? null })
}

export function getTasks(): Promise<TaskSnapshot> {
  return request('/api/tasks')
}

export function retryItem(id: string): Promise<{ status: string }> {
  return post(`/api/items/${id}/retry`, {})
}

export function resummarizeItem(id: string): Promise<{ status: string }> {
  return post(`/api/items/${id}/resummarize`, {})
}

export function collectionSummary(id: string): Promise<Record<string, unknown>> {
  return post(`/api/items/${id}/collection-summary`, {})
}
