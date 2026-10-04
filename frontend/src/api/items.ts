import { del, post, request } from './client'
import type { Item, ItemDetail } from './types'

export interface ListItemsParams {
  folder_id?: string
  keyword?: string
  page?: number
  page_size?: number
}

export function listItems(params: ListItemsParams = {}): Promise<{ total: number; items: Item[] }> {
  const qs = new URLSearchParams()
  if (params.folder_id) qs.set('folder_id', params.folder_id)
  if (params.keyword) qs.set('keyword', params.keyword)
  qs.set('page', String(params.page ?? 1))
  qs.set('page_size', String(params.page_size ?? 20))
  return request(`/api/items?${qs.toString()}`)
}

export function getItem(id: string): Promise<ItemDetail> {
  return request(`/api/items/${id}`)
}

export function moveItems(ids: string[], folderId: string | null): Promise<{ status: string }> {
  return post('/api/items/move', { ids, folder_id: folderId })
}

export function deleteItem(id: string): Promise<{ status: string }> {
  return del(`/api/items/${id}`)
}
