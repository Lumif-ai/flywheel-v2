import { useMutation, useQueryClient } from '@tanstack/react-query'
import { triggerAnalysis } from '../api'

/**
 * Phase 150.1 Plan 03 (Blocker-3 branch P3):
 * `triggerAnalysis` warms the new /broker/extract/contract-analysis endpoint
 * (proving BYOK + X-Flywheel-Skill enforcement live) but cannot complete the
 * full Pattern 3a flow server-side — broker-* skills are web_tier=3 and must
 * run in the user's local Claude Code. `onHandoff` fires on success so the
 * caller can open the ClaudeCommandModal with the pre-filled slash command.
 */
export function useAnalyzeProject(
  projectId: string,
  opts?: { onHandoff?: (command: string) => void },
) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: () => triggerAnalysis(projectId),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['broker-project', projectId] })
      qc.invalidateQueries({ queryKey: ['broker-dashboard-stats'] })
      opts?.onHandoff?.(`/broker:parse-contract ${projectId}`)
    },
  })
}
