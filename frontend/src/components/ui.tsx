import type { ReactNode } from 'react'
import { Inbox } from 'lucide-react'
import { LANE_STYLE, STATUS_STYLE, type Status } from '../lib/status'

export function Card({ title, children, className = '', dense = false }: { title?: string; children: ReactNode; className?: string; dense?: boolean }) {
  return (
    <section className={`card ${dense ? '!p-5' : ''} ${className}`}>
      {title && <h2 className={dense ? 'mb-3' : 'mb-4'}>{title}</h2>}
      {children}
    </section>
  )
}

export function StatusChip({ status }: { status: Status }) {
  const s = STATUS_STYLE[status]
  return (
    <span
      className="inline-flex items-center rounded-full px-2.5 py-0.5 text-[12px] leading-[18px] font-medium whitespace-nowrap"
      style={{ color: s.fg, background: s.bg }}
    >
      {status}
    </span>
  )
}

export function RiskPill({ lane }: { lane: keyof typeof LANE_STYLE | null | undefined }) {
  const s = lane ? LANE_STYLE[lane] : { fg: '#555555', bg: '#EEEEEE' }
  return (
    <span
      className="inline-flex items-center rounded-full px-2.5 py-0.5 text-[12px] leading-[18px] font-medium whitespace-nowrap"
      style={{ color: s.fg, background: s.bg }}
    >
      {lane ?? 'Not processed'}
    </span>
  )
}

export function EmptyState({ title, hint, compact = false }: { title: string; hint: string; compact?: boolean }) {
  return (
    <div className={`flex flex-col items-center justify-center text-center ${compact ? 'py-2' : 'py-12'}`}>
      <Inbox className={`${compact ? 'h-6 w-6 mb-2' : 'h-8 w-8 mb-3'} text-slate-300`} />
      <p className="font-medium text-slate-700">{title}</p>
      <p className="meta mt-1 max-w-sm">{hint}</p>
    </div>
  )
}

export function PageHeader({ title, subtitle, actions, tight = false }: { title: string; subtitle?: string; actions?: ReactNode; tight?: boolean }) {
  return (
    <div className={`flex items-start justify-between gap-6 ${tight ? 'mb-5' : 'mb-6'}`}>
      <div>
        <h1>{title}</h1>
        {subtitle && <p className="meta mt-1">{subtitle}</p>}
      </div>
      {actions}
    </div>
  )
}

export function Kpi({ label, value, hint }: { label: string; value: ReactNode; hint?: string }) {
  return (
    <div className="card !p-5">
      <p className="meta">{label}</p>
      <p className="text-[28px] leading-9 font-semibold text-slate-900 mt-1">{value}</p>
      <p className="meta mt-0.5 min-h-[18px]">{hint ?? ''}</p>
    </div>
  )
}
