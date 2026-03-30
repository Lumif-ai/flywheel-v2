import { useState } from 'react'
import {
  RefreshCw,
  ArrowDown,
  ArrowUp,
  Smile,
  Briefcase,
  Pencil,
  Loader2,
} from 'lucide-react'
import {
  DropdownMenu,
  DropdownMenuTrigger,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
} from '@/components/ui/dropdown-menu'
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
} from '@/components/ui/dialog'
import { Button } from '@/components/ui/button'
import { colors } from '@/lib/design-tokens'
import type { RegenerateRequest } from '../types/email'

interface RegenerateDropdownProps {
  draftId: string
  hasUserEdits: boolean
  isRegenerating: boolean
  onRegenerate: (req: RegenerateRequest) => void
}

const QUICK_ACTIONS: { action: RegenerateRequest['action']; label: string; icon: typeof ArrowDown }[] = [
  { action: 'shorter', label: 'Shorter', icon: ArrowDown },
  { action: 'longer', label: 'Longer', icon: ArrowUp },
  { action: 'more_casual', label: 'More casual', icon: Smile },
  { action: 'more_formal', label: 'More formal', icon: Briefcase },
]

export function RegenerateDropdown({
  hasUserEdits,
  isRegenerating,
  onRegenerate,
}: RegenerateDropdownProps) {
  const [customOpen, setCustomOpen] = useState(false)
  const [customText, setCustomText] = useState('')
  const [confirmRequest, setConfirmRequest] = useState<RegenerateRequest | null>(null)

  function handleAction(request: RegenerateRequest) {
    if (hasUserEdits) {
      setConfirmRequest(request)
    } else {
      onRegenerate(request)
    }
  }

  function handleConfirm() {
    if (confirmRequest) {
      onRegenerate(confirmRequest)
      setConfirmRequest(null)
    }
  }

  function handleCustomSubmit() {
    if (!customText.trim()) return
    const request: RegenerateRequest = { custom_instructions: customText.trim() }
    setCustomOpen(false)
    setCustomText('')
    handleAction(request)
  }

  return (
    <>
      <DropdownMenu>
        <DropdownMenuTrigger
          disabled={isRegenerating}
          className="flex items-center gap-1.5 rounded-xl border px-3 py-2 text-sm font-medium transition-colors hover:bg-[rgba(0,0,0,0.04)] disabled:opacity-50"
          style={{ borderColor: 'var(--subtle-border)', color: colors.headingText }}
        >
          {isRegenerating ? (
            <Loader2 className="size-3.5 animate-spin" />
          ) : (
            <RefreshCw className="size-3.5" />
          )}
          Regenerate
        </DropdownMenuTrigger>

        <DropdownMenuContent align="start" sideOffset={4}>
          {QUICK_ACTIONS.map(({ action, label, icon: Icon }) => (
            <DropdownMenuItem
              key={action}
              onClick={() => handleAction({ action })}
            >
              <Icon className="size-3.5" />
              {label}
            </DropdownMenuItem>
          ))}
          <DropdownMenuSeparator />
          <DropdownMenuItem onClick={() => setCustomOpen(true)}>
            <Pencil className="size-3.5" />
            Custom...
          </DropdownMenuItem>
        </DropdownMenuContent>
      </DropdownMenu>

      {/* Custom instructions inline input */}
      {customOpen && (
        <div
          className="flex items-center gap-2 rounded-lg border p-2 mt-2"
          style={{ borderColor: 'var(--subtle-border)', backgroundColor: 'rgba(0,0,0,0.02)' }}
        >
          <input
            type="text"
            value={customText}
            onChange={(e) => setCustomText(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && handleCustomSubmit()}
            placeholder="e.g., be more empathetic, add a question about timeline..."
            className="flex-1 bg-transparent text-sm outline-none"
            style={{ color: colors.bodyText }}
            autoFocus
          />
          <button
            onClick={handleCustomSubmit}
            disabled={!customText.trim()}
            className="shrink-0 rounded-lg px-3 py-1 text-xs font-medium text-white transition-opacity hover:opacity-90 disabled:opacity-50"
            style={{ background: 'var(--brand-coral)' }}
          >
            Regenerate
          </button>
          <button
            onClick={() => { setCustomOpen(false); setCustomText('') }}
            className="shrink-0 text-xs font-medium transition-opacity hover:opacity-70"
            style={{ color: colors.secondaryText }}
          >
            Cancel
          </button>
        </div>
      )}

      {/* Confirmation dialog for drafts with user edits */}
      <Dialog open={!!confirmRequest} onOpenChange={(open) => !open && setConfirmRequest(null)}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Replace your edits?</DialogTitle>
            <DialogDescription>
              You have edits that will be replaced by the regenerated draft. This cannot be undone.
            </DialogDescription>
          </DialogHeader>
          <div className="flex justify-end gap-2 pt-4">
            <Button variant="outline" onClick={() => setConfirmRequest(null)}>
              Cancel
            </Button>
            <Button onClick={handleConfirm} style={{ background: 'var(--brand-coral)' }}>
              Continue
            </Button>
          </div>
        </DialogContent>
      </Dialog>
    </>
  )
}
