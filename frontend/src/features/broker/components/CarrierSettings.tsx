import { useState } from 'react'
import { Link } from 'react-router'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Badge } from '@/components/ui/badge'
import { Skeleton } from '@/components/ui/skeleton'
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogFooter,
} from '@/components/ui/dialog'
import { ArrowLeft, Plus, Edit2, Power } from 'lucide-react'
import { toast } from 'sonner'
import { useCarriers } from '../hooks/useCarriers'
import { useCreateCarrier, useUpdateCarrier, useDeleteCarrier } from '../hooks/useCarrierMutations'
import type { CarrierConfig, CreateCarrierPayload, UpdateCarrierPayload } from '../types/broker'

const CARRIER_TYPES = [
  { value: 'insurance', label: 'Insurance' },
  { value: 'surety', label: 'Surety' },
]

const SUBMISSION_METHODS = [
  { value: 'email', label: 'Email' },
  { value: 'portal', label: 'Portal' },
]

interface CarrierFormState {
  carrier_name: string
  carrier_type: string
  submission_method: string
  portal_url: string
  email_address: string
  coverage_types: string
  regions: string
  min_project_value: string
  max_project_value: string
  avg_response_days: string
  notes: string
}

const EMPTY_FORM: CarrierFormState = {
  carrier_name: '',
  carrier_type: 'insurance',
  submission_method: 'email',
  portal_url: '',
  email_address: '',
  coverage_types: '',
  regions: '',
  min_project_value: '',
  max_project_value: '',
  avg_response_days: '',
  notes: '',
}

function carrierToForm(carrier: CarrierConfig): CarrierFormState {
  return {
    carrier_name: carrier.carrier_name,
    carrier_type: carrier.carrier_type,
    submission_method: carrier.submission_method,
    portal_url: carrier.portal_url ?? '',
    email_address: carrier.email_address ?? '',
    coverage_types: (carrier.coverage_types ?? []).join(', '),
    regions: (carrier.regions ?? []).join(', '),
    min_project_value: carrier.min_project_value != null ? String(carrier.min_project_value) : '',
    max_project_value: carrier.max_project_value != null ? String(carrier.max_project_value) : '',
    avg_response_days: carrier.avg_response_days != null ? String(carrier.avg_response_days) : '',
    notes: carrier.notes ?? '',
  }
}

function formToPayload(form: CarrierFormState): CreateCarrierPayload {
  return {
    carrier_name: form.carrier_name.trim(),
    carrier_type: form.carrier_type,
    submission_method: form.submission_method,
    portal_url: form.portal_url.trim() || null,
    email_address: form.email_address.trim() || null,
    coverage_types: form.coverage_types
      .split(',')
      .map((s) => s.trim())
      .filter(Boolean),
    regions: form.regions
      .split(',')
      .map((s) => s.trim())
      .filter(Boolean),
    min_project_value: form.min_project_value ? Number(form.min_project_value) : null,
    max_project_value: form.max_project_value ? Number(form.max_project_value) : null,
    avg_response_days: form.avg_response_days ? Number(form.avg_response_days) : null,
    notes: form.notes.trim() || null,
  }
}

