import { useState } from 'react'
import { useMutation, useQuery } from '@tanstack/react-query'
import { useNavigate } from 'react-router-dom'
import { listFolders } from '../api/folders'
import { confirmImport, parseLinks } from '../api/import'
import type { VideoInfo } from '../api/types'
import VideoRow from '../components/VideoRow'
import Button from '../components/ui/Button'
import Select from '../components/ui/Select'
import styles from './ImportPage.module.css'

export default function ImportPage() {
  const [links, setLinks] = useState('')
  const [results, setResults] = useState<VideoInfo[]>([])
  const [selectedBvids, setSelectedBvids] = useState<Set<string>>(new Set())
  const [folderId, setFolderId] = useState('')
  const navigate = useNavigate()

  const foldersQuery = useQuery({ queryKey: ['folders'], queryFn: listFolders })

  const parseMutation = useMutation({
    mutationFn: () =>
      parseLinks(
        links
          .split('\n')
          .map((l) => l.trim())
          .filter(Boolean),
      ),
    onSuccess: (data) => {
      setResults(data)
      setSelectedBvids(new Set(data.filter((d) => !d.error).map((d) => d.bvid)))
    },
  })

  const confirmMutation = useMutation({
    mutationFn: () => {
      const targets = results.flatMap((video) =>
        selectedBvids.has(video.bvid)
          ? video.parts.map((p) => ({
              bvid: video.bvid,
              cid: p.cid,
              title: video.title,
              part_title: p.part_title,
              cover_url: video.cover_url,
              up_name: video.up_name,
              pubdate: video.pubdate,
              duration: p.duration,
            }))
          : [],
      )
      return confirmImport(targets, folderId || null)
    },
    onSuccess: () => navigate('/folders'),
  })

  const toggleBvid = (bvid: string) => {
    setSelectedBvids((prev) => {
      const next = new Set(prev)
      if (next.has(bvid)) next.delete(bvid)
      else next.add(bvid)
      return next
    })
  }

  return (
    <div className={styles.page}>
      <h2 className={styles.heading}>粘贴 B 站链接（每行一个）</h2>
      <textarea
        className={styles.textarea}
        value={links}
        onChange={(e) => setLinks(e.target.value)}
        placeholder={'BV1xx...\nb23.tv/xxx\nhttps://www.bilibili.com/video/BV...'}
        rows={6}
      />
      <Button onClick={() => parseMutation.mutate()} disabled={parseMutation.isPending}>
        解析
      </Button>

      {parseMutation.isPending && <div className={styles.hint}>解析中…</div>}

      {results.length > 0 && (
        <div className={styles.results}>
          {results.map((video) =>
            video.error ? (
              <div key={video.bvid ?? video.error} className={styles.errorRow}>
                解析失败：{video.error}
              </div>
            ) : (
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
                  parts: video.parts,
                }}
                checked={selectedBvids.has(video.bvid)}
                onToggle={() => toggleBvid(video.bvid)}
              />
            ),
          )}
          <div className={styles.confirmRow}>
            <Select value={folderId} onChange={(e) => setFolderId(e.target.value)}>
              <option value="">未分类</option>
              {(foldersQuery.data ?? [])
                .filter((f) => f.kind !== 'uncategorized')
                .map((f) => (
                  <option key={f.id} value={f.id}>
                    {f.title}
                  </option>
                ))}
            </Select>
            <Button onClick={() => confirmMutation.mutate()} disabled={confirmMutation.isPending}>
              确认导入
            </Button>
          </div>
        </div>
      )}
    </div>
  )
}
