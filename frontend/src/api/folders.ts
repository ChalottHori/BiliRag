import { post, request } from './client'
import type { Folder, ItemStatus, PartInfo } from './types'

export interface VideoRow {
  bvid: string
  aid: number
  title: string
  cover_url: string
  up_name: string
  pubdate: number
  duration: number
  is_collection: boolean
  is_invalid: boolean
  part_count?: number
  parts_status?: Record<string, ItemStatus>
}

export function listFolders(): Promise<Folder[]> {
  return request('/api/folders')
}

export function syncFolders(): Promise<{ count: number }> {
  return post('/api/folders/sync', {})
}

export function listFolderVideos(
  fid: string,
  page = 1,
  pageSize = 20,
): Promise<{ items: VideoRow[]; total: number }> {
  return request(`/api/folders/${fid}/videos?page=${page}&page_size=${pageSize}`)
}

export function listVideoParts(bvid: string): Promise<PartInfo[]> {
  return request(`/api/videos/${bvid}/parts`)
}
