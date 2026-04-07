import { useState } from 'react'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { toast } from 'sonner'
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { updateAccount, updateRelationshipType, queryKeys } from '../api'
import type { RelationshipDetailItem } from '../types/relationships'

const STATUSES = ['prospect', 'customer', 'lost']
const RELATIONSHIP_TYPES = ['prospect', 'customer', 'advisor', 'investor']
const RELATIONSHIP_STATUSES = ['active', 'at_risk', 'churned']

interface EditAccountDialogProps {
  account: RelationshipDetailItem
  open: boolean
  onOpenChange: (open: boolean) => void
}

export function EditAccountDialog({ account, open, onOpenChange }: EditAccountDialogProps) {
  const queryClient = useQueryClient()
  const [name, setName] = useState(account.name)
  const [domain, setDomain] = useState(account.domain ?? '')
  const [status, setStatus] = useState(account.status ?? 'prospect')
  const [relStatus, setRelStatus] = useState(account.relationship_status ?? 'active')
  const [types, setTypes] = useState<string[]>(account.relationship_type)

  const accountMutation = useMutation({
    mutationFn: () =>
      updateAccount(account.id, {
        name: name !== account.name ? name : undefined,
        domain: domain || null,
        status,
        relationship_status: relStatus,
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.relationships.detail(account.id) })
      queryClient.invalidateQueries({ queryKey: queryKeys.relationships.all })
    },
  })

  const typeMutation = useMutation({
    mutationFn: () => updateRelationshipType(account.id, types),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.relationships.detail(account.id) })
      queryClient.invalidateQueries({ queryKey: queryKeys.relationships.all })
    },
  })

  function toggleType(t: string) {
    setTypes((prev) =>
      prev.includes(t) ? prev.filter((x) => x !== t) : [...prev, t],
    )
  }

  async function handleSave() {
    try {
      const promises: Promise<unknown>[] = []
      promises.push(accountMutation.mutateAsync())
      if (JSON.stringify(types.sort()) !== JSON.stringify([...account.relationship_type].sort())) {
        promises.push(typeMutation.mutateAsync())
      }
      await Promise.all(promises)
      toast.success('Account updated')
      onOpenChange(false)
    } catch {
      toast.error('Failed to update account')
    }
  }

  const saving = accountMutation.isPending || typeMutation.isPending

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-[480px]">
        <DialogHeader>
          <DialogTitle>Edit Account</DialogTitle>
        </DialogHeader>

        <div className="space-y-4 mt-2">
          {/* Name */}
          <div>
            <label className="text-xs font-medium text-muted-foreground">Name</label>
            <Input value={name} onChange={(e) => setName(e.target.value)} className="mt-1" />
          </div>

          {/* Domain */}
          <div>
            <label className="text-xs font-medium text-muted-foreground">Domain</label>
            <Input
              value={domain}
              onChange={(e) => setDomain(e.target.value)}
              placeholder="example.com"
              className="mt-1"
            />
          </div>

          {/* Status */}
          <div>
            <label className="text-xs font-medium text-muted-foreground">Status</label>
            <div className="flex gap-2 mt-1">
              {STATUSES.map((s) => (
                <button
                  key={s}
                  onClick={() => setStatus(s)}
                  className="px-3 py-1.5 rounded-full text-xs font-medium transition-all"
                  style={{
                    background: status === s ? 'rgba(233,77,53,0.15)' : 'rgba(107,114,128,0.08)',
                    color: status === s ? '#E94D35' : '#6b7280',
                    border: status === s ? '1px solid rgba(233,77,53,0.3)' : '1px solid transparent',
                  }}
                >
                  {s.charAt(0).toUpperCase() + s.slice(1)}
                </button>
              ))}
            </div>
          </div>

          {/* Relationship Status */}
          <div>
            <label className="text-xs font-medium text-muted-foreground">Relationship Status</label>
            <div className="flex gap-2 mt-1">
              {RELATIONSHIP_STATUSES.map((s) => (
                <button
                  key={s}
                  onClick={() => setRelStatus(s)}
                  className="px-3 py-1.5 rounded-full text-xs font-medium transition-all"
                  style={{
                    background: relStatus === s ? 'rgba(233,77,53,0.15)' : 'rgba(107,114,128,0.08)',
                    color: relStatus === s ? '#E94D35' : '#6b7280',
                    border: relStatus === s ? '1px solid rgba(233,77,53,0.3)' : '1px solid transparent',
                  }}
                >
                  {s.replace(/_/g, ' ')}
                </button>
              ))}
            </div>
          </div>

          {/* Relationship Types (multi-select) */}
          <div>
            <label className="text-xs font-medium text-muted-foreground">Relationship Types</label>
            <div className="flex gap-2 mt-1 flex-wrap">
              {RELATIONSHIP_TYPES.map((t) => (
                <button
                  key={t}
                  onClick={() => toggleType(t)}
                  className="px-3 py-1.5 rounded-full text-xs font-medium transition-all"
                  style={{
                    background: types.includes(t) ? 'rgba(233,77,53,0.15)' : 'rgba(107,114,128,0.08)',
                    color: types.includes(t) ? '#E94D35' : '#6b7280',
                    border: types.includes(t) ? '1px solid rgba(233,77,53,0.3)' : '1px solid transparent',
                  }}
                >
                  {t.charAt(0).toUpperCase() + t.slice(1)}
                </button>
              ))}
            </div>
            {types.length === 0 && (
              <p className="text-xs text-destructive mt-1">At least one type required</p>
            )}
          </div>
        </div>

        <div className="flex justify-end gap-2 mt-4">
          <Button variant="outline" onClick={() => onOpenChange(false)}>
            Cancel
          </Button>
          <Button onClick={handleSave} disabled={saving || types.length === 0 || !name.trim()}>
            {saving ? 'Saving...' : 'Save'}
          </Button>
        </div>
      </DialogContent>
    </Dialog>
  )
}
