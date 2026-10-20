import { useQuery } from '@tanstack/react-query'
import { getTasks } from '../api/summarize'

/**
 * 是否存在正在执行的入库任务（存在非终态条目，即 `active > 0`）。
 * 复用 `['tasks']` 查询（与 `TaskProgressPanel` 同 key，React Query 自动去重）。
 */
export function useTasksRunning(): boolean {
  const { data } = useQuery({ queryKey: ['tasks'], queryFn: getTasks, refetchInterval: 3000 })
  return (data?.active ?? 0) > 0
}
