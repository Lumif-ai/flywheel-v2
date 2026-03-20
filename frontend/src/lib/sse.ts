import { useEffect, useRef, useCallback } from 'react'
import { useAuthStore } from '@/stores/auth'

type SSEEventType = 'thinking' | 'text' | 'skill_start' | 'clarify' | 'error' | 'done'

interface SSEEvent {
  type: SSEEventType
  data: Record<string, unknown>
}

export function useSSE(
  url: string | null,
  onEvent: (event: SSEEvent) => void,
) {
  const sourceRef = useRef<EventSource | null>(null)
  const token = useAuthStore((s) => s.token)
  const onEventRef = useRef(onEvent)
  onEventRef.current = onEvent

  const close = useCallback(() => {
    sourceRef.current?.close()
    sourceRef.current = null
  }, [])

  useEffect(() => {
    if (!url) return

    // EventSource doesn't support custom headers, so pass token as query param
    const fullUrl = token
      ? `${url}${url.includes('?') ? '&' : '?'}token=${token}`
      : url
    const source = new EventSource(fullUrl)
    sourceRef.current = source

    const eventTypes: SSEEventType[] = ['thinking', 'text', 'skill_start', 'clarify', 'error', 'done']
    for (const type of eventTypes) {
      source.addEventListener(type, (e: MessageEvent) => {
        const data = JSON.parse(e.data)
        onEventRef.current({ type, data })
        if (type === 'done') {
          source.close()
        }
      })
    }

    source.onerror = () => {
      source.close()
      onEventRef.current({ type: 'error', data: { message: 'Connection lost' } })
    }

    return () => {
      source.close()
      sourceRef.current = null
    }
  }, [url, token])

  return { close }
}
