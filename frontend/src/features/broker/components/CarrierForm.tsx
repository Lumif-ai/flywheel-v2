import { Input } from '@/components/ui/input'
import { Button } from '@/components/ui/button'
import { DialogFooter } from '@/components/ui/dialog'
import type { CarrierConfig, CreateCarrierPayload } from '../types/broker'

export const CARRIER_TYPES = [
  { value: 'insurance', label: 'Insurance' },
  { value: 'surety', label: 'Surety' },
]

export const SUBMISSION_METHODS = [
  { value: 'email', label: 'Email' },
  { value: 'portal', label: 'Portal' },
]

export interface CarrierFormState {
  carrier_name: string
  carrier_type: string
  submission_method: string
  portal_url: string
  portal_limit: string
  coverage_types: string
  regions: string
  min_project_value: string
  max_project_value: string
  avg_response_days: string
  notes: string
}

export const EMPTY_FORM: CarrierFormState = {
  carrier_name: '',
  carrier_type: 'insurance',
  submission_method: 'email',
  portal_url: '',
  portal_limit: '',
  coverage_types: '',
  regions: '',
  min_project_value: '',
  max_project_value: '',
  avg_response_days: '',
  notes: '',
}

export function carrierToForm(carrier: CarrierConfig): CarrierFormState {
  return {
    carrier_name: carrier.carrier_name,
    carrier_type: carrier.carrier_type,
    submission_method: carrier.submission_method,
    portal_url: carrier.portal_url ?? '',
    portal_limit: carrier.portal_limit != null ? String(carrier.portal_limit) : '',
    coverage_types: (carrier.coverage_types ?? []).join(', '),
    regions: (carrier.regions ?? []).join(', '),
    min_project_value: carrier.min_project_value != null ? String(carrier.min_project_value) : '',
    max_project_value: carrier.max_project_value != null ? String(carrier.max_project_value) : '',
    avg_response_days: carrier.avg_response_days != null ? String(carrier.avg_response_days) : '',
    notes: carrier.notes ?? '',
  }
}

export function formToPayload(form: CarrierFormState): CreateCarrierPayload {
  return {
    carrier_name: form.carrier_name.trim(),
    carrier_type: form.carrier_type,
    submission_method: form.submission_method,
    portal_url: form.portal_url.trim() || null,
    portal_limit: form.portal_limit ? Number(form.portal_limit) : null,
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

export function CarrierForm({
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
        <div className="grid grid-cols-2 gap-4">
          <div className="space-y-2">
            <label className="text-sm font-medium">Portal URL</label>
            <Input value={form.portal_url} onChange={set('portal_url')} placeholder="https://portal.carrier.com" />
          </div>
          <div className="space-y-2">
            <label className="text-sm font-medium">Portal Threshold ($)</label>
            <Input
              type="number"
              value={form.portal_limit}
              onChange={set('portal_limit')}
              placeholder="e.g. 500000"
            />
            <p className="text-xs text-muted-foreground">Projects above this value use portal submission</p>
          </div>
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
