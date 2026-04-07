export interface Lead {
  id: string
  owner_id: string
  name: string
  domain: string | null
  purpose: string[]
  fit_score: number | null
  fit_tier: string | null
  fit_rationale: string | null
  intel: Record<string, unknown>
  source: string
  campaign: string | null
  pipeline_stage: string
  contact_count: number
  account_id: string | null
  created_at: string
  updated_at: string
  contacts?: LeadContact[]
}

export interface LeadContact {
  id: string
  lead_id: string
  name: string
  email: string | null
  title: string | null
  linkedin_url: string | null
  role: string | null
  pipeline_stage: string
  notes: string | null
  created_at: string
  messages?: LeadMessage[]
}

export interface LeadMessageMetadata {
  cadence_days?: number
  send_after?: string
}

export interface LeadMessage {
  id: string
  step_number: number
  channel: 'email' | 'linkedin'
  status: 'drafted' | 'sent' | 'delivered' | 'replied' | 'bounced'
  subject: string | null
  body: string | null
  from_email: string | null
  drafted_at: string | null
  sent_at: string | null
  replied_at: string | null
  metadata: LeadMessageMetadata
  created_at: string
}

export interface LeadsResponse {
  items: Lead[]
  total: number
  offset: number
  limit: number
}

export interface PipelineFunnel {
  funnel: Record<string, number>
  total: number
}

export interface LeadParams {
  offset?: number
  limit?: number
  pipeline_stage?: string
  fit_tier?: string
  purpose?: string
  search?: string
}

/** Flattened row for person-level table with company info attached */
export interface LeadRow {
  // Contact fields
  contact_id: string
  contact_name: string
  email: string | null
  title: string | null
  linkedin_url: string | null
  role: string | null
  contact_stage: string
  messages: LeadMessage[]
  // Company fields
  lead_id: string
  company_name: string
  domain: string | null
  purpose: string[]
  fit_tier: string | null
  fit_rationale: string | null
  source: string
  created_at: string
}

/** Flatten leads response into person-level rows */
export function flattenLeadsToRows(leads: Lead[]): LeadRow[] {
  const rows: LeadRow[] = []
  for (const lead of leads) {
    for (const contact of lead.contacts ?? []) {
      rows.push({
        contact_id: contact.id,
        contact_name: contact.name,
        email: contact.email,
        title: contact.title,
        linkedin_url: contact.linkedin_url,
        role: contact.role,
        contact_stage: contact.pipeline_stage,
        messages: contact.messages ?? [],
        lead_id: lead.id,
        company_name: lead.name,
        domain: lead.domain,
        purpose: lead.purpose,
        fit_tier: lead.fit_tier,
        fit_rationale: lead.fit_rationale,
        source: lead.source,
        created_at: contact.created_at,
      })
    }
  }
  return rows
}

export const STAGE_COLORS: Record<string, string> = {
  scraped: '#9CA3AF',
  scored: '#7C8DB5',
  researched: '#6882B8',
  drafted: '#D4885A',
  sent: '#5B94C6',
  replied: '#5EAA7D',
}

export const STAGE_ORDER = ['scraped', 'scored', 'researched', 'drafted', 'sent', 'replied']
