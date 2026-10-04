import { useEffect, useRef, useState } from 'react'
import QRCode from 'qrcode'
import { generateQrcode, pollQrcode } from '../api/auth'
import { useAuthStore } from '../stores/auth'
import Dialog from './ui/Dialog'
import styles from './LoginModal.module.css'

type Phase = 'loading' | 'waiting' | 'pending' | 'expired' | 'success' | 'failed'

interface LoginModalProps {
  open: boolean
  onOpenChange: (open: boolean) => void
}

export default function LoginModal({ open, onOpenChange }: LoginModalProps) {
  const [phase, setPhase] = useState<Phase>('loading')
  const [qrDataUrl, setQrDataUrl] = useState('')
  const keyRef = useRef<string | null>(null)
  const setLoggedIn = useAuthStore((s) => s.setLoggedIn)

  useEffect(() => {
    if (!open) return

    let cancelled = false
    const start = async () => {
      setPhase('loading')
      try {
        const result = await generateQrcode()
        keyRef.current = result.qrcode_key
        const dataUrl = await QRCode.toDataURL(result.qrcode_url)
        if (!cancelled) {
          setQrDataUrl(dataUrl)
          setPhase('waiting')
        }
      } catch {
        if (!cancelled) setPhase('failed')
      }
    }
    start()

    const timer = setInterval(async () => {
      const key = keyRef.current
      if (!key) return
      try {
        const result = await pollQrcode(key)
        if (cancelled) return
        if (result.status === 'success') {
          setLoggedIn(true, result.user_name, result.user_mid)
          setPhase('success')
          clearInterval(timer)
          setTimeout(() => onOpenChange(false), 600)
        } else if (result.status === 'pending') {
          setPhase('pending')
        } else if (result.status === 'expired') {
          setPhase('expired')
        }
      } catch {
        if (!cancelled) setPhase('failed')
      }
    }, 2000)

    return () => {
      cancelled = true
      clearInterval(timer)
    }
  }, [open, onOpenChange, setLoggedIn])

  return (
    <Dialog open={open} onOpenChange={onOpenChange} title="登录 BiliRag">
      <div className={styles.body}>
        {phase === 'expired' ? (
          <button type="button" className={styles.refresh} onClick={() => onOpenChange(false)}>
            二维码已过期，请关闭后重试
          </button>
        ) : (
          qrDataUrl && <img className={styles.qr} src={qrDataUrl} alt="登录二维码" />
        )}
        <p className={styles.hint}>
          {phase === 'waiting' && '请使用 B 站 App 扫码登录'}
          {phase === 'pending' && '已扫码，请在手机上确认'}
          {phase === 'loading' && '加载二维码…'}
          {phase === 'success' && '登录成功'}
          {phase === 'failed' && '登录失败，请重试'}
        </p>
      </div>
    </Dialog>
  )
}
