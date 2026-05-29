import { useState, useCallback, useRef } from 'react'
import { toast } from 'sonner'
import { api, apiUrl } from '@/lib/api'
import { useSSE } from '@/lib/sse'

interface SkillRunResponse {
  run_id: string
  status: string
  stream_url: string
}

interface SkillResult {
  run_id: string
  status: string
  rendered_html?: string
  tokens_used?: number
  cost_estimate?: number | null
}

export function useSkillExecution() {
  const [isExecuting, setIsExecuting] = useState(false)
  const [result, setResult] = useState<SkillResult | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [streamUrl, setStreamUrl] = useState<string | null>(null)
  const runIdRef = useRef<string | null>(null)

  // SSE handler for real-time updates
  useSSE(streamUrl, (event) => {
    if (event.type === 'done') {
      const data = event.data as Record<string, unknown>
      const status = data.status as string
      if (status === 'completed') {
        setResult({
          run_id: runIdRef.current ?? '',
          status: 'completed',
          rendered_html: data.rendered_html as string | undefined,
          tokens_used: data.tokens_used as number | undefined,
          cost_estimate: data.cost_estimate as number | null | undefined,
        })
        toast.success('Deliverable generated')
      } else {
        setError('Skill execution failed')
        toast.error('Skill execution failed')
      }
      setIsExecuting(false)
      setStreamUrl(null)
    } else if (event.type === 'error') {
      const msg = (event.data.message as string) || 'Skill execution failed'
      setError(msg)
      toast.error(msg)
      setIsExecuting(false)
      setStreamUrl(null)
    }
  })

  const execute = useCallback(
    async (skillName: string, skillContext: Record<string, unknown>) => {
      setIsExecuting(true)
      setResult(null)
      setError(null)
      setStreamUrl(null)

      try {
        const response = await api.post<SkillRunResponse>('/skills/runs', {
          skill_name: skillName,
          input_text: JSON.stringify(skillContext),
        })

        runIdRef.current = response.run_id

        // Connect to SSE stream for real-time updates
        setStreamUrl(apiUrl(`/api/v1/skills/runs/${response.run_id}/stream`))
      } catch (err) {
        const msg =
          err instanceof Error ? err.message : 'Failed to start skill execution'
        setError(msg)
        toast.error(msg)
        setIsExecuting(false)
      }
    },
    [],
  )

  const reset = useCallback(() => {
    setResult(null)
    setError(null)
  }, [])

  return { execute, isExecuting, result, error, reset }
}
