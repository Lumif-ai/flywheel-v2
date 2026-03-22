import { useState, useCallback } from 'react'
import { useParams } from 'react-router'
import { Pencil, Check, X } from 'lucide-react'
import { Tabs, TabsList, TabsTrigger, TabsContent } from '@/components/ui/tabs'
import { Skeleton } from '@/components/ui/skeleton'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { useStreamDetail, useRenameStream } from '../hooks/useStreamDetail'
import { DensityBar } from './DensityIndicator'
import { StreamTimeline } from './StreamTimeline'
import { StreamIntelligence } from './StreamIntelligence'
import { StreamChat } from './StreamChat'

export function StreamDetailPage() {
  const { id } = useParams<{ id: string }>()
  const { data: stream, isLoading, error } = useStreamDetail(id ?? '')
  const renameMutation = useRenameStream()

  const [isEditing, setIsEditing] = useState(false)
  const [editName, setEditName] = useState('')

  const startEditing = useCallback(() => {
    if (stream) {
      setEditName(stream.name)
      setIsEditing(true)
    }
  }, [stream])

  const cancelEditing = useCallback(() => {
    setIsEditing(false)
    setEditName('')
  }, [])

  const saveName = useCallback(() => {
    const trimmed = editName.trim()
    if (!trimmed || !id || !stream || trimmed === stream.name) {
      cancelEditing()
      return
    }
    renameMutation.mutate(
      { id, name: trimmed },
      { onSuccess: () => setIsEditing(false) }
    )
  }, [editName, id, stream, renameMutation, cancelEditing])

  if (isLoading) {
    return (
      <div className="p-6 space-y-4">
        <Skeleton className="h-8 w-64" />
        <Skeleton className="h-2 w-full" />
        <Skeleton className="h-8 w-48" />
        <Skeleton className="h-64 w-full" />
      </div>
    )
  }

  if (error || !stream) {
    return (
      <div className="flex flex-col items-center justify-center py-20 text-center">
        <p className="text-lg font-medium">Stream not found</p>
        <p className="mt-1 text-sm text-muted-foreground">
          This work stream may have been deleted or you don't have access.
        </p>
      </div>
    )
  }

  return (
    <div className="p-6 space-y-6">
      {/* Header */}
      <div className="space-y-3">
        <div className="flex items-center gap-2">
          {isEditing ? (
            <div className="flex items-center gap-2">
              <Input
                value={editName}
                onChange={(e) => setEditName(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === 'Enter') saveName()
                  if (e.key === 'Escape') cancelEditing()
                }}
                className="h-9 text-xl font-bold"
                autoFocus
              />
              <Button size="icon" variant="ghost" onClick={saveName}>
                <Check className="size-4" />
              </Button>
              <Button size="icon" variant="ghost" onClick={cancelEditing}>
                <X className="size-4" />
              </Button>
            </div>
          ) : (
            <button
              onClick={startEditing}
              className="group flex items-center gap-2 text-left"
            >
              <h1 className="text-2xl font-bold">{stream.name}</h1>
              <Pencil className="size-4 text-muted-foreground opacity-0 transition-opacity group-hover:opacity-100" />
            </button>
          )}
        </div>

        <DensityBar score={stream.density_score} showLabel />
      </div>

      {/* Tabs */}
      <Tabs defaultValue="timeline">
        <TabsList>
          <TabsTrigger value="timeline">Timeline</TabsTrigger>
          <TabsTrigger value="intelligence">Intelligence</TabsTrigger>
          <TabsTrigger value="chat">Chat</TabsTrigger>
        </TabsList>

        <TabsContent value="timeline" className="mt-4">
          <StreamTimeline entries={stream.recent_entries} />
        </TabsContent>

        <TabsContent value="intelligence" className="mt-4">
          <StreamIntelligence
            entities={stream.entities}
            densityScore={stream.density_score}
          />
        </TabsContent>

        <TabsContent value="chat" className="mt-4">
          <StreamChat streamId={stream.id} />
        </TabsContent>
      </Tabs>
    </div>
  )
}
