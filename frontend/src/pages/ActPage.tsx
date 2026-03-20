import { useEffect, useRef } from 'react'
import { MessageSquare, Search, Users, Briefcase } from 'lucide-react'
import { ScrollArea } from '@/components/ui/scroll-area'
import { ChatInput } from '@/features/chat/components/ChatInput'
import { ChatMessage } from '@/features/chat/components/ChatMessage'
import { useChatStore } from '@/features/chat/store'

const SUGGESTIONS = [
  { icon: Search, label: 'Research Acme Corp' },
  { icon: Users, label: 'Prepare for my next meeting' },
  { icon: Briefcase, label: 'What do we know about...' },
]

export function ActPage() {
  const messages = useChatStore((s) => s.messages)
  const sendMessage = useChatStore((s) => s.sendMessage)
  const bottomRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  return (
    <div className="flex h-full flex-col">
      <ScrollArea className="flex-1 px-4">
        {messages.length === 0 ? (
          <div className="flex h-full min-h-[60vh] flex-col items-center justify-center gap-6">
            <div className="text-center">
              <MessageSquare className="mx-auto mb-3 h-10 w-10 text-muted-foreground/50" />
              <h2 className="text-xl font-semibold text-foreground">
                Start a conversation
              </h2>
              <p className="mt-1 text-sm text-muted-foreground">
                Ask Flywheel to research, prepare, or analyze anything
              </p>
            </div>
            <div className="flex flex-wrap justify-center gap-2">
              {SUGGESTIONS.map(({ icon: Icon, label }) => (
                <button
                  key={label}
                  type="button"
                  onClick={() => sendMessage(label)}
                  className="flex items-center gap-2 rounded-full border bg-background px-4 py-2 text-sm text-muted-foreground transition-colors hover:border-primary hover:text-foreground"
                >
                  <Icon className="h-4 w-4" />
                  {label}
                </button>
              ))}
            </div>
          </div>
        ) : (
          <div className="mx-auto max-w-3xl space-y-4 py-4">
            {messages.map((msg) => (
              <ChatMessage key={msg.id} message={msg} />
            ))}
            <div ref={bottomRef} />
          </div>
        )}
      </ScrollArea>

      <div className="mx-auto w-full max-w-3xl">
        <ChatInput />
      </div>
    </div>
  )
}
