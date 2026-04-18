import { useEffect, useRef, useState } from 'react'
import { toast } from 'sonner'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import { Button } from '@/components/ui/button'

interface ClaudeCommandModalProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  /**
   * The fully-formed slash command to paste into Claude Code, e.g.
   * `/broker:parse-contract 9a2f...`.
   */
  command: string
  /**
   * Skill name shown in the title (e.g. "broker-parse-contract").
   * Optional — when omitted, title falls back to a generic "Run in Claude Code".
   */
  skillName?: string
  /**
   * Optional short label appearing above the command (e.g. "Analyze Contract").
   * Purely for the human; unused by the copy logic.
   */
  actionLabel?: string
}

/**
 * Modal shown when a broker web-UI button is clicked for an action that is
 * implemented as a `web_tier=3` broker-* skill (Phase 150.1 Plan 03 / Blocker-3
 * branch P3). The backend /broker/extract/* endpoint has already been warmed at
 * this point (proving BYOK + X-Flywheel-Skill enforcement); this modal hands
 * the user the exact slash command to run in their local Claude Code session so
 * the Pattern 3a analysis can execute there.
 *
 * Brand tokens: lumif.ai primary accent #E94D35, rounded-xl (12px), Inter.
 */
export function ClaudeCommandModal({
  open,
  onOpenChange,
  command,
  skillName,
  actionLabel,
}: ClaudeCommandModalProps) {
  const [copied, setCopied] = useState(false)
  const textareaRef = useRef<HTMLTextAreaElement | null>(null)

  // Reset the copied indicator whenever the modal is reopened or the command
  // changes so stale "Copied!" state never leaks across invocations.
  useEffect(() => {
    if (!open) setCopied(false)
  }, [open, command])

  async function handleCopy() {
    // Primary path: async clipboard API (available over HTTPS / localhost).
    if (typeof navigator !== 'undefined' && navigator.clipboard?.writeText) {
      try {
        await navigator.clipboard.writeText(command)
        setCopied(true)
        toast.success('Copied! Paste into Claude Code')
        window.setTimeout(() => setCopied(false), 2000)
        return
      } catch {
        // Fall through to the execCommand fallback below.
      }
    }

    // Fallback path: select the textarea and invoke execCommand('copy').
    // Used when the page is served over plain http (some internal tooling) or
    // when the browser blocks the clipboard API for any other reason.
    const el = textareaRef.current
    if (el) {
      el.focus()
      el.select()
      try {
        const ok = document.execCommand('copy')
        if (ok) {
          setCopied(true)
          toast.success('Copied! Paste into Claude Code')
          window.setTimeout(() => setCopied(false), 2000)
          return
        }
      } catch {
        // fall through to explicit failure toast
      }
    }

    toast.error('Could not copy automatically — select the command and press Cmd/Ctrl+C')
  }

  const title = skillName ? `Run ${skillName} in Claude Code` : 'Run in Claude Code'

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle>{title}</DialogTitle>
          <DialogDescription>
            This step runs in Claude Code. Copy the command below and paste it into your local
            Claude Code session — Claude will pick up from here and complete the work.
          </DialogDescription>
        </DialogHeader>

        {actionLabel && (
          <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
            {actionLabel}
          </p>
        )}

        {/* Command block — monospace, selectable, acts as the execCommand fallback target */}
        <div className="rounded-xl border border-foreground/10 bg-muted/40 p-3">
          <textarea
            ref={textareaRef}
            readOnly
            value={command}
            rows={1}
            className="w-full resize-none bg-transparent font-mono text-sm text-foreground outline-none"
            onFocus={(e) => e.currentTarget.select()}
            onClick={(e) => (e.currentTarget as HTMLTextAreaElement).select()}
            aria-label="Claude Code command to copy"
          />
        </div>

        <DialogFooter>
          <Button variant="outline" onClick={() => onOpenChange(false)}>
            Close
          </Button>
          <Button
            onClick={handleCopy}
            className="bg-[#E94D35] text-white hover:bg-[#D4442F]"
          >
            {copied ? 'Copied!' : 'Copy command'}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
