import { useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Eye, EyeOff, CheckCircle2, XCircle, Loader2 } from 'lucide-react'
import { api } from '@/lib/api'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'

interface ApiKeyStatus {
  has_api_key: boolean
  key_hint?: string
}

export function ApiKeyManager() {
  const queryClient = useQueryClient()
  const [apiKey, setApiKey] = useState('')
  const [showKey, setShowKey] = useState(false)

  const { data: keyStatus } = useQuery({
    queryKey: ['api-key-status'],
    queryFn: () => api.get<ApiKeyStatus>('/auth/api-key'),
  })

  const saveMutation = useMutation({
    mutationFn: (key: string) =>
      api.post<{ validated: boolean }>('/auth/api-key', { api_key: key }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['api-key-status'] })
      setApiKey('')
    },
  })

  const handleSave = () => {
    if (!apiKey.trim()) return
    saveMutation.mutate(apiKey.trim())
  }

  const validationIcon = () => {
    if (saveMutation.isPending) {
      return <Loader2 className="size-4 animate-spin text-muted-foreground" />
    }
    if (saveMutation.isSuccess && saveMutation.data?.validated) {
      return <CheckCircle2 className="size-4 text-green-500" />
    }
    if (saveMutation.isError) {
      return <XCircle className="size-4 text-destructive" />
    }
    return null
  }

  return (
    <div className="space-y-6">
      <div>
        <h3 className="text-base font-semibold text-foreground">Anthropic API Key</h3>
        <p className="text-sm text-muted-foreground mt-1">
          Provide your own API key for skill execution. Your key is encrypted at rest and never returned after storage.
        </p>
      </div>

      {keyStatus?.has_api_key && (
        <div className="flex items-center gap-2 rounded-lg border border-border bg-muted/50 px-3 py-2">
          <CheckCircle2 className="size-4 text-green-500 shrink-0" />
          <span className="text-sm text-foreground">
            Key configured: <code className="text-xs bg-muted px-1 py-0.5 rounded">{keyStatus.key_hint || 'sk-...XXXX'}</code>
          </span>
        </div>
      )}

      <div className="space-y-3">
        <div className="flex items-center gap-2">
          <div className="relative flex-1">
            <Input
              type={showKey ? 'text' : 'password'}
              placeholder={keyStatus?.has_api_key ? 'Enter new key to update...' : 'sk-ant-...'}
              value={apiKey}
              onChange={(e) => setApiKey(e.target.value)}
              className="pr-8"
            />
            <button
              type="button"
              onClick={() => setShowKey(!showKey)}
              className="absolute right-2 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground"
            >
              {showKey ? <EyeOff className="size-4" /> : <Eye className="size-4" />}
            </button>
          </div>
          {validationIcon()}
        </div>

        <div className="flex items-center gap-2">
          <Button
            onClick={handleSave}
            disabled={!apiKey.trim() || saveMutation.isPending}
          >
            {saveMutation.isPending ? (
              <>
                <Loader2 className="size-4 animate-spin" />
                Validating...
              </>
            ) : keyStatus?.has_api_key ? (
              'Update Key'
            ) : (
              'Save Key'
            )}
          </Button>
        </div>

        {saveMutation.isSuccess && saveMutation.data?.validated && (
          <p className="text-sm text-green-600">Key saved and validated successfully.</p>
        )}
        {saveMutation.isError && (
          <p className="text-sm text-destructive">
            Failed to save key. Please check that your key is valid.
          </p>
        )}
      </div>
    </div>
  )
}
