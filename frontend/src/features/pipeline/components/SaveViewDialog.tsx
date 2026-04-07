import { useState } from 'react'
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
  DialogFooter,
} from '@/components/ui/dialog'
import { Button } from '@/components/ui/button'
import { useCreateSavedView } from '../hooks/useSavedViews'
import type { SavedView } from '../types/pipeline'

export interface SaveViewDialogProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  filters: SavedView['filters']
  sort?: SavedView['sort']
}

function formatFilterSummary(filters: SavedView['filters']): string {
  const parts: string[] = []
  if (filters.stage?.length) parts.push(`Stage: ${filters.stage.join(', ')}`)
  if (filters.fitTier?.length) parts.push(`Fit: ${filters.fitTier.join(', ')}`)
  if (filters.relationshipType?.length) parts.push(`Type: ${filters.relationshipType.join(', ')}`)
  if (filters.source) parts.push(`Source: ${filters.source}`)
  if (filters.view && filters.view !== 'all') parts.push(`View: ${filters.view}`)
  if (filters.search) parts.push(`Search: "${filters.search}"`)
  return parts.length > 0 ? parts.join(' | ') : 'No filters'
}

export function SaveViewDialog({ open, onOpenChange, filters, sort }: SaveViewDialogProps) {
  const [name, setName] = useState('')
  const createMutation = useCreateSavedView()

  const handleSave = () => {
    if (!name.trim()) return
    createMutation.mutate(
      { name: name.trim(), filters, sort },
      {
        onSuccess: () => {
          setName('')
          onOpenChange(false)
        },
      },
    )
  }

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && name.trim()) {
      e.preventDefault()
      handleSave()
    }
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Save View</DialogTitle>
          <DialogDescription>
            Save the current filters as a named view for quick access from the sidebar.
          </DialogDescription>
        </DialogHeader>

        <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
          <div>
            <label
              htmlFor="view-name"
              style={{ fontSize: '13px', fontWeight: 500, color: '#121212', display: 'block', marginBottom: '4px' }}
            >
              View name
            </label>
            <input
              id="view-name"
              type="text"
              value={name}
              onChange={(e) => setName(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder="e.g. Hot Leads, Enterprise Customers"
              autoFocus
              style={{
                width: '100%',
                height: '36px',
                border: '1px solid #E5E7EB',
                borderRadius: '8px',
                padding: '6px 12px',
                fontSize: '13px',
                color: '#121212',
                background: '#FFFFFF',
                outline: 'none',
              }}
            />
          </div>

          <div
            style={{
              fontSize: '12px',
              color: '#9CA3AF',
              padding: '8px 10px',
              background: '#FAFAFA',
              borderRadius: '6px',
              lineHeight: 1.5,
            }}
          >
            {formatFilterSummary(filters)}
          </div>
        </div>

        <DialogFooter>
          <Button
            variant="outline"
            size="sm"
            onClick={() => onOpenChange(false)}
          >
            Cancel
          </Button>
          <Button
            size="sm"
            onClick={handleSave}
            disabled={!name.trim() || createMutation.isPending}
          >
            {createMutation.isPending ? 'Saving...' : 'Save'}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
