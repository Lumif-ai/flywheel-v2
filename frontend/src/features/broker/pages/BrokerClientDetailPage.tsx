import { useState } from 'react'
import { useParams, useNavigate } from 'react-router'
import { useQuery } from '@tanstack/react-query'
import {
  ArrowLeft,
  Plus,
  Edit2,
  Trash2,
  Building2,
  MapPin,
  Globe,
  Briefcase,
  FileText,
  Loader2,
} from 'lucide-react'
import { Button } from '@/components/ui/button'
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogFooter,
} from '@/components/ui/dialog'
import { Input } from '@/components/ui/input'
import { fetchClient } from '../api'
import { useClientContacts } from '../hooks/useClientContacts'
import {
  useCreateClientContact,
  useUpdateClientContact,
  useDeleteClientContact,
} from '../hooks/useClientContactMutations'
import { useBrokerProjects } from '../hooks/useBrokerProjects'
import type { BrokerClient, BrokerClientContact, CreateClientContactPayload, UpdateContactPayload } from '../types/broker'

const CONTACT_ROLES = [
  'primary',
  'billing',
  'technical',
  'legal',
  'executive',
  'other',
]

const STATUS_COLORS: Record<string, { bg: string; text: string }> = {
  new_request:     { bg: '#EFF6FF', text: '#1D4ED8' },
  analyzing:       { bg: '#FEF9C3', text: '#A16207' },
  gaps_identified: { bg: '#FEF9C3', text: '#A16207' },
  soliciting:      { bg: '#F0FDF4', text: '#15803D' },
  quotes_partial:  { bg: '#F0FDF4', text: '#15803D' },
  quotes_complete: { bg: '#F0FDF4', text: '#166534' },
  recommended:     { bg: '#F0FDF4', text: '#166534' },
  delivered:       { bg: '#DCFCE7', text: '#15803D' },
  bound:           { bg: '#D1FAE5', text: '#064E3B' },
  cancelled:       { bg: '#F3F4F6', text: '#9CA3AF' },
}

function StatusBadge({ status }: { status: string }) {
  const colors = STATUS_COLORS[status] ?? { bg: '#F3F4F6', text: '#6B7280' }
  return (
    <span
      className="inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium capitalize"
      style={{ backgroundColor: colors.bg, color: colors.text }}
    >
      {status.replace(/_/g, ' ')}
    </span>
  )
}

interface ContactDialogState {
  open: boolean
  mode: 'add' | 'edit'
  contact: BrokerClientContact | null
}

const EMPTY_CONTACT: CreateClientContactPayload = {
  name: '',
  email: '',
  phone: '',
  role: '',
  is_primary: false,
}

function ProfileCard({ client }: { client: BrokerClient }) {
  const fields = [
    { label: 'Industry', value: client.industry, icon: Briefcase },
    { label: 'Location', value: client.location, icon: MapPin },
    { label: 'Domain', value: client.domain, icon: Globe },
    { label: 'Legal Name', value: client.legal_name, icon: Building2 },
  ].filter((f) => f.value)

  return (
    <div className="rounded-xl border bg-white shadow-sm p-6">
      <div className="flex items-start justify-between">
        <div>
          <h2 className="text-2xl font-semibold">{client.name}</h2>
          {client.legal_name && client.legal_name !== client.name && (
            <p className="text-sm text-muted-foreground mt-0.5">{client.legal_name}</p>
          )}
        </div>
        <span className="text-xs text-muted-foreground mt-1">
          Added {new Date(client.created_at).toLocaleDateString()}
        </span>
      </div>

      {fields.length > 0 && (
        <div className="mt-4 grid grid-cols-2 gap-4">
          {fields.map(({ label, value, icon: Icon }) => (
            <div key={label} className="flex items-start gap-2">
              <Icon className="h-4 w-4 text-muted-foreground mt-0.5 flex-shrink-0" />
              <div>
                <p className="text-xs text-muted-foreground">{label}</p>
                <p className="text-sm font-medium">{value}</p>
              </div>
            </div>
          ))}
        </div>
      )}

      {client.notes && (
        <div className="mt-4 flex items-start gap-2">
          <FileText className="h-4 w-4 text-muted-foreground mt-0.5 flex-shrink-0" />
          <div>
            <p className="text-xs text-muted-foreground">Notes</p>
            <p className="text-sm">{client.notes}</p>
          </div>
        </div>
      )}
    </div>
  )
}