function CarrierForm({
  form,
  onChange,
  onSubmit,
  isSubmitting,
  submitLabel,
}: {
  form: CarrierFormState
  onChange: (form: CarrierFormState) => void
  onSubmit: (e: React.FormEvent) => void
  isSubmitting: boolean
  submitLabel: string
}) {
  const set = (field: keyof CarrierFormState) => (e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement | HTMLTextAreaElement>) =>
    onChange({ ...form, [field]: e.target.value })

  return (
    <form onSubmit={onSubmit} className="space-y-4">
      <div className="space-y-2">
        <label className="text-sm font-medium">
          Carrier Name <span className="text-red-500">*</span>
        </label>
        <Input value={form.carrier_name} onChange={set('carrier_name')} placeholder="e.g. Mapfre" required />
      </div>

      <div className="grid grid-cols-2 gap-4">
        <div className="space-y-2">
          <label className="text-sm font-medium">Carrier Type</label>
          <select
            value={form.carrier_type}
            onChange={set('carrier_type')}
            className="flex h-9 w-full rounded-md border border-input bg-transparent px-3 py-1 text-sm shadow-sm focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring"
          >
            {CARRIER_TYPES.map((t) => (
              <option key={t.value} value={t.value}>{t.label}</option>
            ))}
          </select>
        </div>
        <div className="space-y-2">
          <label className="text-sm font-medium">Submission Method</label>
          <select
            value={form.submission_method}
            onChange={set('submission_method')}
            className="flex h-9 w-full rounded-md border border-input bg-transparent px-3 py-1 text-sm shadow-sm focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring"
          >
            {SUBMISSION_METHODS.map((t) => (
              <option key={t.value} value={t.value}>{t.label}</option>
            ))}
          </select>
        </div>
      </div>

      {form.submission_method === 'portal' && (
        <div className="space-y-2">
          <label className="text-sm font-medium">Portal URL</label>
          <Input value={form.portal_url} onChange={set('portal_url')} placeholder="https://portal.carrier.com" />
        </div>
      )}

      {form.submission_method === 'email' && (
        <div className="space-y-2">
          <label className="text-sm font-medium">Email Address</label>
          <Input value={form.email_address} onChange={set('email_address')} placeholder="submissions@carrier.com" type="email" />
        </div>
      )}

      <div className="space-y-2">
        <label className="text-sm font-medium">Coverage Types</label>
        <Input
          value={form.coverage_types}
          onChange={set('coverage_types')}
          placeholder="general_liability, property, auto (comma-separated)"
        />
      </div>

      <div className="space-y-2">
        <label className="text-sm font-medium">Regions</label>
        <Input value={form.regions} onChange={set('regions')} placeholder="MX-CDMX, MX-JAL (comma-separated)" />
      </div>

      <div className="grid grid-cols-3 gap-4">
        <div className="space-y-2">
          <label className="text-sm font-medium">Min Project Value</label>
          <Input type="number" value={form.min_project_value} onChange={set('min_project_value')} placeholder="0" />
        </div>
        <div className="space-y-2">
          <label className="text-sm font-medium">Max Project Value</label>
          <Input type="number" value={form.max_project_value} onChange={set('max_project_value')} placeholder="10000000" />
        </div>
        <div className="space-y-2">
          <label className="text-sm font-medium">Avg Response (days)</label>
          <Input type="number" value={form.avg_response_days} onChange={set('avg_response_days')} placeholder="5" />
        </div>
      </div>

      <div className="space-y-2">
        <label className="text-sm font-medium">Notes</label>
        <textarea
          value={form.notes}
          onChange={set('notes')}
          rows={2}
          placeholder="Additional notes about this carrier..."
          className="flex w-full rounded-md border border-input bg-transparent px-3 py-2 text-sm shadow-sm placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring"
        />
      </div>

      <DialogFooter>
        <Button type="submit" disabled={!form.carrier_name.trim() || isSubmitting}>
          {isSubmitting ? 'Saving...' : submitLabel}
        </Button>
      </DialogFooter>
    </form>
  )
}

