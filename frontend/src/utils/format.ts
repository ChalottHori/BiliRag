export function formatDuration(seconds: number): string {
  const s = Math.max(0, Math.floor(seconds))
  const m = Math.floor(s / 60)
  const r = s % 60
  return `${String(m).padStart(2, '0')}:${String(r).padStart(2, '0')}`
}

/** 条目标题：视频标题为主；分P标题与视频标题不同时拼成「视频标题 · 分P标题」。 */
export function formatItemTitle(title: string, partTitle: string): string {
  if (!title) return partTitle
  if (!partTitle || partTitle === title) return title
  return `${title} · ${partTitle}`
}
