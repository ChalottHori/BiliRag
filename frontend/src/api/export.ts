import { post } from './client'

export interface ExportResult {
  count: number
  dest_dir: string
  files: string[]
}

export interface ExportBody {
  item_ids?: string[]
  folder_ids?: string[]
  all?: boolean
  dest_dir?: string
}

export function exportMarkdown(body: ExportBody): Promise<ExportResult> {
  return post('/api/export/markdown', body)
}
