// 与后端 schemas / §7 API 对齐的类型定义

export interface Folder {
  id: string
  fid: string | null
  title: string
  kind: string
  media_count: number
  is_watch_later: boolean
  synced_at: string | null
}

export interface PartInfo {
  cid: number
  page: number
  part_title: string
  duration: number
  item_status?: ItemStatus | null
}

export interface ItemStatus {
  item_id: string
  status: string
  error_msg: string
}

export interface TaskItem {
  item_id: string
  title: string
  part_title: string
  status: string
  error_msg: string
}

export interface TaskSnapshot {
  batch_id: string | null
  total: number
  done: number
  failed: number
  active: number
  items: TaskItem[]
}

export interface VideoInfo {
  bvid: string
  aid: number
  title: string
  cover_url: string
  up_name: string
  pubdate: number
  duration: number
  is_collection: boolean
  is_invalid: boolean
  parts: PartInfo[]
  error?: string
}

export interface Item {
  id: string
  bvid: string
  aid: number
  cid: number
  title: string
  part_title: string
  cover_url: string
  up_name: string
  pubdate: string | null
  duration: number
  source_type: string
  folder_id: string | null
  status: string
  error_msg: string
  chunk_count: number
  imported_at: string
  updated_at: string
}

export interface Summary {
  title: string
  overview: string
  points: string[]
  keywords: string[]
}

export interface ItemDetail extends Item {
  summary: Summary | null
  transcript_snippet: string
}

export interface Citation {
  item_id: string
  bvid: string
  cid: number
  title: string
  chunk_idx: number
  snippet: string
}

export interface Source {
  bvid: string
  title: string
  url: string
  snippet: string
}

export interface ChatFilter {
  folder_ids?: string[]
  bvids?: string[]
}

export interface RetrievalTrace {
  vector_count: number
  keyword_count: number
  final_count: number
  elapsed_ms: number
}

export interface AgentStep {
  kind: 'tool_call' | 'observation'
  tool: string
  label: string
}

export interface TraceStep {
  route?: string
  label?: string
  retrieval?: RetrievalTrace
  steps?: AgentStep[]
}

export interface VerificationIssue {
  type: string
  source?: string
  claim?: string
  reason?: string
}

export interface Verdict {
  verdict: string
  issues: VerificationIssue[]
}

export interface ChatSession {
  id: string
  title: string
  pinned: boolean
  created_at: string
  updated_at: string
  message_count?: number
}

export interface ChatMessage {
  id: string
  session_id: string
  role: string
  content: string
  citations_json: Citation[] | null
  verdict_json: Verdict | null
  created_at: string
}

export interface Settings {
  llm_base_url: string
  llm_api_key_masked: string
  llm_model: string
  qa_llm_model: string
  asr_model: string
  concurrency: number
  data_dir: string
  export_dir: string
  keep_audio: boolean
  chunk_size: number
  top_k: number
  chat_use_react: boolean
  chat_use_verification: boolean
  embedding_provider: string
  embedding_model: string
}
