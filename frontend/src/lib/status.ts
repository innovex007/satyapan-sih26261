export const STATUSES = [
  'Verified',
  'Mismatch detected',
  'Expired',
  'Verification pending',
  'Source unavailable',
  'Manual review required',
] as const
export type Status = (typeof STATUSES)[number]

export const STATUS_STYLE: Record<Status, { fg: string; bg: string }> = {
  'Verified': { fg: '#1E7B3A', bg: '#E3F5E8' },
  'Mismatch detected': { fg: '#C62828', bg: '#FDE3E3' },
  'Expired': { fg: '#C25E00', bg: '#FFEEDD' },
  'Verification pending': { fg: '#1F5FB4', bg: '#E3EEFC' },
  'Source unavailable': { fg: '#555555', bg: '#EEEEEE' },
  'Manual review required': { fg: '#6A3FB5', bg: '#EFE6FB' },
}

export const LANE_STYLE = {
  Green: { fg: '#1E7B3A', bg: '#E3F5E8' },
  Amber: { fg: '#B7791F', bg: '#FFF3D6' },
  Red: { fg: '#C62828', bg: '#FDE3E3' },
} as const
