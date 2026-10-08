import { useEffect, useMemo, useRef, useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { listFolders, listFolderVideos, listVideoParts, syncFolders } from '../api/folders'
import { retryItem, summarize } from '../api/summarize'
import type { PartInfo } from '../api/types'
import ChatWindow from '../components/ChatWindow'
import Pagination from '../components/Pagination'
import SelectionBar from '../components/SelectionBar'
import TaskProgressPanel from '../components/TaskProgressPanel'
import VideoRow from '../components/VideoRow'
import Button from '../components/ui/Button'
import Chip from '../components/ui/Chip'
import { useResizable } from '../hooks/useResizable'
import { useTaskProgress } from '../hooks/useTaskProgress'
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

function partTarget(
  video: { bvid: string; title: string; cover_url: string; up_name: string; pubdate: number },
  part: PartInfo,
): SelectionTarget {
  return {
    bvid: video.bvid,
    cid: part.cid,
    title: video.title,
    partTitle: part.part_title,
    coverUrl: video.cover_url,
    upName: video.up_name,
    pubdate: video.pubdate,
    duration: part.duration,
  }
}

export default function FoldersPage() {
  const queryClient = useQueryClient()
  const [explicitFid, setExplicitFid] = useState<string | null>(null)
  const [page, setPage] = useState(1)
  const [partsByBvid, setPartsByBvid] = useState<Record<string, PartInfo[]>>({})
  const [loadingBvids, setLoadingBvids] = useState<Set<string>>(new Set())

  const { event } = useTaskProgress()

  const selected = useSelectionStore((s) => s.selected)
  const toggle = useSelectionStore((s) => s.toggle)
  const selectMany = useSelectionStore((s) => s.selectMany)
  const clear = useSelectionStore((s) => s.clear)
  const selectedFolders = useSelectionStore((s) => s.selectedFolders)
  const toggleFolder = useSelectionStore((s) => s.toggleFolder)

  const videoPanelWidth = useUiStore((s) => s.videoPanelWidth)
  const setVideoPanelWidth = useUiStore((s) => s.setVideoPanelWidth)
  const startWidthRef = useRef(videoPanelWidth)

  const foldersQuery = useQuery({ queryKey: ['folders'], queryFn: listFolders })

  const folders = foldersQuery.data ?? []
  const activeFid =
    explicitFid ?? folders.find((f) => f.kind === 'uncategorized')?.id ?? folders[0]?.id ?? ''

  const videosQuery = useQuery({
    queryKey: ['folder-videos', activeFid, page],
    queryFn: () => listFolderVideos(activeFid, page, PAGE_SIZE),
    enabled: !!activeFid,
  })

  const syncMutation = useMutation({
    mutationFn: syncFolders,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['folders'] }),
  })

  // 任务进度事件驱动刷新：任务面板与视频列表的入库状态标签同步更新
  useEffect(() => {
    if (event) {
      queryClient.invalidateQueries({ queryKey: ['tasks'] })
      queryClient.invalidateQueries({ queryKey: ['folder-videos', activeFid, page] })
    }
  }, [event, activeFid, page, queryClient])

  const videos = videosQuery.data?.items ?? []
  const total = videosQuery.data?.total ?? 0

  const isSelected = (bvid: string) => Boolean(selected[`${bvid}:0`])
  const selectedPartCids = (bvid: string) =>
    new Set(
      Object.values(selected)
        .filter((t) => t.bvid === bvid && t.cid !== 0)
        .map((t) => t.cid),
    )

  const loadParts = async (bvid: string) => {
    if (partsByBvid[bvid] || loadingBvids.has(bvid)) return
    setLoadingBvids((prev) => new Set(prev).add(bvid))
    try {
      const parts = await listVideoParts(bvid)
      setPartsByBvid((prev) => ({ ...prev, [bvid]: parts }))
    } catch {
      /* 忽略单条解析失败 */
    } finally {
      setLoadingBvids((prev) => {
        const next = new Set(prev)
        next.delete(bvid)
        return next
      })
    }
  }

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
    const targets: Record<string, unknown>[] = []
    const seen = new Set<string>()
    for (const t of Object.values(selected)) {
      if (t.cid === 0) {
        // 整选视频：展开为所有分P
        try {
          const parts = await listVideoParts(t.bvid)
          for (const part of parts) {
            const k = `${t.bvid}:${part.cid}`
            if (seen.has(k)) continue
            seen.add(k)
            targets.push({
              bvid: t.bvid,
              cid: part.cid,
              title: t.title,
              part_title: part.part_title,
              cover_url: t.coverUrl,
              up_name: t.upName,
              pubdate: t.pubdate,
              duration: part.duration,
            })
          }
        } catch {
          /* 忽略单条解析失败 */
        }
      } else {
        const k = `${t.bvid}:${t.cid}`
        if (seen.has(k)) continue
        seen.add(k)
        targets.push({
          bvid: t.bvid,
          cid: t.cid,
          title: t.title,
          part_title: t.partTitle,
          cover_url: t.coverUrl,
          up_name: t.upName,
          pubdate: t.pubdate,
          duration: t.duration,
        })
      }
    }
    if (targets.length === 0) return
    await summarize(targets, activeFid || null)
    clear()
    queryClient.invalidateQueries({ queryKey: ['tasks'] })
  }

  const handleRetry = async (itemId: string) => {
    await retryItem(itemId)
    queryClient.invalidateQueries({ queryKey: ['tasks'] })
    queryClient.invalidateQueries({ queryKey: ['folder-videos', activeFid, page] })
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
            <div key={folder.id} className={styles.folderTab}>
              <Chip
                active={folder.id === activeFid}
                onClick={() => setExplicitFid(folder.id)}
                className={selectedFolders[folder.id] ? styles.scoped : undefined}
              >
                {folder.title}
              </Chip>
              <label className={styles.scopeToggle} title="纳入检索范围">
                <input
                  type="checkbox"
                  checked={Boolean(selectedFolders[folder.id])}
                  onChange={() => toggleFolder({ id: folder.id, title: folder.title })}
                />
              </label>
            </div>
          ))}
          <Button
            variant="ghost"
            onClick={() => syncMutation.mutate()}
            disabled={syncMutation.isPending}
          >
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
                parts: partsByBvid[video.bvid],
                partCount: video.part_count,
                partsStatus: video.parts_status,
              }}
              checked={isSelected(video.bvid)}
              onToggle={() => toggle(videoTarget(video))}
              onExpand={() => loadParts(video.bvid)}
              selectedCids={selectedPartCids(video.bvid)}
              onTogglePart={(part) => toggle(partTarget(video, part))}
              onRetry={handleRetry}
            />
          ))}
          {videos.length === 0 && <div className={styles.empty}>暂无视频</div>}
        </div>

        <Pagination page={page} pageSize={PAGE_SIZE} total={total} onChange={setPage} />

        <SelectionBar count={selectedCount} onStart={startSummarize} onClear={clear} />

        <TaskProgressPanel />
      </div>

      <div className={styles.divider} onMouseDown={handleDividerMouseDown} />

      <div className={styles.chatPanel}>
        <ChatWindow />
      </div>
    </div>
  )
}
