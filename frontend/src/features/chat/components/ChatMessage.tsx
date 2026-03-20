import { cn } from '@/lib/cn'
import type { ChatMessage as ChatMessageType } from '../types'
import { ChatStream } from './ChatStream'
import { SkillOutput } from './SkillOutput'

interface ChatMessageProps {
  message: ChatMessageType
}

export function ChatMessage({ message }: ChatMessageProps) {
  const isUser = message.role === 'user'

  return (
    <div className={cn('flex w-full', isUser ? 'justify-end' : 'justify-start')}>
      <div
        className={cn(
          'max-w-[80%] rounded-2xl px-4 py-2',
          isUser
            ? 'bg-primary text-primary-foreground'
            : 'bg-muted text-foreground',
        )}
      >
        {message.content && (
          <p className="text-sm whitespace-pre-wrap">{message.content}</p>
        )}

        {message.status === 'streaming' && message.runId && (
          <ChatStream runId={message.runId} />
        )}

        {message.outputHtml && <SkillOutput html={message.outputHtml} />}
      </div>
    </div>
  )
}
