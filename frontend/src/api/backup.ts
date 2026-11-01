import { post } from './client'

export interface BackupResult {
  status: string
  backup_dir: string
}

export function backupNow(): Promise<BackupResult> {
  return post('/api/backup', {})
}
