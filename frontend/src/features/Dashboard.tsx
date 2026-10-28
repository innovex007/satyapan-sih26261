import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { Bar, BarChart, Cell, ResponsiveContainer, XAxis, YAxis, Tooltip } from 'recharts'
import { api } from '../lib/api'
import { LANE_STYLE } from '../lib/status'
import { Card, EmptyState, Kpi, PageHeader, RiskPill } from '../components/ui'

interface Attention {
  id: string
  institution: string
  reason: string
}

interface Summary {
  received: number
  ready_for_review: number
  open_flags: number
  avg_seconds_per_application: number | null
  risk_lanes: Record<string, number>
  findings_by_type: Record<string, number>
  needs_attention: Attention[]
  source_checks_pending: { count: number; oldest_age_hours: number | null }
  processed: number
}

const LANES = [
  { key: 'Red', color: LANE_STYLE.Red.fg },
  { key: 'Amber', color: '#F5A623' },
  { key: 'Green', color: LANE_STYLE.Green.fg },
  { key: 'Not processed', color: '#CBD5E1' },
] as const

const CHECK_LABEL: Record<string, string> = {
  completeness: 'Completeness', expiry: 'Expiry', contradiction: 'Cross-check', twin: 'Twin evidence',
  forensic: 'Forensic', source: 'Source', faculty: 'Faculty',
}

function LaneBar({ lanes, total, processed }: { lanes: Record<string, number>; total: number; processed: number }) {
  return (
    <div>
      <div className="flex h-6 w-full overflow-hidden rounded-md bg-slate-100">
        {LANES.map((l) => (lanes[l.key] ? <div key={l.key} title={`${l.key}: ${lanes[l.key]}`} style={{ width: `${(lanes[l.key] / total) * 100}%`, background: l.color }} /> : null))}
      </div>
      <div className="mt-2.5 grid grid-cols-4 gap-3">
        {LANES.map((l) => (
          <div key={l.key}>
            <div className="flex items-center gap-1.5 meta"><span className="h-2 w-2 rounded-full" style={{ background: l.color }} />{l.key}</div>
            <p className="text-[18px] leading-7 font-semibold text-slate-900">{lanes[l.key] ?? 0}</p>
          </div>
        ))}
      </div>
      <p className="meta mt-0.5">{processed} of {total} processed by the pipeline</p>
    </div>
  )
}

export function Dashboard() {
  const [d, setD] = useState<Summary | null>(null)
  useEffect(() => {
    api<Summary>('/dashboard/summary').then(setD).catch(() => setD(null))
  }, [])
  const show = (v: number | null | undefined) => (v == null ? '—' : v)
  const findings = Object.entries(d?.findings_by_type ?? {}).map(([k, v]) => ({ name: CHECK_LABEL[k] ?? k, value: v }))
  const pending = d?.source_checks_pending
  return (
    <>
      <PageHeader tight title="Dashboard" subtitle="Pre-scrutiny overview for the 2026-27 cycle" />
      <div className="grid grid-cols-4 gap-6 mb-6">
        <Kpi label="Applications received" value={show(d?.received)} />
        <Kpi label="Ready for review" value={show(d?.ready_for_review)} />
        <Kpi label="Flags awaiting officer" value={show(d?.open_flags)} />
        <Kpi label="Average time per application" value={d?.avg_seconds_per_application != null ? `${d.avg_seconds_per_application} s` : '—'} hint="pipeline, CPU only" />
      </div>
      <div className="grid grid-cols-2 gap-6">
        <Card dense title="Risk-lane distribution" className="h-[182px]">
          {d ? <LaneBar lanes={d.risk_lanes} total={Math.max(d.received, 1)} processed={d.processed} /> : null}
        </Card>
        <Card dense title="Findings by check type" className="h-[182px]">
          {findings.length ? (
            <ResponsiveContainer width="100%" height={104}>
              <BarChart data={findings} layout="vertical" barCategoryGap={2} margin={{ left: 8, right: 16, top: 0, bottom: 0 }}>
                <XAxis type="number" hide />
                <YAxis type="category" dataKey="name" width={96} interval={0} tickLine={false} axisLine={false} tick={{ fontSize: 12, fill: '#64748B' }} />
                <Tooltip cursor={{ fill: '#F1F5F9' }} />
                <Bar dataKey="value" radius={[0, 4, 4, 0]} barSize={9}>
                  {findings.map((f) => <Cell key={f.name} fill="#1F3864" />)}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          ) : (
            <EmptyState compact title="No findings yet" hint="Appear once the pipeline has processed applications." />
          )}
        </Card>
        <Card dense title="Needs attention" className="h-[182px]">
          {d?.needs_attention.length ? (
            <ul className="divide-y divide-slate-100">
              {d.needs_attention.slice(0, 3).map((a) => (
                <li key={a.id} className="flex items-center gap-3 py-1.5">
                  <RiskPill lane="Red" />
                  <Link to={`/workspace/${a.id}`} className="font-medium text-navy shrink-0">{a.id}</Link>
                  <span className="meta truncate">{a.reason}</span>
                </li>
              ))}
            </ul>
          ) : (
            <EmptyState compact title="Nothing flagged yet" hint="The top Red applications will be listed here." />
          )}
        </Card>
        <Card dense title="Source checks pending" className="h-[182px]">
          <p className="text-[28px] leading-9 font-semibold text-slate-900">{pending?.count ?? '—'}</p>
          <p className="meta mt-1">
            {pending?.oldest_age_hours != null ? `Oldest request ${pending.oldest_age_hours} h ago` : 'No requests awaiting a response'}
          </p>
          <p className="meta mt-3">Simulated source (prototype)</p>
        </Card>
      </div>
    </>
  )
}
