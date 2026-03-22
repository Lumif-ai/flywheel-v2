import { useState } from 'react'
import { CalendarIcon, CheckIcon, XIcon } from 'lucide-react'
import type { BriefingCard as BriefingCardType } from '@/types/streams'
import { useClassifyMeeting, useDismissCard } from '../hooks/useBriefing'
import { useStreams } from '../hooks/useStreams'

interface MeetingClassificationCardProps {
  card: BriefingCardType
}

export function MeetingClassificationCard({
  card,
}: MeetingClassificationCardProps) {
  const [classified, setClassified] = useState(false)
  const [classifiedStreamName, setClassifiedStreamName] = useState('')
  const classifyMutation = useClassifyMeeting()
  const dismissMutation = useDismissCard()
  const { data: streamsData } = useStreams()

  const streams = streamsData?.items ?? []
  const workItemId = card.metadata?.work_item_id
    ? String(card.metadata.work_item_id)
    : ''

  // Extract external domain from metadata for display
  const attendees = (card.metadata?.attendees as string[]) ?? []
  const externalDomains = attendees
    .filter((e) => e.includes('@'))
    .map((e) => e.split('@')[1])
    .filter((d, i, arr) => arr.indexOf(d) === i)

  const handleClassify = (streamId: string, streamName: string) => {
    if (!workItemId) return
    setClassified(true)
    setClassifiedStreamName(streamName)
    classifyMutation.mutate({ work_item_id: workItemId, stream_id: streamId })
  }

  const handleSkip = () => {
    dismissMutation.mutate({
      card_type: 'meeting',
      suggestion_key: workItemId,
    })
  }

  if (classified) {
    return (
      <div className="rounded-xl border border-green-200 bg-green-50/50 p-4 text-center transition-opacity duration-300">
        <div className="flex items-center justify-center gap-2 text-sm text-green-700">
          <CheckIcon className="h-4 w-4" />
          Assigned to {classifiedStreamName}
        </div>
      </div>
    )
  }

  return (
    <div className="rounded-xl border border-blue-200 bg-blue-50/30 p-4">
      <div className="flex items-start gap-3">
        <CalendarIcon className="mt-0.5 h-5 w-5 shrink-0 text-blue-500" />
        <div className="min-w-0 flex-1">
          <h3 className="font-medium leading-tight">{card.title}</h3>
          <p className="mt-1 text-sm text-muted-foreground">{card.body}</p>
          {externalDomains.length > 0 && (
            <p className="mt-1 text-xs text-muted-foreground/70">
              External: {externalDomains.join(', ')}
            </p>
          )}

          {/* Stream picker */}
          <div className="mt-3">
            <p className="mb-2 text-xs font-medium text-muted-foreground">
              Assign to stream:
            </p>
            <div className="flex flex-wrap gap-1.5">
              {streams.map((stream) => (
                <button
                  key={stream.id}
                  onClick={() => handleClassify(stream.id, stream.name)}
                  disabled={classifyMutation.isPending}
                  className="rounded-full border border-border bg-background px-3 py-1 text-xs font-medium transition-colors hover:border-primary hover:bg-primary/5 hover:text-primary disabled:opacity-50"
                >
                  {stream.name}
                </button>
              ))}
            </div>
          </div>

          {/* Skip link */}
          <div className="mt-2">
            <button
              onClick={handleSkip}
              className="text-xs text-muted-foreground/60 hover:text-muted-foreground transition-colors"
            >
              Skip
            </button>
          </div>
        </div>
      </div>
    </div>
  )
}