export function CarrierSettings() {
  const { data: carriers, isLoading } = useCarriers()
  const createMutation = useCreateCarrier()
  const updateMutation = useUpdateCarrier()
  const deleteMutation = useDeleteCarrier()

  const [dialogOpen, setDialogOpen] = useState(false)
  const [editingCarrier, setEditingCarrier] = useState<CarrierConfig | null>(null)
  const [form, setForm] = useState<CarrierFormState>(EMPTY_FORM)
  const [confirmDeactivate, setConfirmDeactivate] = useState<string | null>(null)

  function openCreate() {
    setEditingCarrier(null)
    setForm(EMPTY_FORM)
    setDialogOpen(true)
  }

  function openEdit(carrier: CarrierConfig) {
    setEditingCarrier(carrier)
    setForm(carrierToForm(carrier))
    setDialogOpen(true)
  }

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    const payload = formToPayload(form)

    if (editingCarrier) {
      updateMutation.mutate(
        { id: editingCarrier.id, payload: payload as UpdateCarrierPayload },
        {
          onSuccess: () => {
            toast.success('Carrier updated')
            setDialogOpen(false)
          },
          onError: () => toast.error('Failed to update carrier'),
        },
      )
    } else {
      createMutation.mutate(payload, {
        onSuccess: () => {
          toast.success('Carrier added')
          setDialogOpen(false)
        },
        onError: () => toast.error('Failed to add carrier'),
      })
    }
  }

  function handleDeactivate(id: string) {
    deleteMutation.mutate(id, {
      onSuccess: () => {
        toast.success('Carrier deactivated')
        setConfirmDeactivate(null)
      },
      onError: () => toast.error('Failed to deactivate carrier'),
    })
  }

  if (isLoading) {
    return (
      <div className="p-6 space-y-4">
        <Skeleton className="h-8 w-60" />
        {Array.from({ length: 5 }).map((_, i) => (
          <Skeleton key={i} className="h-12 w-full rounded-lg" />
        ))}
      </div>
    )
  }

  return (
    <div className="p-6 space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <Link to="/broker" className="text-muted-foreground hover:text-foreground transition-colors">
            <ArrowLeft className="h-4 w-4" />
          </Link>
          <h1 className="text-2xl font-semibold">Carrier Settings</h1>
        </div>
        <Button onClick={openCreate}>
          <Plus className="mr-1.5 h-4 w-4" />
          Add Carrier
        </Button>
      </div>

      {/* Table */}
      {!carriers || carriers.length === 0 ? (
        <div className="rounded-xl border border-dashed p-8 text-center text-muted-foreground">
          No carriers configured yet. Click "Add Carrier" to get started.
        </div>
      ) : (
        <div className="overflow-x-auto rounded-xl border">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b bg-muted/50">
                <th className="px-3 py-2 text-left font-medium">Name</th>
                <th className="px-3 py-2 text-left font-medium">Type</th>
                <th className="px-3 py-2 text-left font-medium">Submission</th>
                <th className="px-3 py-2 text-left font-medium">Coverage Types</th>
                <th className="px-3 py-2 text-left font-medium">Status</th>
                <th className="px-3 py-2 text-right font-medium">Actions</th>
              </tr>
            </thead>
            <tbody>
              {carriers.map((carrier) => (
                <tr key={carrier.id} className="border-b last:border-0 hover:bg-muted/30">
                  <td className="px-3 py-2 font-medium">{carrier.carrier_name}</td>
                  <td className="px-3 py-2 capitalize">{carrier.carrier_type}</td>
                  <td className="px-3 py-2 capitalize">{carrier.submission_method}</td>
                  <td className="px-3 py-2">
                    <div className="flex flex-wrap gap-1">
                      {(carrier.coverage_types ?? []).slice(0, 3).map((ct) => (
                        <Badge key={ct} variant="outline" className="text-xs">
                          {ct}
                        </Badge>
                      ))}
                      {(carrier.coverage_types ?? []).length > 3 && (
                        <Badge variant="outline" className="text-xs">
                          +{carrier.coverage_types.length - 3}
                        </Badge>
                      )}
                    </div>
                  </td>
                  <td className="px-3 py-2">
                    <Badge
                      variant="outline"
                      className={
                        carrier.is_active
                          ? 'bg-green-50 text-green-700 border-0'
                          : 'bg-gray-50 text-gray-500 border-0'
                      }
                    >
                      {carrier.is_active ? 'Active' : 'Inactive'}
                    </Badge>
                  </td>
                  <td className="px-3 py-2 text-right">
                    <div className="flex items-center justify-end gap-1">
                      <Button variant="ghost" size="icon" className="h-7 w-7" onClick={() => openEdit(carrier)}>
                        <Edit2 className="h-3.5 w-3.5" />
                      </Button>
                      {carrier.is_active && (
                        <Button
                          variant="ghost"
                          size="icon"
                          className="h-7 w-7 text-orange-600 hover:text-orange-700"
                          onClick={() => setConfirmDeactivate(carrier.id)}
                        >
                          <Power className="h-3.5 w-3.5" />
                        </Button>
                      )}
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {/* Create/Edit Dialog */}
      <Dialog open={dialogOpen} onOpenChange={setDialogOpen}>
        <DialogContent className="sm:max-w-lg max-h-[90vh] overflow-y-auto">
          <DialogHeader>
            <DialogTitle>{editingCarrier ? 'Edit Carrier' : 'Add Carrier'}</DialogTitle>
          </DialogHeader>
          <CarrierForm
            form={form}
            onChange={setForm}
            onSubmit={handleSubmit}
            isSubmitting={createMutation.isPending || updateMutation.isPending}
            submitLabel={editingCarrier ? 'Save Changes' : 'Add Carrier'}
          />
        </DialogContent>
      </Dialog>

      {/* Deactivate Confirmation Dialog */}
      <Dialog open={!!confirmDeactivate} onOpenChange={() => setConfirmDeactivate(null)}>
        <DialogContent className="sm:max-w-sm">
          <DialogHeader>
            <DialogTitle>Deactivate Carrier?</DialogTitle>
          </DialogHeader>
          <p className="text-sm text-muted-foreground">
            This carrier will no longer appear in matching results. You can reactivate it later.
          </p>
          <DialogFooter>
            <Button variant="outline" onClick={() => setConfirmDeactivate(null)}>
              Cancel
            </Button>
            <Button
              variant="destructive"
              onClick={() => confirmDeactivate && handleDeactivate(confirmDeactivate)}
              disabled={deleteMutation.isPending}
            >
              {deleteMutation.isPending ? 'Deactivating...' : 'Deactivate'}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  )
}
