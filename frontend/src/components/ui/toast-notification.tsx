import { useEffect, useState } from 'react'
import { typography } from '@/lib/design-tokens'

interface ToastProps {
  message: string
  visible: boolean
  onDismiss?: () => void
  duration?: number
}

export function Toast({ message, visible, onDismiss, duration = 3000 }: ToastProps) {
  const [show, setShow] = useState(false)

  useEffect(() => {
    if (visible) {
      setShow(true)
      const timer = setTimeout(() => {
        setShow(false)
        onDismiss?.()
      }, duration)
      return () => clearTimeout(timer)
    } else {
      setShow(false)
    }
  }, [visible, duration, onDismiss])

  if (!show) return null

  return (
    <div
      className="fixed bottom-6 left-1/2 -translate-x-1/2 z-50 animate-fade-slide-up"
      style={{
        padding: '10px 20px',
        borderRadius: '12px',
        fontSize: typography.caption.size,
        fontWeight: '500',
        color: 'var(--card-bg)',
        backgroundColor: 'var(--heading-text)',
        boxShadow: '0 4px 12px rgba(0,0,0,0.15)',
        pointerEvents: 'none',
      }}
    >
      {message}
    </div>
  )
}
