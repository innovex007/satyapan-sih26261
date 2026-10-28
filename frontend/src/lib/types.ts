import type { Status } from './status'

export interface Evidence {
  document_id: number | null
  filename: string | null
  doc_type: string
  page: number
  bbox: number[]
  value: string
  key?: string | null
  normalised?: string | null
  application_id?: string
}

export interface Finding {
  id: number
  application_id: string
  document_ids: number[]
  check_type: 'completeness' | 'expiry' | 'contradiction' | 'twin' | 'forensic' | 'source' | 'faculty'
  status: Status
  severity: 'low' | 'medium' | 'high'
  confidence: number
  reason: string
  rule_id: string
  evidence: Evidence[]
  how_to_clear: string
  officer_action: 'none' | 'accepted' | 'dismissed' | 'clarification_requested'
  officer_note: string
}

export interface DocItem {
  id: number
  filename: string
  doc_type: string
  label: string
  pages: number
  kind: 'text' | 'scan' | 'image'
  status: Status
  flags: number
}

export interface Workspace {
  application: { id: string; category: string; academic_session: string; risk_lane: 'Green' | 'Amber' | 'Red' | null; risk_score: number; cycle_label: string }
  institution: { name: string; permanent_id: string; state: string; region: string }
  groups: { group: string; documents: DocItem[] }[]
  missing: { doc_type: string; label: string }[]
  findings: Finding[]
  external?: DocItem[]
  source_checks: { document_id: number; channel: string; result: Status; simulated: boolean; response: unknown }[]
  is_archive: boolean
}
