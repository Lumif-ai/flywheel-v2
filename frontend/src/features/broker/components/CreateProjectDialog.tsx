import { useState } from 'react'
import { Plus } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
  DialogFooter,
} from '@/components/ui/dialog'
import { useCreateProject } from '../hooks/useCreateProject'
import { useClients } from '../hooks/useClients'
import { useCreateClient } from '../hooks/useClientMutations'

const PROJECT_TYPES = [
  { value: 'construction', label: 'Construction' },
  { value: 'services', label: 'Services' },
  { value: 'supply', label: 'Supply' },
  { value: 'other', label: 'Other' },
]

export function CreateProjectDialog() {
  const [open, setOpen] = useState(false)
  const [name, setName] = useState('')
  const [projectType, setProjectType] = useState('')
  const [notes, setNotes] = useState('')

  // Client dropdown state
  const [selectedClientId, setSelectedClientId] = useState('')
  const [clientSearch, setClientSearch] = useState('')

  // Inline create-client state
  const [showCreateClientInline, setShowCreateClientInline] = useState(false)
  const [newClientName, setNewClientName] = useState('')
  const [newClientIndustry, setNewClientIndustry] = useState('')

  const mutation = useCreateProject()
  const createClientMutation = useCreateClient()

  // Fetch clients for dropdown
  const { data: clientsData } = useClients()
  const allClients = clientsData?.items ?? []
  const filteredClients = allClients.filter((c) =>
    c.name.toLowerCase().includes(clientSearch.toLowerCase())
  )

  function resetForm() {
    setName('')
    setProjectType('')
    setNotes('')
    setSelectedClientId('')
    setClientSearch('')
    setShowCreateClientInline(false)
    setNewClientName('')
    setNewClientIndustry('')
  }

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    if (!name.trim()) return

    mutation.mutate(
      {
        name: name.trim(),
        ...(projectType && { project_type: projectType }),
        // Only include client_id when a real UUID is selected (omit empty string to avoid 422)
        ...(selectedClientId ? { client_id: selectedClientId } : {}),
        ...(notes.trim() && { notes: notes.trim() }),
      },
      {
        onSuccess: () => {
          resetForm()
          setOpen(false)
        },
      },
    )
  }

  async function handleCreateClientInline() {
    if (!newClientName.trim()) return
    const created = await createClientMutation.mutateAsync({
      name: newClientName.trim(),
      ...(newClientIndustry.trim() ? { industry: newClientIndustry.trim() } : {}),
    })
    setSelectedClientId(created.id)
    setShowCreateClientInline(false)
    setNewClientName('')
    setNewClientIndustry('')
  }

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger
        render={
          <Button>
            <Plus className="mr-1.5 h-4 w-4" />
            New Project
          </Button>
        }
      />
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle>Create New Project</DialogTitle>
        </DialogHeader>
        <form onSubmit={handleSubmit} className="space-y-4">
          <div className="space-y-2">
            <label htmlFor="project-name" className="text-sm font-medium">
              Project Name <span className="text-red-500">*</span>
            </label>
            <Input
              id="project-name"
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="e.g. Acme Corp - Office Building"
              required
            />
          </div>

          <div className="space-y-2">
            <label htmlFor="project-type" className="text-sm font-medium">
              Contract Type
            </label>
            <select
              id="project-type"
              value={projectType}
              onChange={(e) => setProjectType(e.target.value)}
              className="flex h-9 w-full rounded-md border border-input bg-transparent px-3 py-1 text-sm shadow-sm transition-colors placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring"
            >
              <option value="">Select type (optional)</option>
              {PROJECT_TYPES.map((t) => (
                <option key={t.value} value={t.value}>
                  {t.label}
                </option>
              ))}
            </select>
          </div>

          {/* Client dropdown */}
          <div className="space-y-2">
            <label className="text-sm font-medium">Client (optional)</label>
            <Input
              placeholder="Search clients..."
              value={clientSearch}
              onChange={(e) => setClientSearch(e.target.value)}
              className="mb-1"
            />
            <select
              value={selectedClientId}
              onChange={(e) => {
                if (e.target.value === '__create_new__') {
                  setShowCreateClientInline(true)
                  setSelectedClientId('')
                } else {
                  setSelectedClientId(e.target.value)
                  setShowCreateClientInline(false)
                }
              }}
              className="flex h-9 w-full rounded-md border border-input bg-transparent px-3 py-1 text-sm shadow-sm focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring"
            >
              <option value="">No client</option>
              <option value="__create_new__">+ Create new client...</option>
              {filteredClients.map((c) => (
                <option key={c.id} value={c.id}>
                  {c.name}
                </option>
              ))}
            </select>

            {/* Inline quick-create panel */}
            {showCreateClientInline && (
              <div className="mt-2 p-3 border rounded-md bg-muted/50 space-y-2">
                <p className="text-xs font-medium text-muted-foreground">New client</p>
                <Input
                  placeholder="Client name *"
                  value={newClientName}
                  onChange={(e) => setNewClientName(e.target.value)}
                />
                <Input
                  placeholder="Industry (optional)"
                  value={newClientIndustry}
                  onChange={(e) => setNewClientIndustry(e.target.value)}
                />
                <div className="flex gap-2">
                  <Button
                    type="button"
                    size="sm"
                    onClick={handleCreateClientInline}
                    disabled={!newClientName.trim() || createClientMutation.isPending}
                  >
                    {createClientMutation.isPending ? 'Creating...' : 'Create'}
                  </Button>
                  <Button
                    type="button"
                    size="sm"
                    variant="outline"
                    onClick={() => {
                      setShowCreateClientInline(false)
                      setNewClientName('')
                      setNewClientIndustry('')
                    }}
                  >
                    Cancel
                  </Button>
                </div>
              </div>
            )}

            {/* Show selected client name when one is selected */}
            {selectedClientId && !showCreateClientInline && (
              <p className="text-xs text-muted-foreground">
                Selected:{' '}
                <span className="font-medium text-foreground">
                  {allClients.find((c) => c.id === selectedClientId)?.name}
                </span>
              </p>
            )}
          </div>

          <div className="space-y-2">
            <label htmlFor="project-notes" className="text-sm font-medium">
              Notes
            </label>
            <textarea
              id="project-notes"
              value={notes}
              onChange={(e) => setNotes(e.target.value)}
              placeholder="Additional context about this project..."
              rows={3}
              className="flex w-full rounded-md border border-input bg-transparent px-3 py-2 text-sm shadow-sm placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring"
            />
          </div>

          <DialogFooter>
            <Button
              type="submit"
              disabled={!name.trim() || mutation.isPending}
            >
              {mutation.isPending ? 'Creating...' : 'Create Project'}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  )
}