export function BrokerClientDetailPage() {
  const { id } = useParams<{ id: string }>()
  const navigate = useNavigate()

  // Fetch client
  const { data: client, isLoading: clientLoading } = useQuery({
    queryKey: ['broker-client', id],
    queryFn: () => fetchClient(id!),
    enabled: !!id,
  })

  // Fetch contacts
  const { data: contactsData } = useClientContacts(id ?? '')
  const contacts = contactsData?.items ?? []
  const atLimit = contacts.length >= 20

  // Contact mutations
  const createContact = useCreateClientContact(id ?? '')
  const updateContact = useUpdateClientContact(id ?? '')
  const deleteContact = useDeleteClientContact(id ?? '')

  // Fetch projects filtered by client_id
  const { data: projectsData } = useBrokerProjects({ client_id: id })
  const projects = projectsData?.items ?? []

  // Contact dialog state
  const [dialog, setDialog] = useState<ContactDialogState>({
    open: false,
    mode: 'add',
    contact: null,
  })
  const [contactForm, setContactForm] = useState<CreateClientContactPayload>(EMPTY_CONTACT)

  function openAddContact() {
    setContactForm(EMPTY_CONTACT)
    setDialog({ open: true, mode: 'add', contact: null })
  }

  function openEditContact(contact: BrokerClientContact) {
    setContactForm({
      name: contact.name,
      email: contact.email ?? '',
      phone: contact.phone ?? '',
      role: contact.role ?? '',
      is_primary: contact.is_primary,
    })
    setDialog({ open: true, mode: 'edit', contact })
  }

  function closeDialog() {
    setDialog((d) => ({ ...d, open: false }))
  }

  function handleContactSubmit(e: React.FormEvent) {
    e.preventDefault()
    if (!contactForm.name?.trim()) return

    const payload = {
      name: contactForm.name.trim(),
      email: contactForm.email?.trim() || null,
      phone: contactForm.phone?.trim() || null,
      role: contactForm.role?.trim() || null,
      is_primary: contactForm.is_primary ?? false,
    }

    if (dialog.mode === 'add') {
      createContact.mutate(payload, { onSuccess: closeDialog })
    } else if (dialog.contact) {
      const updatePayload: UpdateContactPayload = payload
      updateContact.mutate(
        { contactId: dialog.contact.id, payload: updatePayload },
        { onSuccess: closeDialog }
      )
    }
  }

  function handleDeleteContact(contactId: string) {
    if (window.confirm('Delete this contact?')) {
      deleteContact.mutate(contactId)
    }
  }

  if (clientLoading) {
    return (
      <div className="p-6 flex items-center justify-center h-64">
        <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
      </div>
    )
  }

  if (!client) {
    return (
      <div className="p-6">
        <p className="text-muted-foreground">Client not found.</p>
      </div>
    )
  }

  return (
    <div className="p-6 space-y-6 max-w-4xl">
      {/* Back navigation */}
      <Button variant="ghost" onClick={() => navigate('/broker/clients')} className="-ml-2">
        <ArrowLeft className="h-4 w-4 mr-1.5" />
        Clients
      </Button>

      {/* Profile card */}
      <ProfileCard client={client} />

      {/* Contacts section */}
      <div className="rounded-xl border bg-white shadow-sm">
        <div className="flex items-center justify-between px-6 py-4 border-b">
          <div className="flex items-center gap-3">
            <h3 className="text-base font-semibold">Contacts</h3>
            <span className="text-xs text-muted-foreground">{contacts.length} / 20</span>
            {atLimit && (
              <span className="inline-flex items-center rounded-full bg-amber-100 px-2 py-0.5 text-xs font-medium text-amber-700">
                Limit reached
              </span>
            )}
          </div>
          <div title={atLimit ? 'Maximum 20 contacts reached' : undefined}>
            <Button
              size="sm"
              onClick={openAddContact}
              disabled={atLimit}
            >
              <Plus className="h-3.5 w-3.5 mr-1" />
              Add Contact
            </Button>
          </div>
        </div>

        {contacts.length === 0 ? (
          <p className="px-6 py-8 text-sm text-muted-foreground text-center">
            No contacts yet. Click Add Contact to get started.
          </p>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b bg-muted/30">
                  <th className="text-left px-6 py-3 font-medium text-muted-foreground">Name</th>
                  <th className="text-left px-4 py-3 font-medium text-muted-foreground">Email</th>
                  <th className="text-left px-4 py-3 font-medium text-muted-foreground">Phone</th>
                  <th className="text-left px-4 py-3 font-medium text-muted-foreground">Role</th>
                  <th className="text-left px-4 py-3 font-medium text-muted-foreground">Primary</th>
                  <th className="w-20 px-4 py-3" />
                </tr>
              </thead>
              <tbody>
                {contacts.map((contact) => (
                  <tr key={contact.id} className="border-b last:border-0 hover:bg-muted/20">
                    <td className="px-6 py-3 font-medium">{contact.name}</td>
                    <td className="px-4 py-3 text-muted-foreground">{contact.email ?? '—'}</td>
                    <td className="px-4 py-3 text-muted-foreground">{contact.phone ?? '—'}</td>
                    <td className="px-4 py-3 capitalize text-muted-foreground">{contact.role ?? '—'}</td>
                    <td className="px-4 py-3">
                      {contact.is_primary && (
                        <span className="inline-flex items-center rounded-full bg-blue-100 px-2 py-0.5 text-xs font-medium text-blue-700">
                          Primary
                        </span>
                      )}
                    </td>
                    <td className="px-4 py-3">
                      <div className="flex items-center gap-1">
                        <Button
                          variant="ghost"
                          size="icon"
                          className="h-7 w-7"
                          onClick={() => openEditContact(contact)}
                        >
                          <Edit2 className="h-3.5 w-3.5" />
                        </Button>
                        <Button
                          variant="ghost"
                          size="icon"
                          className="h-7 w-7 text-red-500 hover:text-red-600"
                          onClick={() => handleDeleteContact(contact.id)}
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

      {/* Linked Projects section */}
      <div className="rounded-xl border bg-white shadow-sm">
        <div className="px-6 py-4 border-b">
          <h3 className="text-base font-semibold">Linked Projects</h3>
        </div>

        {projects.length === 0 ? (
          <p className="px-6 py-8 text-sm text-muted-foreground text-center">
            No projects linked to this client yet.
          </p>
        ) : (
          <ul className="divide-y">
            {projects.map((project) => (
              <li
                key={project.id}
                className="flex items-center justify-between px-6 py-4 hover:bg-muted/20 cursor-pointer"
                onClick={() => navigate(`/broker/projects/${project.id}`)}
              >
                <div>
                  <p className="text-sm font-medium">{project.name}</p>
                  <p className="text-xs text-muted-foreground mt-0.5">
                    {new Date(project.created_at).toLocaleDateString()}
                    {project.project_type && ` · ${project.project_type}`}
                  </p>
                </div>
                <StatusBadge status={project.status} />
              </li>
            ))}
          </ul>
        )}
      </div>

      {/* Add / Edit Contact Dialog */}
      <Dialog open={dialog.open} onOpenChange={(open) => !open && closeDialog()}>
        <DialogContent className="sm:max-w-md">
          <DialogHeader>
            <DialogTitle>
              {dialog.mode === 'add' ? 'Add Contact' : 'Edit Contact'}
            </DialogTitle>
          </DialogHeader>
          <form onSubmit={handleContactSubmit} className="space-y-4">
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
                placeholder="name@company.com"
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
                value={contactForm.role ?? ''}
                onChange={(e) => setContactForm((f) => ({ ...f, role: e.target.value }))}
                className="flex h-9 w-full rounded-md border border-input bg-transparent px-3 py-1 text-sm shadow-sm focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring"
              >
                <option value="">Select role (optional)</option>
                {CONTACT_ROLES.map((r) => (
                  <option key={r} value={r} className="capitalize">
                    {r.charAt(0).toUpperCase() + r.slice(1)}
                  </option>
                ))}
              </select>
            </div>
            <div className="flex items-center gap-2">
              <input
                type="checkbox"
                id="is_primary"
                checked={contactForm.is_primary ?? false}
                onChange={(e) => setContactForm((f) => ({ ...f, is_primary: e.target.checked }))}
                className="h-4 w-4 rounded border-input"
              />
              <label htmlFor="is_primary" className="text-sm font-medium">
                Primary contact
              </label>
            </div>
            <DialogFooter>
              <Button type="button" variant="outline" onClick={closeDialog}>
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
                  : dialog.mode === 'add'
                  ? 'Add Contact'
                  : 'Save Changes'}
              </Button>
            </DialogFooter>
          </form>
        </DialogContent>
      </Dialog>
    </div>
  )
}
