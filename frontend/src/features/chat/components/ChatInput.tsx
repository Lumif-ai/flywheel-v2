import { useState, useCallback, type KeyboardEvent } from 'react'
import { Send } from 'lucide-react'
import { Textarea } from '@/components/ui/textarea'
import { Button } from '@/components/ui/button'
import { useChatStore } from '../store'

export function ChatInput() {
  const [value, setValue] = useState('')
  const streamStatus = useChatStore((s) => s.streamState.status)
  const sendMessage = useChatStore((s) => s.sendMessage)

  const isDisabled =
    streamStatus === 'thinking' ||
    streamStatus === 'streaming' ||
    streamStatus === 'running'

  const handleSubmit = useCallback(() => {
    const trimmed = value.trim()
    if (!trimmed || isDisabled) return
    sendMessage(trimmed)
    setValue('')
  }, [value, isDisabled, sendMessage])

  const handleKeyDown = useCallback(
    (e: KeyboardEvent<HTMLTextAreaElement>) => {
      if (e.key === 'Enter' && !e.shiftKey) {
        e.preventDefault()
        handleSubmit()
      }
    },
    [handleSubmit],
  )

  return (
    <div className="flex items-end gap-2 border-t bg-background p-4">
      <Textarea
        value={value}
        onChange={(e) => setValue(e.target.value)}
        onKeyDown={handleKeyDown}
        placeholder="Ask Flywheel anything..."
        disabled={isDisabled}
        rows={1}
        className="min-h-[44px] max-h-[200px] resize-none"
      />
      <Button
        onClick={handleSubmit}
        disabled={isDisabled || !value.trim()}
        size="icon"
        className="shrink-0"
      >
        <Send className="h-4 w-4" />
      </Button>
    </div>
  )
}
