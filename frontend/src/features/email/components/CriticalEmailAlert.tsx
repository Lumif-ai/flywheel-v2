import { useEffect } from 'react'
import { toast } from 'sonner'
import { useNavigate } from 'react-router'
import { useEmailStore } from '../store/emailStore'
import type { Thread } from '../types/email'

interface CriticalEmailAlertProps {
  threads: Thread[]
}

/**
 * Renderless component that fires Sonner toast alerts for priority-5 (critical) email threads.
 *
 * Deduplication strategy:
 * - Sonner deduplicates by stable id within the current session (no re-fire while toast is visible)
 * - alertDismissedIds in Zustand tracks dismissed threads across refetches (no re-fire after dismiss)
 */
export function CriticalEmailAlert({ threads }: CriticalEmailAlertProps) {
  const navigate = useNavigate()
  const { alertDismissedIds, dismissAlert } = useEmailStore()

  useEffect(() => {
    const criticalThreads = threads.filter(
      (t) => t.max_priority === 5 && !alertDismissedIds.has(t.thread_id),
    )

    for (const thread of criticalThreads) {
      toast.warning(`Critical: ${thread.subject ?? thread.sender_email}`, {
        id: thread.thread_id, // Sonner deduplicates by id — prevents re-fire on same render
        duration: Infinity, // Persist until user explicitly dismisses
        onDismiss: () => dismissAlert(thread.thread_id),
        action: {
          label: 'View',
          onClick: () => navigate(`/email?thread=${thread.thread_id}`),
        },
      })
      // Mark as alerted immediately so the next useEffect pass (30s refetch) skips it.
      // Sonner's id deduplication covers the current render; this covers subsequent refetches.
      dismissAlert(thread.thread_id)
    }
  }, [threads, alertDismissedIds, dismissAlert, navigate])

  return null
}
