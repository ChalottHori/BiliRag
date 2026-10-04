import { post } from './client'
import type { VideoInfo } from './types'

export function parseLinks(links: string[]): Promise<VideoInfo[]> {
  return post('/api/import/parse', { links })
}

export function confirmImport(
  targets: unknown[],
  folderId?: string | null,
): Promise<{ created: number; item_ids: string[] }> {
  return post('/api/import/confirm', { targets, folder_id: folderId ?? null })
}
