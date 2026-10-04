import { useMemo, useRef, useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useNavigate } from 'react-router-dom'
import { listFolders, listFolderVideos, listVideoParts, syncFolders } from '../api/folders'
import { summarize } from '../api/summarize'
import ChatWindow from '../components/ChatWindow'
import Pagination from '../components/Pagination'
import SelectionBar from '../components/SelectionBar'
import VideoRow from '../components/VideoRow'
import Button from '../components/ui/Button'
import Chip from '../components/ui/Chip'
import { useResizable } from '../hooks/useResizable'
import { useSelectionStore, type SelectionTarget } from '../stores/selection'
import { useUiStore } from '../stores/ui'
import styles from './FoldersPage.module.css'

const PAGE_SIZE = 20

function videoTarget(video: {
  bvid: string
  title: string
  cover_url: string
  up_name: string
  pubdate: number
  duration: number
}): SelectionTarget {
  return {
    bvid: video.bvid,
    cid: 0,
    title: video.title,
    partTitle: '',
    coverUrl: video.cover_url,
    upName: video.up_name,
    pubdate: video.pubdate,
    duration: video.duration,
  }
}

export default function FoldersPage() {
  const queryClient = useQueryClient()
  const navigate = useNavigate()
  const [explicitFid, setExplicitFid] = useState<string | null>(null)
  const [page, setPage] = useState(1)

  const selected = useSelectionStore((s) => s.selected)
  const toggle = useSelectionStore((s) => s.toggle)
  const selectMany = useSelectionStore((s) => s.selectMany)
  const clear = useSelectionStore((s) => s.clear)

  const videoPanelWidth = useUiStore((s) => s.videoPanelWidth)
  const setVideoPanelWidth = useUiStore((s) => s.setVideoPanelWidth)
  const startWidthRef = useRef(videoPanelWidth)

  const foldersQuery = useQuery({ queryKey: ['folders'], queryFn: listFolders })

  const folders = foldersQuery.data ?? []
  const activeFid =
    explicitFid ?? (folders.find((f) => f.kind === 'uncategorized')?.id ?? folders[0]?.id ?? '')

  const videosQuery = useQuery({
    queryKey: ['folder-videos', activeFid, page],
    queryFn: () => listFolderVideos(activeFid, page, PAGE_SIZE),
    enabled: !!activeFid,
  })

  const syncMutation = useMutation({
    mutationFn: syncFolders,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['folders'] }),
  })

  const videos = videosQuery.data?.items ?? []
  const total = videosQuery.data?.total ?? 0

  const isSelected = (bvid: string) => Boolean(selected[`${bvid}:0`])
  const allSelected = videos.length > 0 && videos.every((v) => isSelected(v.bvid))
  const someSelected = videos.some((v) => isSelected(v.bvid))

  const toggleAll = () => {
    if (allSelected) {
      for (const v of videos) toggle(videoTarget(v))
    } else {
      selectMany(videos.map(videoTarget))
    }
  }

  const selectedCount = useMemo(() => Object.keys(selected).length, [selected])

  const startSummarize = async () => {
    const targets: unknown[] = []
    const uniqueBvids = [...new Set(Object.values(selected).map((t) => t.bvid))]
    for (const bvid of uniqueBvids) {
      const source = Object.values(selected).find((t) => t.bvid === bvid)
      if (!source) continue
      try {
        const parts = await listVideoParts(bvid)
        for (const part of parts) {
          targets.push({
            bvid,
            cid: part.cid,
            title: source.title,
            part_title: part.part_title,
            cover_url: source.coverUrl,
            up_name: source.upName,
            pubdate: source.pubdate,
            duration: part.duration,
            folder_id: source.folderId ?? null,
          })
        }
      } catch {
        /* 忽略单条解析失败 */
      }
    }
    if (targets.length === 0) return
    await summarize(targets, activeFid || null)
    clear()
    navigate('/tasks')
  }

  const { onMouseDown } = useResizable((delta) => {
    setVideoPanelWidth(Math.max(320, startWidthRef.current + delta))
  })

  const handleDividerMouseDown = (e: React.MouseEvent) => {
    startWidthRef.current = videoPanelWidth
    onMouseDown(e)
  }

  return (
    <div className={styles.workspace}>
      <div className={styles.videoPanel} style={{ width: videoPanelWidth }}>
        <div className={styles.folderTabs}>
          {folders.map((folder) => (
            <Chip key={folder.id} active={folder.id === activeFid} onClick={() => setExplicitFid(folder.id)}>
              {folder.title}
            </Chip>
          ))}
          <Button variant="ghost" onClick={() => syncMutation.mutate()} disabled={syncMutation.isPending}>
            刷新
          </Button>
        </div>

        <div className={styles.toolbar}>
          <label className={styles.selectAll}>
            <input
              type="checkbox"
              checked={allSelected}
              ref={(el) => {
                if (el) el.indeterminate = !allSelected && someSelected
              }}
              onChange={toggleAll}
            />
            整选当前收藏夹
          </label>
          <span className={styles.count}>已选 {selectedCount} 项</span>
        </div>

        <div className={styles.list}>
          {videos.map((video) => (
            <VideoRow
              key={video.bvid}
              video={{
                bvid: video.bvid,
                title: video.title,
                coverUrl: video.cover_url,
                upName: video.up_name,
                duration: video.duration,
                isCollection: video.is_collection,
                isInvalid: video.is_invalid,
              }}
              checked={isSelected(video.bvid)}
              onToggle={() => toggle(videoTarget(video))}
            />
          ))}
          {videos.length === 0 && <div className={styles.empty}>暂无视频</div>}
        </div>

        <Pagination page={page} pageSize={PAGE_SIZE} total={total} onChange={setPage} />

        <SelectionBar count={selectedCount} onStart={startSummarize} onClear={clear} />
      </div>

      <div className={styles.divider} onMouseDown={handleDividerMouseDown} />

      <div className={styles.chatPanel}>
        <ChatWindow />
      </div>
    </div>
  )
}
