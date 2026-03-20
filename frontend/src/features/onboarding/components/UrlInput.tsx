import { useState, useCallback, type KeyboardEvent } from 'react'
import { ArrowRight } from 'lucide-react'
import { Input } from '@/components/ui/input'
import { Button } from '@/components/ui/button'

interface UrlInputProps {
  onSubmit: (url: string) => void
  disabled?: boolean
}

function normalizeUrl(input: string): string {
  const trimmed = input.trim()
  if (!trimmed) return ''
  if (/^https?:\/\//i.test(trimmed)) return trimmed
  return `https://${trimmed}`
}

function isValidUrl(url: string): boolean {
  try {
    const parsed = new URL(url)
    return parsed.protocol === 'http:' || parsed.protocol === 'https:'
  } catch {
    return false
  }
}

export function UrlInput({ onSubmit, disabled }: UrlInputProps) {
  const [value, setValue] = useState('')
  const [error, setError] = useState<string | null>(null)

  const handleSubmit = useCallback(() => {
    const url = normalizeUrl(value)
    if (!url) return
    if (!isValidUrl(url)) {
      setError('Please enter a valid URL')
      return
    }
    setError(null)
    onSubmit(url)
  }, [value, onSubmit])

  const handleKeyDown = useCallback(
    (e: KeyboardEvent<HTMLInputElement>) => {
      if (e.key === 'Enter') {
        e.preventDefault()
        handleSubmit()
      }
    },
    [handleSubmit],
  )

  return (
    <div className="mx-auto max-w-xl space-y-4 text-center">
      <div className="space-y-2">
        <h1 className="text-3xl font-bold tracking-tight text-foreground">
          See Flywheel in action
        </h1>
        <p className="text-muted-foreground">
          No account required -- enter a company URL to get started
        </p>
      </div>

      <div className="flex gap-2">
        <Input
          value={value}
          onChange={(e) => {
            setValue(e.target.value)
            setError(null)
          }}
          onKeyDown={handleKeyDown}
          placeholder="Enter a company URL to get started"
          disabled={disabled}
          className="h-12 text-base"
        />
        <Button
          onClick={handleSubmit}
          disabled={disabled || !value.trim()}
          size="lg"
          className="h-12 gap-2 px-6"
        >
          Analyze
          <ArrowRight className="h-4 w-4" />
        </Button>
      </div>

      {error && (
        <p className="text-sm text-destructive">{error}</p>
      )}
    </div>
  )
}
