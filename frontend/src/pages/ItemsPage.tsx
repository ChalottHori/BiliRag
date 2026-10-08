import { useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { listFolders } from '../api/folders'
import { deleteItem, getItem, listItems } from '../api/items'
import { collectionSummary, resummarizeItem, retryItem } from '../api/summarize'
import Drawer from '../components/Drawer'
import Pagination from '../components/Pagination'
import StatusTag from '../components/StatusTag'
import Button from '../components/ui/Button'
import Input from '../components/ui/Input'
import Select from '../components/ui/Select'
import { formatItemTitle } from '../utils/format'
import styles from './ItemsPage.module.css'

export default function ItemsPage() {
  const queryClient = useQueryClient()
  const [keyword, setKeyword] = useState('')
  const [folderId, setFolderId] = useState('')
  const [page, setPage] = useState(1)
  const [detailId, setDetailId] = useState<string | null>(null)

  const foldersQuery = useQuery({ queryKey: ['folders'], queryFn: listFolders })

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
              <Button variant="ghost" onClick={() => deleteMutation.mutate(detail.id)}>
                删除
              </Button>
            </div>
          </div>
        )}
      </Drawer>
    </div>
  )
}
