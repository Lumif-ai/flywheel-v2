import { useEffect } from 'react'
import { useChatStore } from '@/features/chat/store'
import { ChatInput } from '@/features/chat/components/ChatInput'

interface StreamChatProps {
  streamId: string
}

export function StreamChat({ streamId }: StreamChatProps) {
  const messages = useChatStore((s) => s.messages)

  useEffect(() => {
    useChatStore.getState().setStreamId(streamId)

    return () => {
      useChatStore.getState().setStreamId(null)
    }
  }, [streamId])

  return (
    <div className="flex h-full flex-col">
      <div className="flex-1 space-y-3 overflow-y-auto p-1">
        {messages.length === 0 ? (
          <div className="flex flex-col items-center justify-center py-12 text-center">
            <p className="text-sm text-muted-foreground">
              Chat about this work stream...
            </p>
          </div>
        ) : (
          messages.map((msg) => (
            <div
              key={msg.id}
              className={`rounded-lg px-3 py-2 text-sm ${
                msg.role === 'user'
                  ? 'ml-auto max-w-[80%] bg-primary text-primary-foreground'
                  : 'mr-auto max-w-[80%] bg-muted'
              }`}
            >
              {msg.content}
            </div>
          ))
        )}
      </div>
      <ChatInput />
    </div>
  )
}
