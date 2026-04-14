import { useState } from 'react'
import { Plus, Edit2, Trash2 } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogFooter,
} from '@/components/ui/dialog'
import { useCarrierContacts } from '../hooks/useCarrierContacts'
import {
  useCreateCarrierContact,
  useUpdateCarrierContact,
  useDeleteCarrierContact,
} from '../hooks/useCarrierContactMutations'
import type { CarrierContact, CreateCarrierContactPayload, UpdateContactPayload } from '../types/broker'

const CARRIER_CONTACT_ROLES = [
  'submissions',
  'account_manager',
  'underwriter',
  'claims',
  'billing',
]

interface ContactDialogState {
  open: boolean
  mode: 'add' | 'edit'
  contact: CarrierContact | null
}

const EMPTY_CONTACT: CreateCarrierContactPayload = {
  name: '',
  email: '',
  phone: '',
  role: 'submissions',
  is_primary: false,
}

interface CarrierContactsDialogProps {
  carrierId: string
  carrierName: string
  open: boolean
  onClose: () => void
}

export function CarrierContactsDialog({
  carrierId,
  carrierName,
  open,
  onClose,
}: CarrierContactsDialogProps) {
  const { data: contactsData } = useCarrierContacts(carrierId)
  const contacts = contactsData?.items ?? []
  const atLimit = contacts.length >= 10

  const createContact = useCreateCarrierContact(carrierId)
  const updateContact = useUpdateCarrierContact(carrierId)
  const deleteContact = useDeleteCarrierContact(carrierId)

  const [innerDialog, setInnerDialog] = useState<ContactDialogState>({
    open: false,
    mode: 'add',
    contact: null,
  })
  const [contactForm, setContactForm] = useState<CreateCarrierContactPayload>(EMPTY_CONTACT)

  function openAdd() {
    setContactForm(EMPTY_CONTACT)
    setInnerDialog({ open: true, mode: 'add', contact: null })
  }

  function openEdit(contact: CarrierContact) {
    setContactForm({
      name: contact.name,
      email: contact.email ?? '',
      phone: contact.phone ?? '',
      role: contact.role,
      is_primary: contact.is_primary,
    })
    setInnerDialog({ open: true, mode: 'edit', contact })
  }

  function closeInner() {
    setInnerDialog((d) => ({ ...d, open: false }))
  }

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    if (!contactForm.name?.trim()) return

    const payload = {
      name: contactForm.name?.trim() ?? '',
      email: contactForm.email?.trim() || null,
      phone: contactForm.phone?.trim() || null,
      role: contactForm.role ?? 'submissions',
      is_primary: contactForm.is_primary ?? false,
    }

    if (innerDialog.mode === 'add') {
      createContact.mutate(payload, { onSuccess: closeInner })
    } else if (innerDialog.contact) {
      const updatePayload: UpdateContactPayload = payload
      updateContact.mutate(
        { contactId: innerDialog.contact.id, payload: updatePayload },
        { onSuccess: closeInner }
      )
    }
  }

  function handleDelete(contactId: string) {
    if (window.confirm('Delete this contact?')) {
      deleteContact.mutate(contactId)
    }
  }

  return (
    <>
      {/* Main carrier contacts dialog */}
      <Dialog open={open} onOpenChange={(val) => !val && onClose()}>
        <DialogContent className="sm:max-w-2xl max-h-[90vh] overflow-y-auto">
          <DialogHeader>
            <DialogTitle>Contacts — {carrierName}</DialogTitle>
          </DialogHeader>

          <div className="space-y-4">
            {/* Header row */}
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-3">
                <span className="text-sm text-muted-foreground">{contacts.length} / 10</span>
                {atLimit && (
                  <span className="inline-flex items-center rounded-full bg-amber-100 px-2 py-0.5 text-xs font-medium text-amber-700">
                    Limit reached
                  </span>
                )}
              </div>
              <div title={atLimit ? 'Maximum 10 contacts reached' : undefined}>
                <Button size="sm" onClick={openAdd} disabled={atLimit}>
                  <Plus className="h-3.5 w-3.5 mr-1" />
                  Add Contact
                </Button>
              </div>
            </div>

            {/* Contacts table */}
            {contacts.length === 0 ? (
              <p className="text-sm text-muted-foreground text-center py-8">
                No contacts yet. Click Add Contact to get started.
              </p>
            ) : (
              <div className="overflow-x-auto rounded-md border">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="border-b bg-muted/30">
                      <th className="text-left px-4 py-2.5 font-medium text-muted-foreground">Name</th>
                      <th className="text-left px-4 py-2.5 font-medium text-muted-foreground">Email</th>
                      <th className="text-left px-4 py-2.5 font-medium text-muted-foreground">Phone</th>
                      <th className="text-left px-4 py-2.5 font-medium text-muted-foreground">Role</th>
                      <th className="text-left px-4 py-2.5 font-medium text-muted-foreground">Primary</th>
                      <th className="w-20 px-4 py-2.5" />
                    </tr>
                  </thead>
                  <tbody>
                    {contacts.map((contact) => (
                      <tr key={contact.id} className="border-b last:border-0 hover:bg-muted/20">
                        <td className="px-4 py-2.5 font-medium">{contact.name}</td>
                        <td className="px-4 py-2.5 text-muted-foreground">{contact.email ?? '—'}</td>
                        <td className="px-4 py-2.5 text-muted-foreground">{contact.phone ?? '—'}</td>
                        <td className="px-4 py-2.5 text-muted-foreground capitalize">
                          {contact.role.replace(/_/g, ' ')}
                        </td>
                        <td className="px-4 py-2.5">
                          {contact.is_primary && (
                            <span className="inline-flex items-center rounded-full bg-blue-100 px-2 py-0.5 text-xs font-medium text-blue-700">
                              Primary
                            </span>
                          )}
                        </td>
                        <td className="px-4 py-2.5">
                          <div className="flex items-center gap-1">
                            <Button
                              variant="ghost"
                              size="icon"
                              className="h-7 w-7"
                              onClick={() => openEdit(contact)}
                            >
                              <Edit2 className="h-3.5 w-3.5" />
                            </Button>
                            <Button
                              variant="ghost"
                              size="icon"
                              className="h-7 w-7 text-red-500 hover:text-red-600"
                              onClick={() => handleDelete(contact.id)}
                            >
                              <Trash2 className="h-3.5 w-3.5" />
                            </Button>
                          </div>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>

          <DialogFooter>
            <Button variant="outline" onClick={onClose}>
              Close
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Add / Edit contact inner dialog */}
      <Dialog open={innerDialog.open} onOpenChange={(val) => !val && closeInner()}>
        <DialogContent className="sm:max-w-md">
          <DialogHeader>
            <DialogTitle>
              {innerDialog.mode === 'add' ? 'Add Contact' : 'Edit Contact'}
            </DialogTitle>
          </DialogHeader>
          <form onSubmit={handleSubmit} className="space-y-4">
            <div className="space-y-2">
              <label className="text-sm font-medium">
                Name <span className="text-red-500">*</span>
              </label>
              <Input
                value={contactForm.name ?? ''}
                onChange={(e) => setContactForm((f) => ({ ...f, name: e.target.value }))}
                placeholder="Contact name"
                required
              />
            </div>
            <div className="space-y-2">
              <label className="text-sm font-medium">Email</label>
              <Input
                type="email"
                value={contactForm.email ?? ''}
                onChange={(e) => setContactForm((f) => ({ ...f, email: e.target.value }))}
                placeholder="name@carrier.com"
              />
            </div>
            <div className="space-y-2">
              <label className="text-sm font-medium">Phone</label>
              <Input
                value={contactForm.phone ?? ''}
                onChange={(e) => setContactForm((f) => ({ ...f, phone: e.target.value }))}
                placeholder="+1 (555) 000-0000"
              />
            </div>
            <div className="space-y-2">
              <label className="text-sm font-medium">Role</label>
              <select
                value={contactForm.role ?? 'submissions'}
                onChange={(e) => setContactForm((f) => ({ ...f, role: e.target.value }))}
                className="flex h-9 w-full rounded-md border border-input bg-transparent px-3 py-1 text-sm shadow-sm focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring"
              >
                {CARRIER_CONTACT_ROLES.map((r) => (
                  <option key={r} value={r}>
                    {r.replace(/_/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase())}
                  </option>
                ))}
              </select>
            </div>
            <div className="flex items-center gap-2">
              <input
                type="checkbox"
                id="carrier-contact-primary"
                checked={contactForm.is_primary ?? false}
                onChange={(e) => setContactForm((f) => ({ ...f, is_primary: e.target.checked }))}
                className="h-4 w-4 rounded border-input"
              />
              <label htmlFor="carrier-contact-primary" className="text-sm font-medium">
                Primary contact
              </label>
            </div>
            <DialogFooter>
              <Button type="button" variant="outline" onClick={closeInner}>
                Cancel
              </Button>
              <Button
                type="submit"
                disabled={
                  !contactForm.name?.trim() ||
                  createContact.isPending ||
                  updateContact.isPending
                }
              >
                {createContact.isPending || updateContact.isPending
                  ? 'Saving...'
                  : innerDialog.mode === 'add'
                  ? 'Add Contact'
                  : 'Save Changes'}
              </Button>
            </DialogFooter>
          </form>
        </DialogContent>
      </Dialog>
    </>
  )
}
