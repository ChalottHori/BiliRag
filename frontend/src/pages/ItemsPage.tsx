import { useEffect, useRef, useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { getConfig } from '../api/config'
import { exportMarkdown } from '../api/export'
import type { ExportBody } from '../api/export'
import { listFolders } from '../api/folders'
import { deleteItem, getItem, listItems } from '../api/items'
import { collectionSummary, resummarizeItem, retryItem } from '../api/summarize'
import DirPicker from '../components/DirPicker'
import Drawer from '../components/Drawer'
import Pagination from '../components/Pagination'
import StatusTag from '../components/StatusTag'
import Button from '../components/ui/Button'
import Dialog from '../components/ui/Dialog'
import Input from '../components/ui/Input'
import Select from '../components/ui/Select'
import { formatItemTitle } from '../utils/format'
import styles from './ItemsPage.module.css'

type ExportTarget = { kind: 'folder' } | { kind: 'item'; id: string }

export default function ItemsPage() {
  const queryClient = useQueryClient()
  const [keyword, setKeyword] = useState('')
  const [folderId, setFolderId] = useState('')
  const [page, setPage] = useState(1)
  const [detailId, setDetailId] = useState<string | null>(null)
  const [exportTarget, setExportTarget] = useState<ExportTarget | null>(null)
  const [exportDir, setExportDir] = useState('')
  const [exportResult, setExportResult] = useState<string | null>(null)
  const [exportError, setExportError] = useState<string | null>(null)
  const exportDirReadyRef = useRef(false)

  const foldersQuery = useQuery({ queryKey: ['folders'], queryFn: listFolders })

  const configQuery = useQuery({ queryKey: ['config'], queryFn: getConfig })

  // 首次拿到配置后用后端导出目录预填 DirPicker，后续 refetch 不覆盖用户正在编辑的值
  useEffect(() => {
    if (configQuery.data && !exportDirReadyRef.current) {
      exportDirReadyRef.current = true
      setExportDir(configQuery.data.export_dir ?? '')
    }
  }, [configQuery.data])

  const itemsQuery = useQuery({
    queryKey: ['items', keyword, folderId, page],
    queryFn: () =>
      listItems({
        keyword: keyword || undefined,
        folder_id: folderId || undefined,
        page,
        page_size: 20,
      }),
  })

  const detailQuery = useQuery({
    queryKey: ['item-detail', detailId],
    queryFn: () => getItem(detailId!),
    enabled: !!detailId,
  })

  const deleteMutation = useMutation({
    mutationFn: (id: string) => deleteItem(id),
    onSuccess: () => {
      setDetailId(null)
      queryClient.invalidateQueries({ queryKey: ['items'] })
    },
  })

  const resummarizeMutation = useMutation({
    mutationFn: (id: string) => resummarizeItem(id),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['items'] }),
  })

  const retryMutation = useMutation({
    mutationFn: (id: string) => retryItem(id),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['items'] }),
  })

  const collectionMutation = useMutation({ mutationFn: (id: string) => collectionSummary(id) })

  const exportMutation = useMutation({
    mutationFn: (body: ExportBody) => exportMarkdown(body),
    onSuccess: (data) => {
      setExportResult(`已导出 ${data.count} 条 → ${data.dest_dir}`)
      setExportError(null)
    },
    onError: (err) => {
      setExportError(err instanceof Error ? err.message : String(err))
      setExportResult(null)
    },
  })

  const openFolderExport = () => {
    setExportTarget({ kind: 'folder' })
    setExportResult(null)
    setExportError(null)
  }

  const openItemExport = (id: string) => {
    setExportTarget({ kind: 'item', id })
    setExportResult(null)
    setExportError(null)
  }

  const closeExport = () => {
    setExportTarget(null)
    setExportResult(null)
    setExportError(null)
  }

  const confirmExport = () => {
    if (!exportTarget) return
    const body: ExportBody =
      exportTarget.kind === 'item'
        ? { item_ids: [exportTarget.id] }
        : folderId === ''
          ? { all: true }
          : { folder_ids: [folderId] }
    if (exportDir) body.dest_dir = exportDir
    exportMutation.mutate(body)
  }

  const items = itemsQuery.data?.items ?? []
  const total = itemsQuery.data?.total ?? 0
  const detail = detailQuery.data

  return (
    <div className={styles.page}>
      <div className={styles.filters}>
        <Input
          value={keyword}
          onChange={(e) => setKeyword(e.target.value)}
          placeholder="搜索标题 / 全文稿"
        />
        <Select value={folderId} onChange={(e) => setFolderId(e.target.value)}>
          <option value="">全部收藏夹</option>
          {(foldersQuery.data ?? []).map((f) => (
            <option key={f.id} value={f.id}>
              {f.title}
            </option>
          ))}
        </Select>
        <Button variant="secondary" onClick={openFolderExport}>
          导出
        </Button>
      </div>

      <div className={styles.list}>
        {items.map((item) => (
          <button
            key={item.id}
            type="button"
            className={styles.row}
            onClick={() => setDetailId(item.id)}
          >
            <div className={styles.title}>{formatItemTitle(item.title, item.part_title)}</div>
            <StatusTag status={item.status} />
          </button>
        ))}
        {items.length === 0 && <div className={styles.empty}>暂无条目</div>}
      </div>

      <Pagination page={page} pageSize={20} total={total} onChange={setPage} />

      <Drawer
        open={!!detailId}
        title={detail ? formatItemTitle(detail.title, detail.part_title) : '条目详情'}
        onClose={() => setDetailId(null)}
      >
        {detail && (
          <div className={styles.detail}>
            {detail.summary?.overview && <p>{detail.summary.overview}</p>}
            {detail.summary?.points && detail.summary.points.length > 0 && (
              <ul>
                {detail.summary.points.map((point, i) => (
                  <li key={i}>{point}</li>
                ))}
              </ul>
            )}
            <pre className={styles.transcript}>{detail.transcript_snippet}</pre>
            <div className={styles.actions}>
              {detail.status === 'failed' && (
                <Button variant="secondary" onClick={() => retryMutation.mutate(detail.id)}>
                  重试
                </Button>
              )}
              <Button variant="secondary" onClick={() => resummarizeMutation.mutate(detail.id)}>
                重新总结
              </Button>
              <Button variant="secondary" onClick={() => collectionMutation.mutate(detail.id)}>
                合集总摘要
              </Button>
              <Button variant="secondary" onClick={() => openItemExport(detail.id)}>
                导出
              </Button>
              <Button variant="ghost" onClick={() => deleteMutation.mutate(detail.id)}>
                删除
              </Button>
            </div>
          </div>
        )}
      </Drawer>

      <Dialog
        open={exportTarget !== null}
        onOpenChange={(open) => {
          if (!open) closeExport()
        }}
        title="导出 Markdown"
      >
        <div className={styles.exportForm}>
          <DirPicker value={exportDir} onChange={setExportDir} />
          <Button onClick={confirmExport} disabled={exportMutation.isPending}>
            导出
          </Button>
          {exportMutation.isPending && <div className={styles.exportHint}>导出中…</div>}
          {exportResult && <div className={styles.exportResult}>{exportResult}</div>}
          {exportError && <div className={styles.exportError}>导出失败：{exportError}</div>}
        </div>
      </Dialog>
    </div>
  )
}
