import { useEffect, useRef, useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { getConfig, updateConfig } from '../api/config'
import Button from '../components/ui/Button'
import Input from '../components/ui/Input'
import Select from '../components/ui/Select'
import Switch from '../components/ui/Switch'
import styles from './SettingsPage.module.css'

type Section = 'llm' | 'asr' | 'data' | 'concurrency' | 'embedding' | 'backup'

const SECTIONS: { key: Section; label: string }[] = [
  { key: 'llm', label: 'LLM' },
  { key: 'asr', label: 'ASR' },
  { key: 'data', label: '数据目录' },
  { key: 'concurrency', label: '并发' },
  { key: 'embedding', label: 'Embedding' },
  { key: 'backup', label: '备份' },
]

export default function SettingsPage() {
  const queryClient = useQueryClient()
  const [section, setSection] = useState<Section>('llm')
  const [form, setForm] = useState<Record<string, string | boolean | number>>({})

  const configQuery = useQuery({
    queryKey: ['config'],
    queryFn: getConfig,
    refetchOnWindowFocus: false,
    refetchOnReconnect: false,
  })

  // 仅首次加载时用后端配置初始化表单；后续 refetch（如保存后）不再覆盖用户正在编辑的值
  const initializedRef = useRef(false)
  useEffect(() => {
    const data = configQuery.data
    if (!data || initializedRef.current) return
    initializedRef.current = true
    setForm({
      llm_base_url: data.llm_base_url,
      llm_api_key: '',
      llm_model: data.llm_model,
      qa_llm_model: data.qa_llm_model,
      asr_model: data.asr_model,
      concurrency: data.concurrency,
      export_dir: data.export_dir,
      keep_audio: data.keep_audio,
      chunk_size: data.chunk_size,
      top_k: data.top_k,
      chat_use_react: data.chat_use_react,
      embedding_provider: data.embedding_provider,
      embedding_model: data.embedding_model,
    })
  }, [configQuery.data])

  const saveMutation = useMutation({
    mutationFn: (data: Record<string, unknown>) => updateConfig(data),
    onSuccess: () => {
      setForm((prev) => ({ ...prev, llm_api_key: '' }))
      queryClient.invalidateQueries({ queryKey: ['config'] })
    },
  })

  const set = (key: string, value: string | boolean | number) =>
    setForm((prev) => ({ ...prev, [key]: value }))

  const save = () => {
    const payload: Record<string, unknown> = {
      asr_model: form.asr_model,
      concurrency: Number(form.concurrency),
      keep_audio: Boolean(form.keep_audio),
      chunk_size: Number(form.chunk_size),
      top_k: Number(form.top_k),
      chat_use_react: Boolean(form.chat_use_react),
      embedding_provider: form.embedding_provider,
      embedding_model: form.embedding_model,
    }
    if (form.llm_base_url) payload.llm_base_url = form.llm_base_url
    if (form.llm_api_key) payload.llm_api_key = form.llm_api_key
    if (form.llm_model) payload.llm_model = form.llm_model
    if (form.qa_llm_model) payload.qa_llm_model = form.qa_llm_model
    if (form.export_dir) payload.export_dir = form.export_dir
    saveMutation.mutate(payload)
  }

  return (
    <div className={styles.page}>
      <div className={styles.nav}>
        {SECTIONS.map((s) => (
          <button
            key={s.key}
            type="button"
            className={s.key === section ? styles.navActive : styles.navItem}
            onClick={() => setSection(s.key)}
          >
            {s.label}
          </button>
        ))}
      </div>

      <div className={styles.form}>
        {section === 'llm' && (
          <>
            <Field label="base_url">
              <Input
                value={String(form.llm_base_url ?? '')}
                onChange={(e) => set('llm_base_url', e.target.value)}
              />
            </Field>
            <Field label="api_key（留空不修改）">
              <Input
                type="password"
                value={String(form.llm_api_key ?? '')}
                onChange={(e) => set('llm_api_key', e.target.value)}
              />
            </Field>
            <Field label="要点总结模型">
              <Input
                value={String(form.llm_model ?? '')}
                onChange={(e) => set('llm_model', e.target.value)}
              />
            </Field>
            <Field label="问答模型">
              <Input
                value={String(form.qa_llm_model ?? '')}
                onChange={(e) => set('qa_llm_model', e.target.value)}
              />
            </Field>
            <Field label="多步检索（ReAct）">
              <Switch
                checked={Boolean(form.chat_use_react)}
                onCheckedChange={(v) => set('chat_use_react', v)}
              />
            </Field>
          </>
        )}

        {section === 'asr' && (
          <Field label="ASR 模型">
            <Select
              value={String(form.asr_model ?? 'medium')}
              onChange={(e) => set('asr_model', e.target.value)}
            >
              <option value="small" style={{ color: '#000' }}>small</option>
              <option value="medium" style={{ color: '#000' }}>medium</option>
              <option value="large-v3" style={{ color: '#000' }}>large-v3</option>
            </Select>
          </Field>
        )}

        {section === 'data' && (
          <>
            <Field label="导出目录">
              <Input
                value={String(form.export_dir ?? '')}
                onChange={(e) => set('export_dir', e.target.value)}
              />
            </Field>
            <Field label="保留音频">
              <Switch
                checked={Boolean(form.keep_audio)}
                onCheckedChange={(v) => set('keep_audio', v)}
              />
            </Field>
          </>
        )}

        {section === 'concurrency' && (
          <>
            <Field label="并发数">
              <Input
                type="number"
                value={String(form.concurrency ?? 1)}
                onChange={(e) => set('concurrency', Number(e.target.value))}
              />
            </Field>
            <Field label="切块字数">
              <Input
                type="number"
                value={String(form.chunk_size ?? 1000)}
                onChange={(e) => set('chunk_size', Number(e.target.value))}
              />
            </Field>
            <Field label="检索条数">
              <Input
                type="number"
                value={String(form.top_k ?? 5)}
                onChange={(e) => set('top_k', Number(e.target.value))}
              />
            </Field>
          </>
        )}

        {section === 'embedding' && (
          <>
            <Field label="Provider">
              <Select
                value={String(form.embedding_provider ?? 'local')}
                onChange={(e) => set('embedding_provider', e.target.value)}
              >
                <option value="local" style={{ color: '#000' }}>local</option>
                <option value="api" style={{ color: '#000' }}>api</option>
              </Select>
            </Field>
            <Field label="模型">
              <Input
                value={String(form.embedding_model ?? '')}
                onChange={(e) => set('embedding_model', e.target.value)}
              />
            </Field>
          </>
        )}

        {section === 'backup' && (
          <div className={styles.backup}>
            <p>数据目录：{configQuery.data?.data_dir}</p>
            <Button variant="secondary">立即备份（复制数据目录）</Button>
          </div>
        )}

        <Button onClick={save} disabled={saveMutation.isPending}>
          保存
        </Button>
      </div>
    </div>
  )
}

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <label className={styles.field}>
      <span className={styles.fieldLabel}>{label}</span>
      {children}
    </label>
  )
}
