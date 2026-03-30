import { useState, useEffect, useRef } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { Loader2 } from 'lucide-react'
import { toast } from 'sonner'
import { api } from '@/lib/api'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
} from '@/components/ui/dialog'

interface VoiceProfile {
  tone: string | null
  avg_length: number | null
  sign_off: string | null
  phrases: string[]
  formality_level: string | null
  greeting_style: string | null
  question_style: string | null
  paragraph_pattern: string | null
  emoji_usage: string | null
  avg_sentences: number | null
  samples_analyzed: number
  updated_at: string
}

const FIELD_LABELS: { key: keyof VoiceProfile; label: string }[] = [
  { key: 'tone', label: 'Tone' },
  { key: 'formality_level', label: 'Formality Level' },
  { key: 'greeting_style', label: 'Greeting Style' },
  { key: 'sign_off', label: 'Sign-off' },
  { key: 'avg_length', label: 'Average Length' },
  { key: 'avg_sentences', label: 'Average Sentences' },
  { key: 'paragraph_pattern', label: 'Paragraph Pattern' },
  { key: 'question_style', label: 'Question Style' },
  { key: 'emoji_usage', label: 'Emoji Usage' },
  { key: 'phrases', label: 'Common Phrases' },
]

const EDITABLE_FIELDS = new Set(['tone', 'sign_off'])

function formatFieldValue(key: keyof VoiceProfile, value: unknown): string {
  if (value === null || value === undefined) return 'Not detected'
  if (key === 'phrases') {
    const arr = value as string[]
    return arr.length > 0 ? arr.join(', ') : 'Not detected'
  }
  if (key === 'avg_length' || key === 'avg_sentences') {
    return String(value)
  }
  return String(value)
}

export function VoiceProfileSettings() {
  const queryClient = useQueryClient()
  const [editTone, setEditTone] = useState('')
  const [editSignOff, setEditSignOff] = useState('')
  const [resetDialogOpen, setResetDialogOpen] = useState(false)
  const justReset = useRef(false)

  const { data: profile, isLoading } = useQuery({
    queryKey: ['voice-profile'],
    queryFn: () => api.get<VoiceProfile | null>('/email/voice-profile'),
  })

  // Sync local edit state when profile data changes
  useEffect(() => {
    if (profile) {
      setEditTone(profile.tone ?? '')
      setEditSignOff(profile.sign_off ?? '')
    }
  }, [profile])

  const saveMutation = useMutation({
    mutationFn: (updates: { tone?: string; sign_off?: string }) =>
      api.patch('/email/voice-profile', updates),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['voice-profile'] })
      toast.success('Voice profile updated')
    },
    onError: (err: Error) => {
      toast.error(err.message || 'Failed to update voice profile')
    },
  })

  const resetMutation = useMutation({
    mutationFn: () => api.post('/email/voice-profile/reset'),
    onSuccess: () => {
      justReset.current = true
      setResetDialogOpen(false)
      queryClient.invalidateQueries({ queryKey: ['voice-profile'] })
      toast.success('Re-learning your voice from sent emails...')
    },
    onError: (err: Error) => {
      toast.error(err.message || 'Failed to reset voice profile')
    },
  })

  if (isLoading) {
    return (
      <div className="flex items-center justify-center py-12">
        <Loader2 className="size-6 animate-spin text-muted-foreground" />
      </div>
    )
  }

  // No profile state
  if (!profile) {
    return (
      <div className="space-y-4">
        <div>
          <h3 className="text-base font-semibold text-foreground">Voice Profile</h3>
        </div>
        <div className="rounded-lg border p-6 text-center">
          <p className="text-sm text-muted-foreground">
            {justReset.current
              ? 'Re-learning your voice from sent emails... This usually takes about a minute.'
              : 'No voice profile yet. Connect Gmail to get started.'}
          </p>
        </div>
      </div>
    )
  }

  // Clear justReset flag when profile exists again
  justReset.current = false

  const toneChanged = editTone !== (profile.tone ?? '')
  const signOffChanged = editSignOff !== (profile.sign_off ?? '')
  const hasChanges = toneChanged || signOffChanged

  const handleSave = () => {
    const updates: { tone?: string; sign_off?: string } = {}
    if (toneChanged) updates.tone = editTone
    if (signOffChanged) updates.sign_off = editSignOff
    saveMutation.mutate(updates)
  }

  return (
    <div className="space-y-6">
      <div>
        <h3 className="text-base font-semibold text-foreground">Voice Profile</h3>
        <p className="text-sm text-muted-foreground mt-1">
          Learned from {profile.samples_analyzed} emails
        </p>
      </div>

      <div className="rounded-lg border p-6 space-y-4">
        {FIELD_LABELS.map(({ key, label }) => {
          const isEditable = EDITABLE_FIELDS.has(key)
          const value = profile[key]

          return (
            <div key={key}>
              <label className="text-sm font-medium text-foreground">{label}</label>
              {isEditable ? (
                <Input
                  className="mt-1"
                  value={key === 'tone' ? editTone : editSignOff}
                  onChange={(e) =>
                    key === 'tone'
                      ? setEditTone(e.target.value)
                      : setEditSignOff(e.target.value)
                  }
                  placeholder={label}
                />
              ) : (
                <p className="text-sm text-muted-foreground mt-1">
                  {key === 'phrases' ? (
                    (value as string[])?.length > 0 ? (
                      <span className="flex flex-wrap gap-1.5 mt-1">
                        {(value as string[]).map((phrase, i) => (
                          <span
                            key={i}
                            className="inline-flex items-center rounded-full border px-2.5 py-0.5 text-xs"
                          >
                            {phrase}
                          </span>
                        ))}
                      </span>
                    ) : (
                      'Not detected'
                    )
                  ) : (
                    formatFieldValue(key, value)
                  )}
                </p>
              )}
            </div>
          )
        })}
      </div>

      <div className="flex items-center gap-3">
        <Button
          onClick={handleSave}
          disabled={!hasChanges || saveMutation.isPending}
        >
          {saveMutation.isPending ? (
            <>
              <Loader2 className="size-4 animate-spin" />
              Saving...
            </>
          ) : (
            'Save'
          )}
        </Button>

        <Button
          variant="outline"
          onClick={() => setResetDialogOpen(true)}
          className="text-destructive hover:text-destructive border-destructive/30 hover:border-destructive/60"
        >
          Reset & Relearn
        </Button>
      </div>

      <Dialog open={resetDialogOpen} onOpenChange={setResetDialogOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Reset & Relearn Voice Profile?</DialogTitle>
            <DialogDescription>
              This will delete your current voice profile and re-analyze your sent
              emails to build a new one. The re-learning process usually takes about
              a minute.
            </DialogDescription>
          </DialogHeader>
          <div className="flex justify-end gap-2 pt-4">
            <Button variant="outline" onClick={() => setResetDialogOpen(false)}>
              Cancel
            </Button>
            <Button
              variant="destructive"
              onClick={() => resetMutation.mutate()}
              disabled={resetMutation.isPending}
            >
              {resetMutation.isPending ? (
                <>
                  <Loader2 className="size-4 animate-spin" />
                  Resetting...
                </>
              ) : (
                'Reset & Relearn'
              )}
            </Button>
          </div>
        </DialogContent>
      </Dialog>
    </div>
  )
}
