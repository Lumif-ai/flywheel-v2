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

  const mutation = useCreateProject()

  function resetForm() {
    setName('')
    setProjectType('')
    setNotes('')
  }

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    if (!name.trim()) return

    mutation.mutate(
      {
        name: name.trim(),
        ...(projectType && { project_type: projectType }),
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
