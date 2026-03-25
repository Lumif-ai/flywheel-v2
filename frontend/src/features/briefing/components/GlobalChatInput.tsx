import { useState, useEffect } from 'react'
import { useNavigate } from 'react-router'
import { SendIcon } from 'lucide-react'
import { useChatStore } from '@/features/chat/store'

interface GlobalChatInputProps {
  placeholder?: string
  /** Optional gate: return false to prevent submission (e.g., for signup gate). */
  onBeforeSubmit?: (input: string) => boolean
}

export function GlobalChatInput({ placeholder = 'Ask Flywheel anything...', onBeforeSubmit }: GlobalChatInputProps) {
  const [value, setValue] = useState('')
  const navigate = useNavigate()
  const sendMessage = useChatStore((s) => s.sendMessage)
  const setStreamId = useChatStore((s) => s.setStreamId)

  useEffect(() => {
    setStreamId(null)
  }, [setStreamId])

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    const trimmed = value.trim()
    if (!trimmed) return

    // Allow caller to gate the submission (e.g., for signup gate)
    if (onBeforeSubmit && !onBeforeSubmit(trimmed)) return

    setValue('')
    await sendMessage(trimmed)
    navigate('/chat')
  }

  return (
    <form onSubmit={handleSubmit} className="flex items-center gap-2">
      <input
        type="text"
        value={value}
        onChange={(e) => setValue(e.target.value)}
        placeholder={placeholder}
        className="flex-1 rounded-lg border border-input bg-background px-4 py-2.5 text-sm placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-ring"
      />
      <button
        type="submit"
        disabled={!value.trim()}
        className="inline-flex h-10 w-10 items-center justify-center rounded-lg bg-primary text-primary-foreground transition-colors hover:bg-primary/90 disabled:opacity-50"
      >
        <SendIcon className="h-4 w-4" />
      </button>
    </form>
  )
}
