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
import { updateContact, createContact, queryKeys } from '../api'
import type { ContactItem } from '../types/relationships'

interface EditContactDialogProps {
  accountId: string
  contact: ContactItem | null // null = creating new
  open: boolean
  onOpenChange: (open: boolean) => void
}

export function EditContactDialog({ accountId, contact, open, onOpenChange }: EditContactDialogProps) {
  const queryClient = useQueryClient()
  const isNew = contact === null

  const [name, setName] = useState(contact?.name ?? '')
  const [email, setEmail] = useState(contact?.email ?? '')
  const [title, setTitle] = useState(contact?.title ?? '')
  const [role, setRole] = useState(contact?.role ?? '')
  const [linkedin, setLinkedin] = useState(contact?.linkedin_url ?? '')

  const mutation = useMutation({
    mutationFn: () => {
      const payload = {
        name: name.trim(),
        email: email.trim() || null,
        title: title.trim() || null,
        role: role.trim() || null,
        linkedin_url: linkedin.trim() || null,
      }
      if (isNew) {
        return createContact(accountId, payload)
      }
      return updateContact(accountId, contact!.id, payload)
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.relationships.detail(accountId) })
      toast.success(isNew ? 'Contact added' : 'Contact updated')
      onOpenChange(false)
    },
    onError: () => {
      toast.error(isNew ? 'Failed to add contact' : 'Failed to update contact')
    },
  })

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-[440px]">
        <DialogHeader>
          <DialogTitle>{isNew ? 'Add Contact' : 'Edit Contact'}</DialogTitle>
        </DialogHeader>

        <div className="space-y-3 mt-2">
          <div>
            <label className="text-xs font-medium text-muted-foreground">Name *</label>
            <Input value={name} onChange={(e) => setName(e.target.value)} className="mt-1" />
          </div>
          <div>
            <label className="text-xs font-medium text-muted-foreground">Title</label>
            <Input value={title} onChange={(e) => setTitle(e.target.value)} className="mt-1" placeholder="e.g. VP Engineering" />
          </div>
          <div>
            <label className="text-xs font-medium text-muted-foreground">Email</label>
            <Input value={email} onChange={(e) => setEmail(e.target.value)} className="mt-1" type="email" placeholder="name@company.com" />
          </div>
          <div>
            <label className="text-xs font-medium text-muted-foreground">Role</label>
            <Input value={role} onChange={(e) => setRole(e.target.value)} className="mt-1" placeholder="e.g. decision-maker, champion" />
          </div>
          <div>
            <label className="text-xs font-medium text-muted-foreground">LinkedIn URL</label>
            <Input value={linkedin} onChange={(e) => setLinkedin(e.target.value)} className="mt-1" placeholder="https://linkedin.com/in/..." />
          </div>
        </div>

        <div className="flex justify-end gap-2 mt-4">
          <Button variant="outline" onClick={() => onOpenChange(false)}>Cancel</Button>
          <Button onClick={() => mutation.mutate()} disabled={mutation.isPending || !name.trim()}>
            {mutation.isPending ? 'Saving...' : isNew ? 'Add' : 'Save'}
          </Button>
        </div>
      </DialogContent>
    </Dialog>
  )
}
